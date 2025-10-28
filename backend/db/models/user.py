"""ORM model for the users table."""

from sqlalchemy import Column, text
from sqlalchemy.dialects.postgresql import UUID, TEXT, TIMESTAMP

from db.base import Base


class User(Base):
    """User account information."""

    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    email = Column(TEXT, nullable=False, unique=True)
    display_name = Column(TEXT, nullable=True)
    password_hash = Column(TEXT, nullable=False)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
