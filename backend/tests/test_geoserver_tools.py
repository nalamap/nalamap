from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from models.geodata import DataOrigin, DataType, GeoDataObject
from models.settings_model import (GeoServerBackend, ModelSettings,
                                   SearchPortal, SettingsSnapshot, ToolConfig)
from models.states import GeoDataAgentState
from services.tools.geoserver.custom_geoserver import (
    _get_custom_geoserver_data, fetch_all_service_capabilities,
    parse_wcs_capabilities, parse_wfs_capabilities, parse_wms_capabilities,
    parse_wmts_capabilities, preload_backend_layers)
from services.tools.geoserver.vector_store import reset_vector_store_for_tests

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
            GeoServerBackend(url=MOCK_GEOSERVER_URL, enabled=True, username=None, password=None)
        ],
        model_settings=ModelSettings(
            model_provider="mock",
            model_name="mock-model",
            max_tokens=100,
            system_prompt="You are a helpful assistant.",
        ),
        tools=[ToolConfig(name="mock_tool", enabled=True, prompt_override="")],
        session_id="test-session",
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


@pytest.fixture(autouse=True)
def temp_vector_store(tmp_path, monkeypatch):
    db_path = tmp_path / "geoserver_vectors.db"
    monkeypatch.setenv("NALAMAP_GEOSERVER_VECTOR_DB", str(db_path))
    reset_vector_store_for_tests()
    yield
    reset_vector_store_for_tests()


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


def test_parse_wmts_capabilities(monkeypatch, mock_wmts_service):
    """Test parsing of WMTS capabilities."""
    # Ensure filtering is disabled for this test so layer is included
    monkeypatch.setenv("NALAMAP_FILTER_NON_WEBMERCATOR_WMTS", "false")
    layers = parse_wmts_capabilities(mock_wmts_service, MOCK_WMTS_URL)
    assert len(layers) == 1
    assert layers[0].layer_type == "WMTS"
    assert layers[0].id == "wmts_workspace:layer1"


def test_parse_wmts_capabilities_filtered(monkeypatch, mock_wmts_service):
    """When filtering is enabled and no WebMercator set exists, no layers are returned."""
    monkeypatch.setenv("NALAMAP_FILTER_NON_WEBMERCATOR_WMTS", "true")
    layers = parse_wmts_capabilities(mock_wmts_service, MOCK_WMTS_URL)
    assert len(layers) == 0


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
    monkeypatch,
):
    """Test fetching from all services and getting a flat list."""
    # Disable WMTS filtering for this test so WMTS layer is included
    monkeypatch.setenv("NALAMAP_FILTER_NON_WEBMERCATOR_WMTS", "false")
    mock_wms_constructor.return_value = mock_wms_service
    mock_wfs_constructor.return_value = mock_wfs_service
    mock_wcs_constructor.return_value = mock_wcs_service
    mock_wmts_constructor.return_value = mock_wmts_service

    backend = GeoServerBackend(url=MOCK_GEOSERVER_URL, enabled=True, username="user", password="pw")
    layers = fetch_all_service_capabilities(backend)

    assert len(layers) == 5  # 2 from WMS, 1 from each of the others
    assert any(layer.id == "wms_workspace:layer1" for layer in layers)
    assert any(layer.id == "wfs_workspace:layer1" for layer in layers)
    assert any(layer.id == "wcs_workspace:layer1" for layer in layers)
    assert any(layer.id == "wmts_workspace:layer1" for layer in layers)


@patch("services.tools.geoserver.custom_geoserver.fetch_all_service_capabilities_with_status")
def test_prefetch_and_query_returns_layers(mock_fetch, initial_agent_state):
    """Prefetched layers should be returned by the tool."""
    backend = initial_agent_state["options"].geoserver_backends[0]
    session_id = initial_agent_state["options"].session_id

    layer = GeoDataObject(
        id="wms_layer1",
        name="Rivers",
        title="Major Rivers",
        data_type=DataType.RASTER,
        data_origin=DataOrigin.TOOL.value,
        data_source="test",
        data_source_id="test_source_1",
        data_link="http://mock.link",
    )
    mock_fetch.return_value = ([layer], {"WMS": True, "WFS": False, "WCS": False, "WMTS": False})

    preload_backend_layers(session_id, backend)

    tool_call_id = "prefetch_call"
    result = _get_custom_geoserver_data(state=initial_agent_state, tool_call_id=tool_call_id)
    assert not isinstance(result, ToolMessage)

    result_dict = result.update if isinstance(result, Command) else result
    layers = result_dict.get("geodata_results", [])
    assert len(layers) == 1
    assert layers[0].name == "Rivers"


@patch("services.tools.geoserver.custom_geoserver.fetch_all_service_capabilities_with_status")
def test_prefetch_and_query_with_search(mock_fetch, initial_agent_state):
    backend = initial_agent_state["options"].geoserver_backends[0]
    session_id = initial_agent_state["options"].session_id

    layers = [
        GeoDataObject(
            id="wms_layer1",
            name="Forests",
            title="Forest Coverage",
            data_type=DataType.RASTER,
            data_origin=DataOrigin.TOOL.value,
            data_source="test",
            data_source_id="source_1",
            data_link="http://mock.link/1",
        ),
        GeoDataObject(
            id="wms_layer2",
            name="Rivers",
            title="River Basins",
            data_type=DataType.RASTER,
            data_origin=DataOrigin.TOOL.value,
            data_source="test",
            data_source_id="source_2",
            data_link="http://mock.link/2",
        ),
    ]
    mock_fetch.return_value = (layers, {"WMS": True, "WFS": False, "WCS": False, "WMTS": False})

    preload_backend_layers(session_id, backend)

    tool_call_id = "search_call"
    result = _get_custom_geoserver_data(
        state=initial_agent_state,
        tool_call_id=tool_call_id,
        search_term="river",
        max_results=1,
    )

    assert not isinstance(result, ToolMessage)
    result_dict = result.update if isinstance(result, Command) else result
    layers = result_dict.get("geodata_results", [])
    assert len(layers) == 1
    assert layers[0].id == "wms_layer2"


def test_get_custom_geoserver_data_requires_prefetch(initial_agent_state):
    """Without prefetching the tool should instruct the caller to preload."""
    tool_call_id = "needs_prefetch"
    result = _get_custom_geoserver_data(state=initial_agent_state, tool_call_id=tool_call_id)
    assert isinstance(result, ToolMessage)
    assert "No prefetched GeoServer layers" in result.content


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


def test_get_custom_geoserver_data_missing_session(initial_agent_state):
    initial_agent_state["options"].session_id = None
    tool_call_id = "missing_session"

    result = _get_custom_geoserver_data(state=initial_agent_state, tool_call_id=tool_call_id)

    assert isinstance(result, ToolMessage)
    assert "Missing session identifier" in result.content
