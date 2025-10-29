"""Tests for enable_smart_crs setting in ModelSettings and ProcessingMetadata."""

import pytest
from models.settings_model import ModelSettings
from models.geodata import ProcessingMetadata, GeoDataObject, DataType, DataOrigin


@pytest.mark.unit
def test_model_settings_enable_smart_crs_default_true():
    """Test that enable_smart_crs defaults to True in ModelSettings."""
    settings = ModelSettings(
        model_provider="openai",
        model_name="gpt-4o-mini",
        max_tokens=4000,
    )
    assert settings.enable_smart_crs is True


@pytest.mark.unit
def test_model_settings_enable_smart_crs_can_be_disabled():
    """Test that enable_smart_crs can be set to False."""
    settings = ModelSettings(
        model_provider="openai",
        model_name="gpt-4o-mini",
        max_tokens=4000,
        enable_smart_crs=False,
    )
    assert settings.enable_smart_crs is False


@pytest.mark.unit
def test_model_settings_enable_smart_crs_serialization():
    """Test that enable_smart_crs is properly serialized."""
    settings = ModelSettings(
        model_provider="openai",
        model_name="gpt-4o-mini",
        max_tokens=4000,
        enable_smart_crs=True,
    )
    data = settings.model_dump()
    assert "enable_smart_crs" in data
    assert data["enable_smart_crs"] is True


@pytest.mark.unit
def test_model_settings_enable_smart_crs_from_dict():
    """Test that enable_smart_crs can be loaded from dict."""
    data = {
        "model_provider": "openai",
        "model_name": "gpt-4o-mini",
        "max_tokens": 4000,
        "enable_smart_crs": False,
    }
    settings = ModelSettings(**data)
    assert settings.enable_smart_crs is False


@pytest.mark.unit
def test_processing_metadata_creation():
    """Test that ProcessingMetadata can be created with required fields."""
    metadata = ProcessingMetadata(
        operation="buffer",
        crs_used="EPSG:32633",
        crs_name="WGS 84 / UTM zone 33N",
        projection_property="conformal",
        auto_selected=True,
        selection_reason="Local extent - UTM zone 33N",
        expected_error=0.1,
    )
    assert metadata.operation == "buffer"
    assert metadata.crs_used == "EPSG:32633"
    assert metadata.crs_name == "WGS 84 / UTM zone 33N"
    assert metadata.projection_property == "conformal"
    assert metadata.auto_selected is True
    assert metadata.selection_reason == "Local extent - UTM zone 33N"
    assert metadata.expected_error == 0.1


@pytest.mark.unit
def test_processing_metadata_optional_fields():
    """Test that ProcessingMetadata works with only required fields."""
    metadata = ProcessingMetadata(
        operation="area",
        crs_used="EPSG:3857",
        crs_name="Web Mercator",
        projection_property="compromise",
        auto_selected=False,
    )
    assert metadata.operation == "area"
    assert metadata.selection_reason is None
    assert metadata.expected_error is None


@pytest.mark.unit
def test_geodata_object_with_processing_metadata():
    """Test that GeoDataObject can include ProcessingMetadata."""
    metadata = ProcessingMetadata(
        operation="buffer",
        crs_used="EPSG:32633",
        crs_name="WGS 84 / UTM zone 33N",
        projection_property="conformal",
        auto_selected=True,
        selection_reason="Local extent",
        expected_error=0.1,
    )

    geodata = GeoDataObject(
        id="test_123",
        data_source_id="geoprocess",
        data_type=DataType.GEOJSON,
        data_origin=DataOrigin.TOOL,
        data_source="NaLaMapGeoprocess",
        data_link="http://example.com/test.geojson",
        name="buffered_layer",
        processing_metadata=metadata,
    )

    assert geodata.processing_metadata is not None
    assert geodata.processing_metadata.operation == "buffer"
    assert geodata.processing_metadata.crs_used == "EPSG:32633"
    assert geodata.processing_metadata.auto_selected is True


@pytest.mark.unit
def test_geodata_object_without_processing_metadata():
    """Test that GeoDataObject works without ProcessingMetadata."""
    geodata = GeoDataObject(
        id="test_456",
        data_source_id="upload",
        data_type=DataType.GEOJSON,
        data_origin=DataOrigin.UPLOAD,
        data_source="User Upload",
        data_link="http://example.com/upload.geojson",
        name="uploaded_layer",
    )

    assert geodata.processing_metadata is None


@pytest.mark.unit
def test_processing_metadata_serialization():
    """Test that ProcessingMetadata serializes correctly."""
    metadata = ProcessingMetadata(
        operation="overlay",
        crs_used="EPSG:3031",
        crs_name="Antarctic Polar Stereographic",
        projection_property="conformal",
        auto_selected=True,
        expected_error=2.0,
    )

    data = metadata.model_dump()
    assert "operation" in data
    assert data["operation"] == "overlay"
    assert data["crs_used"] == "EPSG:3031"
    assert data["auto_selected"] is True


@pytest.mark.integration
def test_buffer_with_auto_optimize_includes_metadata():
    """Test that buffer operation with auto_optimize_crs includes metadata."""
    from services.tools.geoprocessing.ops.buffer import op_buffer

    # Create a simple test layer
    layers = [
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [10.0, 50.0]},
                    "properties": {"name": "test_point"},
                }
            ],
        }
    ]

    # Call buffer with auto_optimize_crs and projection_metadata enabled
    result = op_buffer(
        layers,
        radius=1000,
        auto_optimize_crs=True,
        projection_metadata=True,
    )

    # Verify result includes CRS metadata
    assert len(result) > 0
    feature_collection = result[0]
    assert "properties" in feature_collection
    assert "_crs_metadata" in feature_collection["properties"]

    crs_meta = feature_collection["properties"]["_crs_metadata"]
    assert "epsg_code" in crs_meta
    assert "crs_name" in crs_meta
    assert "projection_property" in crs_meta
    assert "auto_selected" in crs_meta
    assert crs_meta["auto_selected"] is True
