from typing import List

import pytest

from models.geodata import DataOrigin, DataType, GeoDataObject
from models.settings_model import (
    GeoServerBackend,
    ModelSettings,
    SearchPortal,
    SettingsSnapshot,
    ToolConfig,
)
from models.states import GeoDataAgentState
from services.tools.geoserver.custom_geoserver import (
    get_custom_geoserver_data,
    preload_backend_layers,
)


def _create_tool_call(tool_name: str, args: dict, call_id: str) -> dict:
    """Create a proper ToolCall format for invoking tools with InjectedToolCallId."""
    return {"name": tool_name, "args": args, "id": call_id, "type": "tool_call"}


class _StubBackendFetcher:
    """Helper to monkeypatch fetch_all_service_capabilities returning canned layers."""

    def __init__(self):
        self.calls = []

    def __call__(self, backend: GeoServerBackend, search_term=None):  # signature subset
        self.calls.append(backend.url)
        # generate two layers per backend with backend url embedded so assertions can check
        layers: List[GeoDataObject] = []
        for i in range(2):
            # Assign a bounding box: first backend near origin, second far away
            if "alt.example" in backend.url:
                # Far away bbox (200,10 to 210,20)
                bbox_wkt = "POLYGON((210 10, 210 20, 200 20, 200 10, 210 10))"
            else:
                # Near origin (-5,-5 to 5,5)
                bbox_wkt = "POLYGON((5 -5, 5 5, -5 5, -5 -5, 5 -5))"
            layers.append(
                GeoDataObject(
                    id=f"wms_layer_{i}_{backend.url[-5:]}",
                    data_source_id="geoserver_stub",
                    data_type=DataType.RASTER,
                    data_origin=DataOrigin.TOOL.value,
                    data_source="Stub",
                    data_link=f"{backend.url}wms?layer=layer{i}",
                    name=f"layer_{i}",
                    title=f"Layer {i}",
                    description="",
                    bounding_box=bbox_wkt,
                    layer_type="WMS",
                    properties={"srs": ["EPSG:4326"]},
                )
            )
        return layers, {"WMS": True, "WFS": False, "WCS": False, "WMTS": False}


@pytest.fixture
def settings_snapshot():
    backends = [
        GeoServerBackend(
            url="https://example.com/geoserver/",
            name="Primary",
            description="First",
            enabled=True,
            username=None,
            password=None,
        ),
        GeoServerBackend(
            url="https://alt.example.com/geoserver/",
            name="Secondary",
            description="Second",
            enabled=True,
            username=None,
            password=None,
        ),
    ]
    return SettingsSnapshot(
        search_portals=[SearchPortal(url="https://portal.example.com", enabled=True)],
        geoserver_backends=backends,
        model_settings=ModelSettings(
            model_provider="local",
            model_name="none",
            max_tokens=1,
            system_prompt="",
        ),
        tools=[
            ToolConfig(
                name="get_custom_geoserver_data",
                enabled=True,
                prompt_override="",
            )
        ],
        session_id="backend-filter-session",
    )


def _base_state(snapshot: SettingsSnapshot) -> GeoDataAgentState:
    return {
        "options": snapshot,
        "geodata_layers": [],
        "messages": [],
        "results_title": "",
        "geodata_last_results": [],
        "geodata_results": [],
        "remaining_steps": 0,
    }


def test_backend_name_filter(monkeypatch, settings_snapshot):
    stub = _StubBackendFetcher()
    from services.tools.geoserver import custom_geoserver as cg

    monkeypatch.setattr(
        cg,
        "fetch_all_service_capabilities_with_status",
        stub,
    )
    preload_backend_layers(settings_snapshot.session_id, settings_snapshot.geoserver_backends[0])
    state = _base_state(settings_snapshot)
    tool_call = _create_tool_call(
        "get_custom_geoserver_data",
        {
            "state": state,
            "backend_name": "Primary",
        },
        "test_call",
    )
    result = get_custom_geoserver_data.invoke(tool_call)
    # unwrap Command update
    if hasattr(result, "update"):
        update = result.update
    else:
        update = result
    layers = update.get("geodata_results", [])
    assert len(layers) == 2  # only one backend queried
    assert stub.calls == ["https://example.com/geoserver/"]
    # metadata annotation
    for lyr in layers:
        assert lyr.properties.get("_backend_url") == "https://example.com/geoserver"
        assert lyr.properties.get("_backend_name") == "Primary"
        assert lyr.properties.get("_backend_description") == "First"


def test_backend_url_filter(monkeypatch, settings_snapshot):
    stub = _StubBackendFetcher()
    from services.tools.geoserver import custom_geoserver as cg

    monkeypatch.setattr(
        cg,
        "fetch_all_service_capabilities_with_status",
        stub,
    )
    preload_backend_layers(settings_snapshot.session_id, settings_snapshot.geoserver_backends[1])
    state = _base_state(settings_snapshot)
    tool_call = _create_tool_call(
        "get_custom_geoserver_data",
        {
            "state": state,
            "backend_url": "https://alt.example.com/geoserver/",
        },
        "test_call",
    )
    result = get_custom_geoserver_data.invoke(tool_call)
    if hasattr(result, "update"):
        update = result.update
    else:
        update = result
    layers = update.get("geodata_results", [])
    assert len(layers) == 2
    assert stub.calls == ["https://alt.example.com/geoserver/"]
    for lyr in layers:
        assert lyr.properties.get("_backend_url") == "https://alt.example.com/geoserver"
        assert lyr.properties.get("_backend_name") == "Secondary"
        assert lyr.properties.get("_backend_description") == "Second"


def test_no_filter_queries_all(monkeypatch, settings_snapshot):
    stub = _StubBackendFetcher()
    from services.tools.geoserver import custom_geoserver as cg

    monkeypatch.setattr(
        cg,
        "fetch_all_service_capabilities_with_status",
        stub,
    )
    for backend in settings_snapshot.geoserver_backends:
        preload_backend_layers(settings_snapshot.session_id, backend)
    state = _base_state(settings_snapshot)
    tool_call = _create_tool_call(
        "get_custom_geoserver_data",
        {
            "state": state,
        },
        "test_call",
    )
    result = get_custom_geoserver_data.invoke(tool_call)
    if hasattr(result, "update"):
        update = result.update
    else:
        update = result
    layers = update.get("geodata_results", [])
    assert len(layers) == 4  # two backends * two layers each
    assert set(stub.calls) == {
        "https://example.com/geoserver/",
        "https://alt.example.com/geoserver/",
    }
    # ensure each layer carries metadata
    urls = {layer.properties.get("_backend_url") for layer in layers}
    assert urls == {
        "https://example.com/geoserver",
        "https://alt.example.com/geoserver",
    }


def test_bounding_box_filter_includes_only_intersecting(monkeypatch, settings_snapshot):
    stub = _StubBackendFetcher()
    from services.tools.geoserver import custom_geoserver as cg

    monkeypatch.setattr(
        cg,
        "fetch_all_service_capabilities_with_status",
        stub,
    )
    for backend in settings_snapshot.geoserver_backends:
        preload_backend_layers(settings_snapshot.session_id, backend)
    state = _base_state(settings_snapshot)
    # Bounding box near origin should include only primary backend layers
    tool_call = _create_tool_call(
        "get_custom_geoserver_data",
        {
            "state": state,
            "bounding_box": "-6,-6,6,6",
        },
        "test_call",
    )
    result = get_custom_geoserver_data.invoke(tool_call)
    update = result.update if hasattr(result, "update") else result
    layers = update.get("geodata_results", [])
    assert len(layers) == 2
    for lyr in layers:
        assert lyr.properties.get("_backend_url") == "https://example.com/geoserver"


def test_invalid_bounding_box(monkeypatch, settings_snapshot):
    stub = _StubBackendFetcher()
    from services.tools.geoserver import custom_geoserver as cg

    monkeypatch.setattr(
        cg,
        "fetch_all_service_capabilities_with_status",
        stub,
    )
    for backend in settings_snapshot.geoserver_backends:
        preload_backend_layers(settings_snapshot.session_id, backend)
    state = _base_state(settings_snapshot)
    tool_call = _create_tool_call(
        "get_custom_geoserver_data",
        {
            "state": state,
            "bounding_box": "bad_box",
        },
        "test_call",
    )
    result = get_custom_geoserver_data.invoke(tool_call)
    # Expect ToolMessage with error content
    from langchain_core.messages import ToolMessage

    assert isinstance(result, ToolMessage)
    assert "Invalid bounding_box format" in result.content
