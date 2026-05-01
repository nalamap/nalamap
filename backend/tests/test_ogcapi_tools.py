"""
Unit tests for services/tools/ogcapi_tools.py.

All HTTP calls are mocked – no network access required.
Run with:
    poetry run python -m pytest tests/test_ogcapi_tools.py -m unit -v
"""

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from langchain_core.messages import HumanMessage, ToolMessage

from models.geodata import GeoDataObject
from models.settings_model import ModelSettings, OGCAPIBackend, SettingsSnapshot
from models.states import GeoDataAgentState
from services.tools.ogcapi_tools import (
    _collection_to_geodata,
    _extract_access_url,
    _extract_bbox,
    _fetch_collections,
    _search_ogcapi_layers,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MOCK_MODEL_SETTINGS = ModelSettings(
    model_provider="openai",
    model_name="gpt-4o",
    max_tokens=1024,
)

_BACKEND_URL = "https://ogcapi.example.com/v1"


def _make_backend(enabled: bool = True, allow_insecure: bool = False) -> OGCAPIBackend:
    return OGCAPIBackend(
        url=_BACKEND_URL,
        name="Test OGC API",
        enabled=enabled,
        allow_insecure=allow_insecure,
    )


def _make_snapshot(backends: List[OGCAPIBackend]) -> SettingsSnapshot:
    return SettingsSnapshot(
        geoserver_backends=[],
        ogcapi_backends=backends,
        model_settings=_MOCK_MODEL_SETTINGS,
        tools=[],
    )


def _make_state(snapshot: SettingsSnapshot | None = None) -> GeoDataAgentState:
    state: GeoDataAgentState = GeoDataAgentState()
    state["messages"] = [HumanMessage("Find rivers")]
    state["geodata_last_results"] = []
    state["geodata_results"] = []
    state["geodata_layers"] = []
    state["results_title"] = ""
    state["options"] = snapshot
    state["execution_plan"] = None
    state["remaining_steps"] = 5
    return state


def _make_collection(col_id: str, title: str, description: str = "") -> Dict[str, Any]:
    return {
        "id": col_id,
        "title": title,
        "description": description,
        "links": [
            {"rel": "self", "href": f"{_BACKEND_URL}/collections/{col_id}"},
            {"rel": "items", "href": f"{_BACKEND_URL}/collections/{col_id}/items"},
        ],
        "extent": {
            "spatial": {"bbox": [[5.0, 47.0, 15.0, 55.0]]},
        },
    }


def _mock_httpx_response(status_code: int, body: Dict[str, Any]) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        import httpx

        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    return resp


# ---------------------------------------------------------------------------
# _extract_access_url
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_extract_access_url_prefers_items_link():
    col = _make_collection("rivers", "Rivers")
    url = _extract_access_url(col, _BACKEND_URL)
    assert url == f"{_BACKEND_URL}/collections/rivers/items"


@pytest.mark.unit
def test_extract_access_url_falls_back_to_tiles():
    col = {
        "id": "dem",
        "title": "DEM",
        "links": [{"rel": "tiles", "href": f"{_BACKEND_URL}/collections/dem/tiles"}],
    }
    url = _extract_access_url(col, _BACKEND_URL)
    assert url == f"{_BACKEND_URL}/collections/dem/tiles"


@pytest.mark.unit
def test_extract_access_url_normalizes_relative_href():
    col = {
        "id": "roads",
        "title": "Roads",
        "links": [{"rel": "items", "href": "collections/roads/items"}],
    }
    url = _extract_access_url(col, _BACKEND_URL)
    assert url == f"{_BACKEND_URL}/collections/roads/items"


@pytest.mark.unit
def test_extract_access_url_constructs_fallback_when_no_links():
    col = {"id": "roads", "title": "Roads", "links": []}
    url = _extract_access_url(col, _BACKEND_URL)
    assert "roads" in url
    assert "items" in url


# ---------------------------------------------------------------------------
# _extract_bbox
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_extract_bbox_returns_wkt():
    col = {"extent": {"spatial": {"bbox": [[5.0, 47.0, 15.0, 55.0]]}}}
    bbox = _extract_bbox(col)
    assert bbox is not None
    assert "POLYGON" in bbox
    assert "5.0" in bbox and "55.0" in bbox


@pytest.mark.unit
def test_extract_bbox_returns_none_when_missing():
    assert _extract_bbox({}) is None
    assert _extract_bbox({"extent": {}}) is None


# ---------------------------------------------------------------------------
# _collection_to_geodata
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_collection_to_geodata_maps_fields():
    col = _make_collection("rivers", "Rivers of Germany", "Major rivers")
    backend = _make_backend()
    obj = _collection_to_geodata(col, backend)

    assert isinstance(obj, GeoDataObject)
    assert obj.title == "Rivers of Germany"
    assert obj.description == "Major rivers"
    assert obj.data_source == "ogcapi"
    assert obj.data_origin == "tool"
    assert "rivers/items" in obj.data_link
    assert obj.bounding_box is not None


@pytest.mark.unit
def test_collection_to_geodata_maps_coverage_to_raster():
    col = {
        "id": "dem",
        "title": "Digital Elevation Model",
        "datasetType": "coverage",
        "links": [{"rel": "tiles", "href": f"{_BACKEND_URL}/collections/dem/tiles"}],
    }
    backend = _make_backend()
    obj = _collection_to_geodata(col, backend)
    assert obj.data_type == "Raster"


# ---------------------------------------------------------------------------
# _fetch_collections  (server-side q= supported)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_fetch_collections_uses_q_param():
    """Server returns matching collections for q= query."""
    rivers_col = _make_collection("rivers", "Rivers")
    response_body = {"collections": [rivers_col]}

    async_ctx = AsyncMock()
    async_ctx.__aenter__ = AsyncMock(return_value=async_ctx)
    async_ctx.__aexit__ = AsyncMock(return_value=False)
    async_ctx.get = AsyncMock(return_value=_mock_httpx_response(200, response_body))

    with patch("services.tools.ogcapi_tools._build_http_client", return_value=async_ctx):
        import asyncio

        result = asyncio.run(
            _fetch_collections(
                base_url=_BACKEND_URL,
                query="rivers",
                max_results=10,
                allow_insecure=False,
            )
        )

    assert len(result) == 1
    assert result[0]["id"] == "rivers"


@pytest.mark.unit
def test_fetch_collections_fallback_on_400():
    """Server responds 400 to q= → tool falls back to listing all and filters client-side."""
    roads_col = _make_collection("roads", "Roads Network", "Highway data")
    rivers_col = _make_collection("rivers", "Rivers", "Hydrology")
    all_collections_body = {"collections": [roads_col, rivers_col]}

    async_ctx = AsyncMock()
    async_ctx.__aenter__ = AsyncMock(return_value=async_ctx)
    async_ctx.__aexit__ = AsyncMock(return_value=False)

    # First call (q=) → 400; second call (fallback list) → 200
    async_ctx.get = AsyncMock(
        side_effect=[
            _mock_httpx_response(400, {}),
            _mock_httpx_response(200, all_collections_body),
        ]
    )

    with patch("services.tools.ogcapi_tools._build_http_client", return_value=async_ctx):
        import asyncio

        result = asyncio.run(
            _fetch_collections(
                base_url=_BACKEND_URL,
                query="rivers",
                max_results=10,
                allow_insecure=False,
            )
        )

    # Only the rivers collection should match the client-side filter for "rivers"
    assert len(result) == 1
    assert result[0]["id"] == "rivers"


@pytest.mark.unit
def test_fetch_collections_does_not_fallback_on_5xx():
    async_ctx = AsyncMock()
    async_ctx.__aenter__ = AsyncMock(return_value=async_ctx)
    async_ctx.__aexit__ = AsyncMock(return_value=False)
    async_ctx.get = AsyncMock(return_value=_mock_httpx_response(503, {}))

    with patch("services.tools.ogcapi_tools._build_http_client", return_value=async_ctx):
        import asyncio
        import httpx

        with pytest.raises(httpx.HTTPStatusError):
            asyncio.run(
                _fetch_collections(
                    base_url=_BACKEND_URL,
                    query="rivers",
                    max_results=10,
                    allow_insecure=False,
                )
            )


# ---------------------------------------------------------------------------
# _search_ogcapi_layers (integration of the core function)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_search_returns_matching_collections():
    """Tool returns GeoDataObjects when backend returns matching collections."""
    rivers_col = _make_collection("rivers", "Rivers Germany")
    roads_col = _make_collection("roads", "Roads Germany")
    response_body = {"collections": [rivers_col, roads_col]}

    async_ctx = AsyncMock()
    async_ctx.__aenter__ = AsyncMock(return_value=async_ctx)
    async_ctx.__aexit__ = AsyncMock(return_value=False)
    async_ctx.get = AsyncMock(return_value=_mock_httpx_response(200, response_body))

    backend = _make_backend()
    snapshot = _make_snapshot([backend])
    state = _make_state(snapshot)

    with patch("services.tools.ogcapi_tools._build_http_client", return_value=async_ctx):
        result = _search_ogcapi_layers(
            state=state,
            tool_call_id="test-call-1",
            query="rivers",
        )

    from langgraph.types import Command

    assert isinstance(result, Command)
    layers = result.update["geodata_last_results"]
    assert len(layers) == 2
    assert all(isinstance(layer, GeoDataObject) for layer in layers)
    assert all(layer.data_source == "ogcapi" for layer in layers)


@pytest.mark.unit
def test_search_no_backends_configured():
    """No ogcapi_backends → ToolMessage with clear error."""
    snapshot = _make_snapshot([])
    state = _make_state(snapshot)

    result = _search_ogcapi_layers(state=state, tool_call_id="test-call-2", query="rivers")

    assert isinstance(result, ToolMessage)
    assert "No OGC API backends" in result.content


@pytest.mark.unit
def test_search_backend_disabled():
    """Disabled backend is skipped → ToolMessage with no results."""
    backend = _make_backend(enabled=False)
    snapshot = _make_snapshot([backend])
    state = _make_state(snapshot)

    result = _search_ogcapi_layers(state=state, tool_call_id="test-call-3", query="rivers")

    assert isinstance(result, ToolMessage)
    assert "No OGC API backends" in result.content


@pytest.mark.unit
def test_search_no_match_returns_tool_message():
    """Server returns empty collections list → graceful ToolMessage."""
    async_ctx = AsyncMock()
    async_ctx.__aenter__ = AsyncMock(return_value=async_ctx)
    async_ctx.__aexit__ = AsyncMock(return_value=False)
    async_ctx.get = AsyncMock(return_value=_mock_httpx_response(200, {"collections": []}))

    backend = _make_backend()
    snapshot = _make_snapshot([backend])
    state = _make_state(snapshot)

    with patch("services.tools.ogcapi_tools._build_http_client", return_value=async_ctx):
        result = _search_ogcapi_layers(
            state=state,
            tool_call_id="test-call-4",
            query="zzznomatch",
        )

    assert isinstance(result, ToolMessage)
    assert "No OGC API collections found" in result.content


@pytest.mark.unit
def test_search_ssl_error_handled_gracefully():
    """SSL error on one backend → graceful error message ToolMessage."""
    import ssl

    async_ctx = AsyncMock()
    async_ctx.__aenter__ = AsyncMock(return_value=async_ctx)
    async_ctx.__aexit__ = AsyncMock(return_value=False)
    async_ctx.get = AsyncMock(side_effect=ssl.SSLError("certificate verify failed"))

    backend = _make_backend()
    snapshot = _make_snapshot([backend])
    state = _make_state(snapshot)

    with patch("services.tools.ogcapi_tools._build_http_client", return_value=async_ctx):
        result = _search_ogcapi_layers(
            state=state,
            tool_call_id="test-call-5",
            query="rivers",
        )

    # SSL error on only backend → ToolMessage reports backend failure.
    assert isinstance(result, ToolMessage)
    assert "failed" in result.content.lower()


@pytest.mark.unit
def test_search_maps_tiles_link_for_coverage():
    """Coverage collection whose only data link is 'tiles' → access_url uses tiles href."""
    col = {
        "id": "dem",
        "title": "Digital Elevation Model",
        "datasetType": "coverage",
        "links": [
            {"rel": "tiles", "href": f"{_BACKEND_URL}/collections/dem/tiles"},
        ],
        "extent": {"spatial": {"bbox": [[0.0, 0.0, 10.0, 10.0]]}},
    }
    backend = _make_backend()
    obj = _collection_to_geodata(col, backend)
    assert "tiles" in obj.data_link


@pytest.mark.unit
def test_search_deduplicates_by_access_url():
    """When two backends return the same collection, duplicates are removed."""
    col = _make_collection("rivers", "Rivers")
    response_body = {"collections": [col]}

    async_ctx = AsyncMock()
    async_ctx.__aenter__ = AsyncMock(return_value=async_ctx)
    async_ctx.__aexit__ = AsyncMock(return_value=False)
    async_ctx.get = AsyncMock(return_value=_mock_httpx_response(200, response_body))

    backend1 = _make_backend()
    # Second backend with same URL will produce identical access_url → deduplicated
    backend2 = OGCAPIBackend(url=_BACKEND_URL, name="Mirror", enabled=True)
    snapshot = _make_snapshot([backend1, backend2])
    state = _make_state(snapshot)

    with patch("services.tools.ogcapi_tools._build_http_client", return_value=async_ctx):
        result = _search_ogcapi_layers(
            state=state,
            tool_call_id="test-call-6",
            query="rivers",
        )

    from langgraph.types import Command

    assert isinstance(result, Command)
    layers = result.update["geodata_last_results"]
    # Should be 1, not 2, after dedup
    assert len(layers) == 1


@pytest.mark.unit
def test_settings_snapshot_includes_ogcapi_backends():
    """SettingsSnapshot round-trips OGCAPIBackend list through model_validate."""
    raw = {
        "geoserver_backends": [],
        "ogcapi_backends": [{"url": "https://example.com/v1", "name": "Example", "enabled": True}],
        "model_settings": {
            "model_provider": "openai",
            "model_name": "gpt-4o",
            "max_tokens": 512,
        },
        "tools": [],
    }
    snapshot = SettingsSnapshot.model_validate(raw)
    assert len(snapshot.ogcapi_backends) == 1
    assert snapshot.ogcapi_backends[0].name == "Example"


@pytest.mark.unit
def test_ogcapi_backend_defaults():
    """OGCAPIBackend optional fields default correctly."""
    b = OGCAPIBackend(url="https://test.com")
    assert b.enabled is True
    assert b.allow_insecure is False
    assert b.name is None
