"""CRUD endpoints for layers."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from db.models.layer import Layer
from db.models.user import User
from db.session import get_session
from models.layer import LayerCreate, LayerRead, LayerUpdate


router = APIRouter(prefix="/layers", tags=["layers"])


@router.post("/", response_model=LayerRead, status_code=status.HTTP_201_CREATED)
async def create_layer(
    payload: LayerCreate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> LayerRead:
    """Create a layer."""
    layer_obj = Layer(
        data_link=payload.data_link,
        data_type=payload.data_type,
        name=payload.name,
        description=payload.description,
        derived=payload.derived,
        style=payload.style,
        payload=payload.payload,
        owner_id=current_user.id,
    )
    db.add(layer_obj)
    await db.commit()
    await db.refresh(layer_obj)
    return LayerRead.model_validate(layer_obj)


@router.get("/", response_model=list[LayerRead])
async def list_layers(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[LayerRead]:
    """List layers."""
    result = await db.execute(
        select(Layer)
        .where(Layer.owner_id == current_user.id)
        .order_by(Layer.name.asc())
        .limit(limit)
        .offset(offset)
    )
    return [LayerRead.model_validate(item) for item in result.scalars().all()]


@router.get("/{layer_id}", response_model=LayerRead)
async def get_layer(
    layer_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> LayerRead:
    """Fetch a layer by id."""
    result = await db.execute(
        select(Layer).where(Layer.id == layer_id, Layer.owner_id == current_user.id)
    )
    layer_obj = result.scalars().first()
    if not layer_obj:
        raise HTTPException(status_code=404, detail="Layer not found")
    return LayerRead.model_validate(layer_obj)


@router.patch("/{layer_id}", response_model=LayerRead)
async def update_layer(
    layer_id: UUID,
    payload: LayerUpdate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> LayerRead:
    """Update a layer."""
    result = await db.execute(
        select(Layer).where(Layer.id == layer_id, Layer.owner_id == current_user.id)
    )
    layer_obj = result.scalars().first()
    if not layer_obj:
        raise HTTPException(status_code=404, detail="Layer not found")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    payload_update = updates.pop("payload", None)
    if payload_update is not None:
        if payload_update:
            existing_payload = layer_obj.payload or {}
            layer_obj.payload = {**existing_payload, **payload_update}
        else:
            layer_obj.payload = payload_update

    for key, value in updates.items():
        setattr(layer_obj, key, value)

    await db.commit()
    await db.refresh(layer_obj)
    return LayerRead.model_validate(layer_obj)


@router.delete("/{layer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_layer(
    layer_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Delete a layer."""
    result = await db.execute(
        select(Layer).where(Layer.id == layer_id, Layer.owner_id == current_user.id)
    )
    layer_obj = result.scalars().first()
    if not layer_obj:
        raise HTTPException(status_code=404, detail="Layer not found")

    await db.delete(layer_obj)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
