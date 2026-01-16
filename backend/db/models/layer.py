"""ORM model for the layers table."""

from sqlalchemy import Column, ForeignKey, text
from sqlalchemy.dialects.postgresql import BOOLEAN, JSONB, TEXT, UUID

from db.base import Base


class Layer(Base):
    """Layer metadata and styling."""

    __tablename__ = "layers"

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
    data_link = Column(TEXT, nullable=False)
    data_type = Column(TEXT, nullable=False)
    name = Column(TEXT, nullable=False)
    description = Column(TEXT, nullable=True)
    derived = Column(BOOLEAN, nullable=False, server_default=text("false"))
    style = Column(JSONB, nullable=True)
    payload = Column(JSONB, nullable=True)
