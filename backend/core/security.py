"""Security utilities for password hashing and JWT tokens."""

from datetime import datetime, timedelta
from uuid import uuid4

from jose import jwt  # , JWTError
from passlib.context import CryptContext

from core.config import SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES

# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")
ALGORITHM = "HS256"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its hashed value."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a plaintext password."""
    # bcrypt has a maximum input length of 72 bytes. Reject overly long
    # passwords early with a clear message so the client can respond.
    pw_bytes = password.encode("utf-8")
    if len(pw_bytes) > 72:
        raise ValueError(
            "Password too long: bcrypt supports up to 72 bytes. "
            "Please use a shorter password (max 72 bytes)."
        )

    return pwd_context.hash(password)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token with an expiration and subject (user ID)."""
    to_encode = {"sub": subject}
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode a JWT token and return the payload."""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def create_oauth_state(provider: str, redirect_url: str, expires_minutes: int = 10) -> str:
    """Create a short-lived signed state token for OIDC flows."""
    now = datetime.utcnow()
    payload = {
        "provider": provider,
        "redirect": redirect_url,
        "nonce": uuid4().hex,
        "exp": now + timedelta(minutes=expires_minutes),
        "iat": now,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_oauth_state(token: str) -> dict:
    """Decode and validate an OAuth state token."""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
