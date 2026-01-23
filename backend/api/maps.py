"""CRUD endpoints for maps."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from db.models.layer import Layer
from db.models.map import Map
from db.models.map_layer import MapLayer
from db.models.user import User
from db.session import get_session
from models.layer import LayerRead
from models.map_layer import MapLayerItem, MapLayerRead
from models.map import MapCreate, MapRead, MapUpdate


router = APIRouter(prefix="/maps", tags=["maps"])


async def _get_map_for_user(
    map_id: UUID,
    db: AsyncSession,
    current_user: User,
) -> Map:
    result = await db.execute(select(Map).where(Map.id == map_id, Map.owner_id == current_user.id))
    map_obj = result.scalars().first()
    if not map_obj:
        raise HTTPException(status_code=404, detail="Map not found")
    return map_obj


@router.post("/", response_model=MapRead, status_code=status.HTTP_201_CREATED)
async def create_map(
    payload: MapCreate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MapRead:
    """Create a map."""
    map_obj = Map(
        name=payload.name,
        description=payload.description,
        owner_id=current_user.id,
    )
    db.add(map_obj)
    await db.commit()
    await db.refresh(map_obj)
    return MapRead.model_validate(map_obj)


@router.get("/", response_model=list[MapRead])
async def list_maps(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[MapRead]:
    """List maps."""
    result = await db.execute(
        select(Map)
        .where(Map.owner_id == current_user.id)
        .order_by(Map.name.asc())
        .limit(limit)
        .offset(offset)
    )
    return [MapRead.model_validate(item) for item in result.scalars().all()]


@router.get("/{map_id}", response_model=MapRead)
async def get_map(
    map_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MapRead:
    """Fetch a map by id."""
    map_obj = await _get_map_for_user(map_id, db, current_user)
    return MapRead.model_validate(map_obj)


@router.patch("/{map_id}", response_model=MapRead)
async def update_map(
    map_id: UUID,
    payload: MapUpdate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MapRead:
    """Update a map."""
    map_obj = await _get_map_for_user(map_id, db, current_user)

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    for key, value in updates.items():
        setattr(map_obj, key, value)

    await db.commit()
    await db.refresh(map_obj)
    return MapRead.model_validate(map_obj)


@router.delete("/{map_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_map(
    map_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Delete a map."""
    map_obj = await _get_map_for_user(map_id, db, current_user)

    await db.delete(map_obj)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{map_id}/layers", response_model=list[MapLayerRead])
async def list_map_layers(
    map_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[MapLayerRead]:
    """List layers for a map."""
    await _get_map_for_user(map_id, db, current_user)

    result = await db.execute(
        select(MapLayer, Layer)
        .join(Layer, MapLayer.layer_id == Layer.id)
        .where(MapLayer.map_id == map_id, Layer.owner_id == current_user.id)
        .order_by(MapLayer.z_index.asc())
    )

    records: list[MapLayerRead] = []
    for map_layer, layer in result.all():
        base = LayerRead.model_validate(layer).model_dump()
        records.append(
            MapLayerRead.model_validate(
                {
                    **base,
                    "z_index": map_layer.z_index,
                    "visible": map_layer.visible,
                }
            )
        )

    return records


@router.put("/{map_id}/layers")
async def replace_map_layers(
    map_id: UUID,
    payload: list[MapLayerItem],
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Replace map layer composition."""
    await _get_map_for_user(map_id, db, current_user)

    layer_ids = {item.layer_id for item in payload}
    if layer_ids:
        result = await db.execute(
            select(Layer.id).where(Layer.id.in_(layer_ids), Layer.owner_id == current_user.id)
        )
        existing_ids = {row[0] for row in result.all()}
        missing = layer_ids - existing_ids
        if missing:
            raise HTTPException(status_code=404, detail="Layer not found")

    await db.execute(delete(MapLayer).where(MapLayer.map_id == map_id))
    for item in payload:
        db.add(
            MapLayer(
                map_id=map_id,
                layer_id=item.layer_id,
                z_index=item.z_index,
                visible=item.visible,
            )
        )

    await db.commit()
    return {"saved": len(payload)}
