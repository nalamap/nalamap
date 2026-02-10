"""Shared API dependencies."""

import logging
from types import SimpleNamespace
from uuid import UUID as UUIDType

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import AUTH_ENABLED
from core.security import decode_access_token
from db.models.user import User
from db.session import get_session

logger = logging.getLogger(__name__)

# Anonymous user stub returned when authentication is disabled.
# Uses SimpleNamespace so it behaves like an ORM object with attribute access.
ANONYMOUS_USER = SimpleNamespace(
    id="00000000-0000-0000-0000-000000000000",
    email="anonymous@localhost",
    display_name="Anonymous",
)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> User:
    """Return the current authenticated user based on session cookie.

    When ``AUTH_ENABLED`` is ``False`` an anonymous stub is returned so that
    map/layer persistence routes still work without requiring login.
    """
    if not AUTH_ENABLED:
        return ANONYMOUS_USER  # type: ignore[return-value]

    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    # Validate user_id is a valid UUID format before database query
    try:
        UUIDType(user_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user
