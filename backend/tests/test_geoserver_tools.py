import pytest
from unittest.mock import MagicMock, patch

from models.geodata import GeoDataObject, DataType, DataOrigin
from models.settings_model import (
    GeoServerBackend,
    ModelSettings,
    SearchPortal,
    SettingsSnapshot,
    ToolConfig,
)
from models.states import GeoDataAgentState
from services.tools.geoserver.custom_geoserver import (
    fetch_all_service_capabilities,
    get_custom_geoserver_data,
    merge_layers,
    parse_wms_capabilities,
    parse_wfs_capabilities,
    parse_wcs_capabilities,
    parse_wmts_capabilities,
)

# Mock URLs
MOCK_GEOSERVER_URL = "http://mockgeoserver.com/"
MOCK_WMS_URL = "http://mockgeoserver.com/wms"
MOCK_WFS_URL = "http://mockgeoserver.com/wfs"
MOCK_WCS_URL = "http://mockgeoserver.com/wcs"
MOCK_WMTS_URL = "http://mockgeoserver.com/gwc/service/wmts"


@pytest.fixture
def mock_wms_service():
    """Fixture for a mock WMS service."""
    wms = MagicMock()
    wms.provider.contact.organization = "Mock WMS Org"
    layer = MagicMock(
        title="Mock Layer 1",
        abstract="Abstract for layer 1.",
        boundingBoxWGS84=(-10, -10, 10, 10),
        crsOptions=[],
        keywords=[],
    )
    layer.name = "workspace:layer1"  # Set the name attribute directly
    wms.contents = {"workspace:layer1": layer}
    return wms


@pytest.fixture
def mock_wfs_service():
    """Fixture for a mock WFS service."""
    wfs = MagicMock()
    wfs.provider.name = "Mock WFS Org"
    wfs.contents = {
        "workspace:layer1": MagicMock(
            id="workspace:layer1",
            title="Mock Feature 1",
            abstract="Abstract for feature 1.",
            boundingBoxWGS84=(-10, -10, 10, 10),
            crsOptions=[],
            keywords=[],
        )
    }
    return wfs


@pytest.fixture
def mock_wcs_service():
    """Fixture for a mock WCS service."""
    wcs = MagicMock()
    wcs.provider.name = "Mock WCS Org"
    wcs.contents = {
        "workspace:layer1": MagicMock(
            id="workspace:layer1",
            title="Mock Coverage 1",
            abstract="Abstract for coverage 1.",
            boundingBoxWGS84=(-10, -10, 10, 10),
            supportedFormats=[],
        )
    }
    return wcs


@pytest.fixture
def mock_wmts_service():
    """Fixture for a mock WMTS service."""
    wmts = MagicMock()
    wmts.provider.name = "Mock WMTS Org"
    tile_matrix_link = MagicMock()
    tile_matrix_link.template = "http://mock/tile/{TileMatrix}/{TileRow}/{TileCol}"
    wmts.contents = {
        "workspace:layer1": MagicMock(
            id="workspace:layer1",
            title="Mock Tile 1",
            abstract="Abstract for tile 1.",
            boundingBoxWGS84=(-10, -10, 10, 10),
            tilematrixsetlinks={"default": tile_matrix_link},
        )
    }
    return wmts


@pytest.fixture
def mock_settings_snapshot() -> SettingsSnapshot:
    """Fixture for a valid SettingsSnapshot."""
    return SettingsSnapshot(
        search_portals=[SearchPortal(url="http://mockportal.com", enabled=True)],
        geoserver_backends=[
            GeoServerBackend(
                url=MOCK_GEOSERVER_URL, enabled=True, username=None, password=None
            )
        ],
        model_settings=ModelSettings(
            model_provider="mock",
            model_name="mock-model",
            max_tokens=100,
            system_prompt="You are a helpful assistant.",
        ),
        tools=[
            ToolConfig(name="mock_tool", enabled=True, prompt_override="")
        ],
    )


def test_parse_wms_capabilities(mock_wms_service):
    """Test parsing of WMS capabilities."""
    layers = parse_wms_capabilities(mock_wms_service, MOCK_WMS_URL)
    assert "workspace:layer1" in layers
    layer = layers["workspace:layer1"]
    assert layer.layer_type == "WMS"
    assert layer.service_links is not None
    assert "WMS" in layer.service_links


def test_parse_wfs_capabilities(mock_wfs_service):
    """Test parsing of WFS capabilities."""
    layers = parse_wfs_capabilities(mock_wfs_service, MOCK_WFS_URL)
    assert "workspace:layer1" in layers
    layer = layers["workspace:layer1"]
    assert layer.layer_type == "WFS"
    assert layer.service_links is not None
    assert "WFS" in layer.service_links


def test_parse_wcs_capabilities(mock_wcs_service):
    """Test parsing of WCS capabilities."""
    layers = parse_wcs_capabilities(mock_wcs_service, MOCK_WCS_URL)
    assert "workspace:layer1" in layers
    layer = layers["workspace:layer1"]
    assert layer.layer_type == "WCS"
    assert layer.service_links is not None
    assert "WCS" in layer.service_links


def test_parse_wmts_capabilities(mock_wmts_service):
    """Test parsing of WMTS capabilities."""
    layers = parse_wmts_capabilities(mock_wmts_service, MOCK_WMTS_URL)
    assert "workspace:layer1" in layers
    layer = layers["workspace:layer1"]
    assert layer.layer_type == "WMTS"
    assert layer.service_links is not None
    assert "WMTS" in layer.service_links


def test_merge_layers():
    """Test merging of layer dictionaries."""
    base_layer = GeoDataObject(
        id="layer1",
        data_source_id="test_source_1",
        data_link="http://wms",
        name="Layer 1",
        title="Layer 1",
        service_links={"WMS": "http://wms"},
        description="Base",
        data_type=DataType.RASTER,
        data_origin=DataOrigin.TOOL.value,
        data_source="test",
    )
    new_layer = GeoDataObject(
        id="layer1",
        data_source_id="test_source_1",
        data_link="http://wfs",
        name="Layer 1",
        title="Layer 1",
        service_links={"WFS": "http://wfs"},
        description="New",
        data_type=DataType.RASTER,
        data_origin=DataOrigin.TOOL.value,
        data_source="test",
    )
    merged = merge_layers({"layer1": base_layer}, {"layer1": new_layer})
    assert "layer1" in merged
    assert len(merged) == 1
    assert merged["layer1"].service_links is not None
    assert "WMS" in merged["layer1"].service_links
    assert "WFS" in merged["layer1"].service_links
    assert merged["layer1"].description == "Base"  # Description should not be overwritten


@patch("services.tools.geoserver.custom_geoserver.WebMapService")
@patch("services.tools.geoserver.custom_geoserver.WebFeatureService")
@patch("services.tools.geoserver.custom_geoserver.WebCoverageService")
@patch("services.tools.geoserver.custom_geoserver.WebMapTileService")
def test_fetch_all_service_capabilities(
    mock_wmts_constructor, mock_wcs_constructor, mock_wfs_constructor, mock_wms_constructor,
    mock_wms_service, mock_wfs_service, mock_wcs_service, mock_wmts_service
):
    """Test fetching from all services and merging the results."""
    mock_wms_constructor.return_value = mock_wms_service
    mock_wfs_constructor.return_value = mock_wfs_service
    mock_wcs_constructor.return_value = mock_wcs_service
    mock_wmts_constructor.return_value = mock_wmts_service

    backend = GeoServerBackend(
        url=MOCK_GEOSERVER_URL, enabled=True, username="user", password="pw"
    )
    layers = fetch_all_service_capabilities(backend)

    assert len(layers) == 1
    assert "workspace:layer1" in layers
    layer = layers["workspace:layer1"]
    assert layer.service_links is not None
    assert "WMS" in layer.service_links
    assert "WFS" in layer.service_links
    assert "WCS" in layer.service_links
    assert "WMTS" in layer.service_links


@patch("services.tools.geoserver.custom_geoserver.fetch_all_service_capabilities")
def test_get_custom_geoserver_data(mock_fetch, mock_settings_snapshot):
    """Test the main tool entry point."""
    mock_layer = GeoDataObject(
        id="layer1",
        name="Test Layer",
        title="Test Layer",
        data_type=DataType.RASTER,
        data_origin=DataOrigin.TOOL.value,
        data_source="test",
        data_source_id="test_source_1",
        data_link="http://mock.link",
    )
    mock_fetch.return_value = {"layer1": mock_layer}

    initial_state: GeoDataAgentState = {
        "options": mock_settings_snapshot,
        "geodata_layers": [],
        "messages": [],
        "results_title": "",
        "geodata_last_results": [],
        "geodata_results": [],
        "remaining_steps": 0,
    }
    tool_call_id = "test_tool_call"

    result = get_custom_geoserver_data.invoke(
        {"state": initial_state, "tool_call_id": tool_call_id}
    )

    assert "geodata_layers" in result
    layers = result["geodata_layers"]
    assert len(layers) == 1
    assert layers[0].id == "layer1"
    mock_fetch.assert_called_once()


def test_get_custom_geoserver_data_no_backends(mock_settings_snapshot):
    """Test tool behavior when no backends are configured."""
    mock_settings_snapshot.geoserver_backends = []
    initial_state: GeoDataAgentState = {
        "options": mock_settings_snapshot,
        "geodata_layers": [],
        "messages": [],
        "results_title": "",
        "geodata_last_results": [],
        "geodata_results": [],
        "remaining_steps": 0,
    }
    tool_call_id = "test_tool_call"
    result = get_custom_geoserver_data.invoke(
        {"state": initial_state, "tool_call_id": tool_call_id}
    )
    assert "No GeoServer backends configured" in result.content


def test_get_custom_geoserver_data_no_enabled_backends(mock_settings_snapshot):
    """Test tool behavior when all backends are disabled."""
    mock_settings_snapshot.geoserver_backends[0].enabled = False
    initial_state: GeoDataAgentState = {
        "options": mock_settings_snapshot,
        "geodata_layers": [],
        "messages": [],
        "results_title": "",
        "geodata_last_results": [],
        "geodata_results": [],
        "remaining_steps": 0,
    }
    tool_call_id = "test_tool_call"
    result = get_custom_geoserver_data.invoke(
        {"state": initial_state, "tool_call_id": tool_call_id}
    )
    assert "All configured GeoServer backends are disabled" in result.content
