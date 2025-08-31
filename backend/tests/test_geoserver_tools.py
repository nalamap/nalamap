import pytest
from unittest.mock import MagicMock, patch

from langchain_core.messages import ToolMessage

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
    _get_custom_geoserver_data,
    fetch_all_service_capabilities,
    parse_wcs_capabilities,
    parse_wfs_capabilities,
    parse_wms_capabilities,
    parse_wmts_capabilities,
)
from langgraph.types import Command

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
    layer1 = MagicMock(
        title="Mock Layer 1",
        abstract="Abstract for layer 1.",
        boundingBoxWGS84=(-10, -10, 10, 10),
        crsOptions=[],
        keywords=[],
    )
    layer1.name = "workspace:layer1"
    layer2 = MagicMock(
        title="Another Layer",
        abstract="Different abstract.",
        boundingBoxWGS84=(-20, -20, 20, 20),
        crsOptions=[],
        keywords=[],
    )
    layer2.name = "workspace:layer2"
    wms.contents = {"workspace:layer1": layer1, "workspace:layer2": layer2}
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
        tools=[ToolConfig(name="mock_tool", enabled=True, prompt_override="")],
    )


@pytest.fixture
def initial_agent_state(mock_settings_snapshot) -> GeoDataAgentState:
    """Fixture for a valid initial agent state."""
    return {
        "options": mock_settings_snapshot,
        "geodata_layers": [],
        "messages": [],
        "results_title": "",
        "geodata_last_results": [],
        "geodata_results": [],
        "remaining_steps": 0,
    }


def test_parse_wms_capabilities(mock_wms_service):
    """Test parsing of WMS capabilities."""
    layers = parse_wms_capabilities(mock_wms_service, MOCK_WMS_URL)
    assert len(layers) == 2
    assert layers[0].layer_type == "WMS"
    assert layers[0].id == "wms_workspace:layer1"


def test_parse_wms_capabilities_with_search(mock_wms_service):
    """Test parsing of WMS capabilities with a search term."""
    layers = parse_wms_capabilities(mock_wms_service, MOCK_WMS_URL, search_term="Another")
    assert len(layers) == 1
    assert layers[0].title == "Another Layer"


def test_parse_wfs_capabilities(mock_wfs_service):
    """Test parsing of WFS capabilities."""
    layers = parse_wfs_capabilities(mock_wfs_service, MOCK_WFS_URL)
    assert len(layers) == 1
    assert layers[0].layer_type == "WFS"
    assert layers[0].id == "wfs_workspace:layer1"


def test_parse_wcs_capabilities(mock_wcs_service):
    """Test parsing of WCS capabilities."""
    layers = parse_wcs_capabilities(mock_wcs_service, MOCK_WCS_URL)
    assert len(layers) == 1
    assert layers[0].layer_type == "WCS"
    assert layers[0].id == "wcs_workspace:layer1"


def test_parse_wmts_capabilities(mock_wmts_service):
    """Test parsing of WMTS capabilities."""
    layers = parse_wmts_capabilities(mock_wmts_service, MOCK_WMTS_URL)
    assert len(layers) == 1
    assert layers[0].layer_type == "WMTS"
    assert layers[0].id == "wmts_workspace:layer1"


@patch("services.tools.geoserver.custom_geoserver.WebMapService")
@patch("services.tools.geoserver.custom_geoserver.WebFeatureService")
@patch("services.tools.geoserver.custom_geoserver.WebCoverageService")
@patch("services.tools.geoserver.custom_geoserver.WebMapTileService")
def test_fetch_all_service_capabilities(
    mock_wmts_constructor,
    mock_wcs_constructor,
    mock_wfs_constructor,
    mock_wms_constructor,
    mock_wms_service,
    mock_wfs_service,
    mock_wcs_service,
    mock_wmts_service,
):
    """Test fetching from all services and getting a flat list."""
    mock_wms_constructor.return_value = mock_wms_service
    mock_wfs_constructor.return_value = mock_wfs_service
    mock_wcs_constructor.return_value = mock_wcs_service
    mock_wmts_constructor.return_value = mock_wmts_service

    backend = GeoServerBackend(
        url=MOCK_GEOSERVER_URL, enabled=True, username="user", password="pw"
    )
    layers = fetch_all_service_capabilities(backend)

    assert len(layers) == 5  # 2 from WMS, 1 from each of the others
    assert any(layer.id == "wms_workspace:layer1" for layer in layers)
    assert any(layer.id == "wfs_workspace:layer1" for layer in layers)
    assert any(layer.id == "wcs_workspace:layer1" for layer in layers)
    assert any(layer.id == "wmts_workspace:layer1" for layer in layers)


@patch("services.tools.geoserver.custom_geoserver.fetch_all_service_capabilities")
def test_get_custom_geoserver_data(mock_fetch, initial_agent_state):
    """Test the main tool entry point."""
    mock_layer = GeoDataObject(
        id="wms_layer1",
        name="Test Layer",
        title="Test Layer",
        data_type=DataType.RASTER,
        data_origin=DataOrigin.TOOL.value,
        data_source="test",
        data_source_id="test_source_1",
        data_link="http://mock.link",
    )
    mock_fetch.return_value = [mock_layer]
    tool_call_id = "test_tool_call"

    result = _get_custom_geoserver_data(state=initial_agent_state, tool_call_id=tool_call_id)

    assert not isinstance(result, ToolMessage)
    # support tools returning a Command(update=...) or a plain dict
    if isinstance(result, Command):
        result_dict = result.update
    else:
        result_dict = result

    assert "geodata_layers" in result_dict
    layers = result_dict["geodata_layers"]
    assert len(layers) == 1
    assert layers[0].id == "wms_layer1"
    mock_fetch.assert_called_once_with(
        initial_agent_state["options"].geoserver_backends[0], search_term=None
    )


@patch("services.tools.geoserver.custom_geoserver.fetch_all_service_capabilities")
def test_get_custom_geoserver_data_with_params(mock_fetch, initial_agent_state):
    """Test the tool with search and max_results parameters."""
    mock_layers = [
        GeoDataObject(
            id=f"wms_layer{i}",
            name=f"Test Layer {i}",
            title=f"Test Layer {i}",
            data_type=DataType.RASTER,
            data_origin=DataOrigin.TOOL.value,
            data_source="test",
            data_source_id=f"test_source_{i}",
            data_link="http://mock.link",
        )
        for i in range(5)
    ]
    mock_fetch.return_value = mock_layers
    tool_call_id = "test_tool_call"

    # The tool itself handles the max_results logic, so the mock can return all.
    result = _get_custom_geoserver_data(
        state=initial_agent_state,
        tool_call_id=tool_call_id,
        search_term="Test",
        max_results=3,
    )

    assert not isinstance(result, ToolMessage)
    # support tools returning a Command(update=...) or a plain dict
    if isinstance(result, Command):
        result_dict = result.update
    else:
        result_dict = result

    assert "geodata_layers" in result_dict
    layers = result_dict["geodata_layers"]
    assert len(layers) == 3
    mock_fetch.assert_called_once_with(
        initial_agent_state["options"].geoserver_backends[0], search_term="Test"
    )


def test_get_custom_geoserver_data_no_backends(initial_agent_state):
    """Test tool behavior when no backends are configured."""
    initial_agent_state["options"].geoserver_backends = []
    tool_call_id = "test_tool_call"

    result = _get_custom_geoserver_data(state=initial_agent_state, tool_call_id=tool_call_id)

    assert isinstance(result, ToolMessage)
    assert "No GeoServer backends configured" in result.content


def test_get_custom_geoserver_data_no_enabled_backends(initial_agent_state):
    """Test tool behavior when all backends are disabled."""
    initial_agent_state["options"].geoserver_backends[0].enabled = False
    tool_call_id = "test_tool_call"

    result = _get_custom_geoserver_data(state=initial_agent_state, tool_call_id=tool_call_id)

    assert isinstance(result, ToolMessage)
    assert "All configured GeoServer backends are disabled" in result.content
