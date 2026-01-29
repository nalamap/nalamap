"""ORM model for the maps table."""

from sqlalchemy import Column, ForeignKey, text
from sqlalchemy.dialects.postgresql import TEXT, UUID

from db.base import Base


class Map(Base):
    """Map metadata."""

    __tablename__ = "maps"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    name = Column(TEXT, nullable=False)
    description = Column(TEXT, nullable=True)
