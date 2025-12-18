"""Authentication endpoints for user registration, login, and OIDC sign-in."""

from urllib.parse import urlparse

from authlib.integrations.httpx_client import AsyncOAuth2Client
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    BASE_URL,
    COOKIE_HTTPONLY,
    COOKIE_SAMESITE,
    COOKIE_SECURE,
    FRONTEND_BASE_URL,
    get_oidc_providers,
)
from core.security import (
    create_access_token,
    create_oauth_state,
    decode_access_token,
    decode_oauth_state,
    get_password_hash,
    verify_password,
)
from jose import JWTError
from db.models.user import User
from db.session import get_session

from pydantic import BaseModel


router = APIRouter()


class SignUpForm(BaseModel):
    email: str
    password: str
    display_name: str | None = None


class LoginForm(BaseModel):
    email: str
    password: str


def _set_session_cookie(response: JSONResponse | RedirectResponse, token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=COOKIE_HTTPONLY,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


def _issue_session_response(user: User) -> JSONResponse:
    token = create_access_token(str(user.id))
    response = JSONResponse(
        content={
            "user": {
                "id": str(user.id),
                "email": user.email,
                "display_name": user.display_name,
            }
        }
    )
    _set_session_cookie(response, token)
    return response


def _default_redirect_url() -> str:
    return f"{FRONTEND_BASE_URL.rstrip('/')}/map"


def _validate_redirect(redirect_url: str | None) -> str:
    """Allow only redirects pointing to the configured frontend origin."""
    if not redirect_url:
        return _default_redirect_url()

    target = urlparse(redirect_url)
    allowed = urlparse(FRONTEND_BASE_URL)
    if not target.scheme and not target.netloc:
        # Relative path - anchor to allowed origin
        redirect_url = f"{allowed.scheme}://{allowed.netloc}{redirect_url}"
        target = urlparse(redirect_url)

    if target.scheme == allowed.scheme and target.netloc == allowed.netloc:
        return redirect_url

    raise HTTPException(status_code=400, detail="Invalid redirect URL")


def _get_provider_config(name: str) -> dict:
    providers = {p["name"]: p for p in get_oidc_providers()}
    provider = providers.get(name)
    if not provider:
        raise HTTPException(status_code=404, detail="OIDC provider not configured")
    return provider


async def _fetch_oidc_metadata(client: AsyncOAuth2Client, issuer: str) -> dict:
    """Fetch OIDC metadata document."""
    url = f"{issuer}/.well-known/openid-configuration"
    try:
        async with httpx.AsyncClient() as http_client:
            resp = await http_client.get(url, timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:  # pragma: no cover - network errors
        raise HTTPException(status_code=502, detail=f"Failed to load OIDC metadata: {exc}")


@router.post("/auth/signup", status_code=status.HTTP_201_CREATED)
async def signup(form: SignUpForm, db: AsyncSession = Depends(get_session)) -> JSONResponse:
    """Register a new user and set a session cookie."""
    # Check if email already exists
    result = await db.execute(select(User).filter_by(email=form.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")

    try:
        password_hash = get_password_hash(form.password)
    except ValueError as exc:
        # Surface a clear, client-friendly error when password is too long
        raise HTTPException(status_code=400, detail=str(exc))

    user = User(email=form.email, display_name=form.display_name, password_hash=password_hash)
    db.add(user)
    await db.commit()
    return _issue_session_response(user)


@router.post("/auth/login")
async def login(form: LoginForm, db: AsyncSession = Depends(get_session)) -> JSONResponse:
    """Authenticate user credentials and set a session cookie."""
    result = await db.execute(select(User).filter_by(email=form.email))
    user = result.scalars().first()
    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return _issue_session_response(user)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response):
    """Clear the session cookie."""
    response.delete_cookie("access_token", path="/")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/auth/me")
async def me(request: Request, db: AsyncSession = Depends(get_session)):
    """Return the current user based on session cookie."""
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(User).filter_by(id=user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {"id": str(user.id), "email": user.email, "display_name": user.display_name}


@router.get("/auth/oidc/providers")
async def list_oidc_providers():
    """Return configured OIDC providers for the frontend."""
    providers = get_oidc_providers()
    return [{"name": p["name"], "issuer": p["issuer"], "scopes": p["scopes"]} for p in providers]


@router.get("/auth/oidc/login")
async def oidc_login(
    provider: str = Query(..., description="OIDC provider name"),
    redirect: str | None = Query(None, description="Redirect URL after login"),
):
    """Initiate an OIDC login by redirecting to the provider's authorization endpoint."""
    provider_cfg = _get_provider_config(provider)
    redirect_url = _validate_redirect(redirect)

    client = AsyncOAuth2Client(
        provider_cfg["client_id"],
        provider_cfg["client_secret"],
        scope=provider_cfg["scopes"].split(),
        redirect_uri=f"{BASE_URL.rstrip('/')}/api/auth/oidc/callback",
    )
    metadata = await _fetch_oidc_metadata(client, provider_cfg["issuer"])

    authorization_endpoint = metadata.get("authorization_endpoint")
    if not authorization_endpoint:
        raise HTTPException(status_code=502, detail="OIDC authorization endpoint not found")

    state_token = create_oauth_state(provider=provider, redirect_url=redirect_url)
    auth_url, _ = client.create_authorization_url(
        authorization_endpoint,
        state=state_token,
        prompt="select_account",
    )
    return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)


@router.get("/auth/oidc/callback")
async def oidc_callback(
    request: Request,
    code: str = Query(..., description="Authorization code"),
    state: str = Query(..., description="Signed state parameter"),
    db: AsyncSession = Depends(get_session),
):
    """Handle OIDC callback, create or link user, and set session cookie."""
    try:
        state_payload = decode_oauth_state(state)
        provider_name = state_payload.get("provider")
        redirect_url = _validate_redirect(state_payload.get("redirect"))
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    provider_cfg = _get_provider_config(provider_name)

    client = AsyncOAuth2Client(
        provider_cfg["client_id"],
        provider_cfg["client_secret"],
        scope=provider_cfg["scopes"].split(),
        redirect_uri=str(request.url.replace(path="/api/auth/oidc/callback", query="")),
    )
    metadata = await _fetch_oidc_metadata(client, provider_cfg["issuer"])

    token_endpoint = metadata.get("token_endpoint")
    userinfo_endpoint = metadata.get("userinfo_endpoint")
    if not token_endpoint or not userinfo_endpoint:
        raise HTTPException(status_code=500, detail="OIDC provider metadata incomplete")

    try:
        token = await client.fetch_token(token_endpoint, code=code)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=502, detail=f"Failed to exchange code: {exc}")
    client.token = token
    try:
        userinfo_resp = await client.get(userinfo_endpoint)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=502, detail=f"Failed to fetch user info: {exc}")
    userinfo = userinfo_resp.json()

    sub = userinfo.get("sub")
    email = userinfo.get("email")
    display_name = userinfo.get("name") or email or provider_name
    if not sub:
        raise HTTPException(status_code=400, detail="OIDC userinfo missing sub")

    # Resolve or create user
    result = await db.execute(
        select(User).filter_by(oidc_provider=provider_name, oidc_subject=sub)
    )
    user = result.scalars().first()

    if not user and email:
        # Link to an existing email-based account if present
        email_match = await db.execute(select(User).filter_by(email=email))
        user = email_match.scalars().first()
        if user:
            user.oidc_provider = provider_name
            user.oidc_subject = sub

    if not user:
        user = User(
            email=email or f"{provider_name}:{sub}",
            display_name=display_name,
            oidc_provider=provider_name,
            oidc_subject=sub,
            password_hash=None,
        )
        db.add(user)
        await db.flush()

    await db.commit()

    token = create_access_token(str(user.id))
    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)
    _set_session_cookie(response, token)
    return response
