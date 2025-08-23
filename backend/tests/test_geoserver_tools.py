import pytest
from unittest.mock import MagicMock, patch

from models.geodata import GeoDataObject, DataType, DataOrigin
from models.settings_model import GeoServerBackend, SettingsSnapshot, ModelSettings
from models.states import GeoDataAgentState
from services.tools.geoserver.custom_geoserver import (
    fetch_geoserver_capabilities,
    get_custom_geoserver_data,
    parse_wms_capabilities,
)

# Mock data for a WMS capabilities response
MOCK_WMS_URL = "http://mockgeoserver.com/wms"


@pytest.fixture
def mock_wms_service():
    """Fixture to create a mock WebMapService object."""
    wms = MagicMock()
    wms.provider.contact.organization = "Mock Organization"
    wms.provider.url = MOCK_WMS_URL
    wms.contents = {
        "layer1": MagicMock(
            name="layer1",
            title="Mock Layer 1",
            abstract="This is the first mock layer.",
            boundingBoxWGS84=(-180, -90, 180, 90),
            styles={},
            crsOptions=[],
            keywords=[],
        ),
        "layer2": MagicMock(
            name="layer2",
            title="Mock Layer 2",
            abstract="This is the second mock layer.",
            boundingBoxWGS84=None,  # Test case with no bounding box
            styles={},
            crsOptions=[],
            keywords=[],
        ),
    }
    return wms


def test_parse_wms_capabilities(mock_wms_service):
    """Test the parsing of WMS capabilities into GeoDataObjects."""
    layers = parse_wms_capabilities(mock_wms_service, MOCK_WMS_URL)

    assert len(layers) == 2
    layer1 = layers[0]
    assert isinstance(layer1, GeoDataObject)
    assert layer1.name == "layer1"
    assert layer1.title == "Mock Layer 1"
    assert layer1.data_type == DataType.RASTER
    assert layer1.data_origin == DataOrigin.TOOL.value
    assert layer1.bounding_box is not None
    assert "POLYGON" in layer1.bounding_box

    layer2 = layers[1]
    assert layer2.name == "layer2"
    assert layer2.bounding_box is None


def test_fetch_geoserver_capabilities_disabled():
    """Test that disabled backends are skipped."""
    backend = GeoServerBackend(
        url=MOCK_WMS_URL, enabled=False, username=None, password=None
    )
    result = fetch_geoserver_capabilities(backend)
    assert result == []


@patch("services.tools.geoserver.custom_geoserver.WebMapService")
def test_fetch_geoserver_capabilities_success(mock_wms_constructor, mock_wms_service):
    """Test successful fetching and parsing of capabilities."""
    mock_wms_constructor.return_value = mock_wms_service

    backend = GeoServerBackend(
        url=MOCK_WMS_URL, enabled=True, username="user", password="password"
    )
    layers = fetch_geoserver_capabilities(backend)

    assert len(layers) == 2
    assert layers[0].name == "layer1"
    mock_wms_constructor.assert_called_once_with(
        backend.url,
        version="1.3.0",
        username=backend.username,
        password=backend.password,
    )


@patch("services.tools.geoserver.custom_geoserver.WebMapService")
def test_fetch_geoserver_capabilities_failure(mock_wms_constructor):
    """Test handling of exceptions during fetching."""
    mock_wms_constructor.side_effect = Exception("Connection failed")

    backend = GeoServerBackend(
        url=MOCK_WMS_URL, enabled=True, username=None, password=None
    )
    result = fetch_geoserver_capabilities(backend)
    assert result == []


def test_get_custom_geoserver_data_no_options():
    """Test tool behavior when no options are in the state."""
    state = {"options": None}
    tool_call_id = "test_id"
    result = get_custom_geoserver_data.invoke(
        {"state": state, "tool_call_id": tool_call_id}
    )
    assert "No GeoServer backends configured" in result.content


def test_get_custom_geoserver_data_empty_backends():
    """Test tool behavior with empty backends list."""
    state = {
        "options": SettingsSnapshot(
            geoserver_backends=[],
            search_portals=[],
            model_settings=ModelSettings(
                model_provider="test",
                model_name="test",
                max_tokens=1,
                system_prompt="",
            ),
            tools=[],
        )
    }
    tool_call_id = "test_id"
    result = get_custom_geoserver_data.invoke(
        {"state": state, "tool_call_id": tool_call_id}
    )
    assert "No GeoServer backends configured" in result.content


@patch("services.tools.geoserver.custom_geoserver.fetch_geoserver_capabilities")
def test_get_custom_geoserver_data_success(mock_fetch):
    """Test the complete tool flow with mocked fetching."""
    # Mock fetch to return a list with one GeoDataObject
    mock_layer = GeoDataObject(
        id="1",
        data_source_id="ds1",
        data_type=DataType.RASTER,
        data_origin=DataOrigin.TOOL.value,
        data_source="test",
        data_link="http://test.com",
        name="test_layer",
    )
    mock_fetch.return_value = [mock_layer]

    backends = [
        GeoServerBackend(url=MOCK_WMS_URL, enabled=True, username=None, password=None),
        GeoServerBackend(
            url="http://another.com", enabled=False, username=None, password=None
        ),  # Should be ignored
    ]
    options = SettingsSnapshot(
        geoserver_backends=backends,
        search_portals=[],
        model_settings=ModelSettings(
            model_provider="test", model_name="test", max_tokens=1, system_prompt=""
        ),
        tools=[],
    )
    initial_layers = [
        GeoDataObject(
            id="0",
            name="initial",
            data_source_id="ds0",
            data_type=DataType.RASTER,
            data_origin=DataOrigin.TOOL.value,
            data_source="test",
            data_link="http://test.com",
        )
    ]
    state = GeoDataAgentState(
        messages=[], options=options, geodata_layers=initial_layers
    )
    tool_call_id = "test_id"

    result = get_custom_geoserver_data.invoke(
        {"state": state, "tool_call_id": tool_call_id}
    )

    assert mock_fetch.call_count == 1
    assert "geodata_layers" in result
    updated_layers = result["geodata_layers"]
    assert len(updated_layers) == 2
    assert updated_layers[0].name == "initial"
    assert updated_layers[1].name == "test_layer"
