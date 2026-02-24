import pytest

from models.geodata import ProcessingMetadata


@pytest.mark.unit
def test_processing_metadata_geocoding_fields():
    """ProcessingMetadata should accept optional geocoding fields."""
    meta = ProcessingMetadata(
        operation="overpass_query",
        crs_used="EPSG:4326",
        crs_name="WGS 84",
        auto_selected=True,
        query_intent="residential buildings",
        query_location="Bonn Nordstadt",
        resolution_method="semantic",
        resolution_detail="expanded via tag embeddings + LLM",
        osm_tags_used=["building=residential", "building=apartments"],
        osm_tags_excluded=[{"tag": "landuse=residential", "reason": "land zoning, not buildings"}],
        overpass_query='[out:json];nwr["building"~"^(residential|apartments)$"];',
    )
    assert meta.query_intent == "residential buildings"
    assert len(meta.osm_tags_used) == 2
    assert meta.osm_tags_excluded[0]["tag"] == "landuse=residential"
    assert meta.resolution_method == "semantic"
    assert meta.overpass_query is not None


@pytest.mark.unit
def test_processing_metadata_geocoding_fields_optional():
    """Geocoding fields should be optional (None by default)."""
    meta = ProcessingMetadata(
        operation="overpass_query",
        crs_used="EPSG:4326",
        crs_name="WGS 84",
        auto_selected=True,
    )
    assert meta.query_intent is None
    assert meta.query_location is None
    assert meta.resolution_method is None
    assert meta.resolution_detail is None
    assert meta.osm_tags_used is None
    assert meta.osm_tags_excluded is None
    assert meta.overpass_query is None


@pytest.mark.unit
def test_processing_metadata_serialization():
    """Geocoding fields should serialize to dict/JSON correctly."""
    meta = ProcessingMetadata(
        operation="overpass_query",
        crs_used="EPSG:4326",
        crs_name="WGS 84",
        auto_selected=True,
        query_intent="restaurants",
        osm_tags_used=["amenity=restaurant"],
    )
    d = meta.model_dump()
    assert d["query_intent"] == "restaurants"
    assert d["osm_tags_used"] == ["amenity=restaurant"]
    assert d["query_location"] is None


@pytest.mark.unit
def test_processing_metadata_existing_crs_fields_unchanged():
    """Existing CRS fields should remain fully functional."""
    meta = ProcessingMetadata(
        operation="buffer",
        crs_used="EPSG:32633",
        crs_name="WGS 84 / UTM zone 33N",
        auto_selected=True,
        selection_reason="Local extent - UTM zone 33N",
        origin_layers=["layer_a", "layer_b"],
    )
    assert meta.operation == "buffer"
    assert meta.crs_used == "EPSG:32633"
    assert meta.crs_name == "WGS 84 / UTM zone 33N"
    assert meta.auto_selected is True
    assert meta.selection_reason == "Local extent - UTM zone 33N"
    assert meta.origin_layers == ["layer_a", "layer_b"]
    # Geocoding fields absent
    assert meta.query_intent is None


@pytest.mark.unit
def test_processing_metadata_osm_tags_excluded_structure():
    """osm_tags_excluded should be a list of dicts with 'tag' and 'reason' keys."""
    excluded = [
        {"tag": "landuse=residential", "reason": "land zoning, not buildings"},
        {"tag": "amenity=residential", "reason": "not a standard OSM tag"},
    ]
    meta = ProcessingMetadata(
        operation="overpass_query",
        crs_used="EPSG:4326",
        crs_name="WGS 84",
        auto_selected=True,
        osm_tags_excluded=excluded,
    )
    assert len(meta.osm_tags_excluded) == 2
    assert meta.osm_tags_excluded[1]["reason"] == "not a standard OSM tag"
    d = meta.model_dump()
    assert d["osm_tags_excluded"][0]["tag"] == "landuse=residential"
