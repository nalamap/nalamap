"""Tests for Map, Layer, and MapLayer ORM model definitions."""

import pytest
from sqlalchemy.dialects.postgresql import BOOLEAN, INTEGER, JSONB, TEXT, UUID as PG_UUID

from db.models.layer import Layer
from db.models.map import Map
from db.models.map_layer import MapLayer


@pytest.mark.unit
def test_map_model_columns():
    """Verify the Map ORM model columns and their properties."""
    assert Map.__tablename__ == "maps"

    columns = {col.name: col for col in Map.__table__.columns}

    assert "id" in columns
    id_col = columns["id"]
    assert isinstance(id_col.type, PG_UUID)
    assert id_col.primary_key
    assert id_col.server_default is not None
    assert id_col.server_default.arg.text == "gen_random_uuid()"

    assert "owner_id" in columns
    owner_col = columns["owner_id"]
    assert isinstance(owner_col.type, PG_UUID)
    assert owner_col.nullable
    assert {fk.target_fullname for fk in owner_col.foreign_keys} == {"users.id"}

    assert "name" in columns
    name_col = columns["name"]
    assert isinstance(name_col.type, TEXT)
    assert not name_col.nullable

    assert "description" in columns
    description_col = columns["description"]
    assert isinstance(description_col.type, TEXT)
    assert description_col.nullable


@pytest.mark.unit
def test_layer_model_columns():
    """Verify the Layer ORM model columns and their properties."""
    assert Layer.__tablename__ == "layers"

    columns = {col.name: col for col in Layer.__table__.columns}

    assert "id" in columns
    id_col = columns["id"]
    assert isinstance(id_col.type, PG_UUID)
    assert id_col.primary_key
    assert id_col.server_default is not None
    assert id_col.server_default.arg.text == "gen_random_uuid()"

    assert "owner_id" in columns
    owner_col = columns["owner_id"]
    assert isinstance(owner_col.type, PG_UUID)
    assert owner_col.nullable
    assert {fk.target_fullname for fk in owner_col.foreign_keys} == {"users.id"}

    assert "data_link" in columns
    data_link_col = columns["data_link"]
    assert isinstance(data_link_col.type, TEXT)
    assert not data_link_col.nullable

    assert "data_type" in columns
    data_type_col = columns["data_type"]
    assert isinstance(data_type_col.type, TEXT)
    assert not data_type_col.nullable

    assert "name" in columns
    name_col = columns["name"]
    assert isinstance(name_col.type, TEXT)
    assert not name_col.nullable

    assert "description" in columns
    description_col = columns["description"]
    assert isinstance(description_col.type, TEXT)
    assert description_col.nullable

    assert "derived" in columns
    derived_col = columns["derived"]
    assert isinstance(derived_col.type, BOOLEAN)
    assert not derived_col.nullable
    assert derived_col.server_default is not None
    assert derived_col.server_default.arg.text == "false"

    assert "style" in columns
    style_col = columns["style"]
    assert isinstance(style_col.type, JSONB)
    assert style_col.nullable

    assert "payload" in columns
    payload_col = columns["payload"]
    assert isinstance(payload_col.type, JSONB)
    assert payload_col.nullable


@pytest.mark.unit
def test_map_layer_model_columns():
    """Verify the MapLayer ORM model columns and their properties."""
    assert MapLayer.__tablename__ == "map_layers"

    columns = {col.name: col for col in MapLayer.__table__.columns}

    assert "map_id" in columns
    map_id_col = columns["map_id"]
    assert isinstance(map_id_col.type, PG_UUID)
    assert map_id_col.primary_key
    assert {fk.target_fullname for fk in map_id_col.foreign_keys} == {"maps.id"}

    assert "layer_id" in columns
    layer_id_col = columns["layer_id"]
    assert isinstance(layer_id_col.type, PG_UUID)
    assert layer_id_col.primary_key
    assert {fk.target_fullname for fk in layer_id_col.foreign_keys} == {"layers.id"}

    assert "z_index" in columns
    z_index_col = columns["z_index"]
    assert isinstance(z_index_col.type, INTEGER)
    assert not z_index_col.nullable
    assert z_index_col.server_default is not None
    assert z_index_col.server_default.arg.text == "0"

    assert "visible" in columns
    visible_col = columns["visible"]
    assert isinstance(visible_col.type, BOOLEAN)
    assert not visible_col.nullable
    assert visible_col.server_default is not None
    assert visible_col.server_default.arg.text == "true"

    assert set(MapLayer.__table__.primary_key.columns.keys()) == {"map_id", "layer_id"}
