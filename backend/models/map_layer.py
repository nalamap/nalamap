"""Pydantic models for map-layer composition."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from models.layer import LayerRead


class MapLayerItem(BaseModel):
    """Payload entry for setting map layers."""

    layer_id: UUID
    z_index: int
    visible: bool = True

    model_config = ConfigDict(extra="forbid")


class MapLayerRead(LayerRead):
    """Layer details with map-specific metadata."""

    z_index: int
    visible: bool

    model_config = ConfigDict(from_attributes=True, extra="forbid")
