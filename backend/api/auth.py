"""Authentication endpoints for user registration and login."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import COOKIE_SECURE, COOKIE_HTTPONLY, COOKIE_SAMESITE, ACCESS_TOKEN_EXPIRE_MINUTES
from core.security import (
    create_access_token,
    decode_access_token,
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


@router.post("/auth/signup", status_code=status.HTTP_201_CREATED)
async def signup(
    form: SignUpForm, db: AsyncSession = Depends(get_session)
) -> JSONResponse:
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
    # Create session token
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
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=COOKIE_HTTPONLY,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    return response


@router.post("/auth/login")
async def login(
    form: LoginForm, db: AsyncSession = Depends(get_session)
) -> JSONResponse:
    """Authenticate user credentials and set a session cookie."""
    result = await db.execute(select(User).filter_by(email=form.email))
    user = result.scalars().first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

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
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=COOKIE_HTTPONLY,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    return response


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
