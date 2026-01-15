"""Pydantic models for map CRUD."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MapBase(BaseModel):
    """Shared fields for map payloads."""

    name: str
    description: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class MapCreate(MapBase):
    """Payload for creating a map."""


class MapUpdate(BaseModel):
    """Payload for updating a map."""

    name: Optional[str] = None
    description: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class MapRead(MapBase):
    """Response model for a map."""

    id: UUID

    model_config = ConfigDict(from_attributes=True, extra="forbid")
