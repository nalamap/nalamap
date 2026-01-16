"""ORM model for map-layer composition."""

from sqlalchemy import Column, ForeignKey, text
from sqlalchemy.dialects.postgresql import BOOLEAN, INTEGER, UUID

from db.base import Base


class MapLayer(Base):
    """Join table for associating layers with maps."""

    __tablename__ = "map_layers"

    map_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maps.id", ondelete="CASCADE"),
        primary_key=True,
    )
    layer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("layers.id", ondelete="CASCADE"),
        primary_key=True,
    )
    z_index = Column(INTEGER, nullable=False, server_default=text("0"))
    visible = Column(BOOLEAN, nullable=False, server_default=text("true"))
