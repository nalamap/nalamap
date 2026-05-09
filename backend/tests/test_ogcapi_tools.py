"""Unit tests for the OGC API layer search tool.

All HTTP calls are mocked via unittest.mock so no network access is needed.
"""

from contextlib import contextmanager
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from models.geodata import DataType
from models.settings_model import (
    ModelSettings,
    OGCAPIBackend,
    SettingsSnapshot,
)
from models.states import GeoDataAgentState
from services.tools.ogcapi_tools import (
    _collection_to_geodata,
    _pick_access_url,
    _search_ogcapi_layers_impl,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MOCK_BACKEND = OGCAPIBackend(
    url="https://ogcapi.example.com/v1",
    name="Test OGC API",
    enabled=True,
)

MOCK_BACKEND_DISABLED = OGCAPIBackend(
    url="https://ogcapi.example.com/v1",
    name="Disabled Backend",
    enabled=False,
)


def _make_collection(
    col_id: str,
    title: str,
    description: str = "",
    bbox: List[float] | None = None,
    links: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    col: Dict[str, Any] = {"id": col_id, "title": title, "description": description}
    if bbox:
        col["extent"] = {"spatial": {"bbox": [bbox]}}
    if links:
        col["links"] = links
    return col


def _make_snapshot(backends: List[OGCAPIBackend]) -> SettingsSnapshot:
    return SettingsSnapshot(
        geoserver_backends=[],
        ogcapi_backends=backends,
        mcp_servers=[],
        model_settings=ModelSettings(
            model_provider="openai",
            model_name="gpt-4",
            max_tokens=1000,
            system_prompt="",
        ),
        tools=[],
    )


def _make_state(snapshot: SettingsSnapshot) -> GeoDataAgentState:
    return GeoDataAgentState(
        messages=[],
        geodata_layers=[],
        options=snapshot,
    )


def _mock_http_response(json_data: Any, status_code: int = 200) -> MagicMock:
    """Build a mock httpx Response."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data
    if status_code >= 400:
        import httpx

        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=mock_resp
        )
    else:
        mock_resp.raise_for_status = MagicMock()
    return mock_resp


@contextmanager
def _patch_client(responses: List[MagicMock]):
    """Context manager that patches _make_client to return a mock httpx.Client.

    ``responses`` is consumed in order — one response per client.get() call.
    """
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.side_effect = responses

    with patch("services.tools.ogcapi_tools._make_client", return_value=mock_client):
        yield mock_client


# ---------------------------------------------------------------------------
# Unit tests: helpers
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_pick_access_url_tiles_link():
    col = _make_collection(
        "rivers",
        "Rivers",
        links=[
            {"rel": "tiles", "href": "https://example.com/tiles"},
            {"rel": "items", "href": "https://example.com/items"},
        ],
    )
    assert _pick_access_url(col, "https://example.com") == "https://example.com/tiles"


@pytest.mark.unit
def test_pick_access_url_items_link_when_no_tiles():
    col = _make_collection(
        "rivers",
        "Rivers",
        links=[{"rel": "items", "href": "https://example.com/items"}],
    )
    assert _pick_access_url(col, "https://example.com") == "https://example.com/items"


@pytest.mark.unit
def test_pick_access_url_fallback_to_constructed():
    col = _make_collection("rivers", "Rivers")
    result = _pick_access_url(col, "https://example.com/v1")
    assert result == "https://example.com/v1/collections/rivers/items"


@pytest.mark.unit
def test_collection_to_geodata_maps_fields():
    col = _make_collection(
        "kba",
        "Key Biodiversity Areas",
        description="Global KBA dataset",
        bbox=[-180.0, -90.0, 180.0, 90.0],
    )
    obj = _collection_to_geodata(col, MOCK_BACKEND)
    assert obj.title == "Key Biodiversity Areas"
    assert obj.description == "Global KBA dataset"
    assert obj.data_type == DataType.LAYER
    assert obj.data_source == "ogcapi"
    assert obj.name == "kba"
    assert obj.data_source_id == "Test OGC API"
    assert obj.data_link is not None
    assert obj.bounding_box is not None
    assert "POLYGON" in obj.bounding_box
    assert obj.properties["collection_id"] == "kba"
    assert obj.properties["backend_name"] == "Test OGC API"


# ---------------------------------------------------------------------------
# Unit tests: tool integration
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_search_returns_matching_collections():
    """Server-side q= search returns 2 collections → 2 GeoDataObjects."""
    collections = [
        _make_collection("rivers", "Rivers Germany", "German river network"),
        _make_collection("streams", "Streams Germany", "Small streams"),
    ]
    resp = _mock_http_response({"collections": collections})

    snapshot = _make_snapshot([MOCK_BACKEND])
    state = _make_state(snapshot)

    with _patch_client([resp]):
        result = _search_ogcapi_layers_impl(
            state=state, tool_call_id="test-call-id", query="rivers", max_results=20
        )

    assert isinstance(result, Command)
    geo_results = result.update["geodata_last_results"]
    assert len(geo_results) == 2
    assert geo_results[0].title == "Rivers Germany"
    assert geo_results[1].title == "Streams Germany"


@pytest.mark.unit
def test_search_no_backends_configured():
    """Empty ogcapi_backends list → ToolMessage with clear error."""
    snapshot = _make_snapshot([])
    state = _make_state(snapshot)

    result = _search_ogcapi_layers_impl(
        state=state, tool_call_id="test-call-id", query="rivers", max_results=20
    )

    assert isinstance(result, ToolMessage)
    assert "No OGC API backends configured" in result.content


@pytest.mark.unit
def test_search_backend_disabled():
    """All backends disabled → ToolMessage with appropriate error."""
    snapshot = _make_snapshot([MOCK_BACKEND_DISABLED])
    state = _make_state(snapshot)

    result = _search_ogcapi_layers_impl(
        state=state, tool_call_id="test-call-id", query="rivers", max_results=20
    )

    assert isinstance(result, ToolMessage)
    assert "disabled" in result.content.lower()


@pytest.mark.unit
def test_search_q_fallback_on_400():
    """HTTP 400 on q= → tool falls back to listing all + client-side filter."""
    bad_resp = _mock_http_response({}, status_code=400)

    all_collections = [
        _make_collection("rivers", "Rivers", "German rivers"),
        _make_collection("airports", "Airports", "International airports"),
    ]
    good_resp = _mock_http_response({"collections": all_collections})

    snapshot = _make_snapshot([MOCK_BACKEND])
    state = _make_state(snapshot)

    with _patch_client([bad_resp, good_resp]):
        result = _search_ogcapi_layers_impl(
            state=state, tool_call_id="test-call-id", query="rivers", max_results=20
        )

    assert isinstance(result, Command)
    geo_results = result.update["geodata_last_results"]
    # Only the "rivers" collection matches the query "rivers"
    assert len(geo_results) == 1
    assert geo_results[0].title == "Rivers"


@pytest.mark.unit
def test_search_ssl_error_handled():
    """SSL error → graceful ToolMessage error, does not raise."""
    import ssl

    snapshot = _make_snapshot([MOCK_BACKEND])
    state = _make_state(snapshot)

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.side_effect = ssl.SSLError("certificate verify failed")

    with patch("services.tools.ogcapi_tools._make_client", return_value=mock_client):
        result = _search_ogcapi_layers_impl(
            state=state, tool_call_id="test-call-id", query="rivers", max_results=20
        )

    assert isinstance(result, ToolMessage)
    assert "Test OGC API" in result.content


@pytest.mark.unit
def test_search_maps_tiles_link():
    """Collection with a tiles link → data_link set to tiles URL."""
    collections = [
        _make_collection(
            "wdpa",
            "WDPA Protected Areas",
            links=[
                {"rel": "tiles", "href": "https://ogcapi.example.com/v1/collections/wdpa/tiles"}
            ],
        )
    ]
    resp = _mock_http_response({"collections": collections})

    snapshot = _make_snapshot([MOCK_BACKEND])
    state = _make_state(snapshot)

    with _patch_client([resp]):
        result = _search_ogcapi_layers_impl(
            state=state, tool_call_id="test-call-id", query="wdpa", max_results=20
        )

    assert isinstance(result, Command)
    geo_results = result.update["geodata_last_results"]
    assert len(geo_results) == 1
    assert geo_results[0].data_link == "https://ogcapi.example.com/v1/collections/wdpa/tiles"


@pytest.mark.unit
def test_search_no_results_returns_tool_message():
    """Server returns empty list → ToolMessage with no-results message."""
    resp = _mock_http_response({"collections": []})

    snapshot = _make_snapshot([MOCK_BACKEND])
    state = _make_state(snapshot)

    with _patch_client([resp, _mock_http_response({"collections": []})]):
        result = _search_ogcapi_layers_impl(
            state=state, tool_call_id="test-call-id", query="xyz_nonexistent", max_results=20
        )

    assert isinstance(result, ToolMessage)
    assert "No collections found" in result.content
