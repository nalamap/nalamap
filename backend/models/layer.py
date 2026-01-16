"""Pydantic models for layer CRUD."""

from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LayerBase(BaseModel):
    """Shared fields for layer payloads."""

    data_link: str
    data_type: str
    name: str
    description: Optional[str] = None
    derived: bool = False
    style: Optional[Dict[str, Any]] = None
    payload: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="forbid")


class LayerCreate(LayerBase):
    """Payload for creating a layer."""


class LayerUpdate(BaseModel):
    """Payload for updating a layer."""

    data_link: Optional[str] = None
    data_type: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    derived: Optional[bool] = None
    style: Optional[Dict[str, Any]] = None
    payload: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="forbid")


class LayerRead(LayerBase):
    """Response model for a layer."""

    id: UUID

    model_config = ConfigDict(from_attributes=True, extra="forbid")
