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
    UnsafeURLError,
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


@pytest.fixture(autouse=True)
def _public_dns():
    """Resolve every hostname to a public address (no real DNS in unit tests)."""
    with patch("services.tools.ogcapi_tools._resolve_host", return_value=["93.184.216.34"]):
        yield


# ---------------------------------------------------------------------------
# Unit tests: helpers
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_pick_access_url_ignores_tiles_link_and_uses_items():
    col = _make_collection(
        "rivers",
        "Rivers",
        links=[
            {"rel": "tiles", "href": "https://example.com/tiles"},
            {"rel": "items", "href": "https://example.com/items"},
        ],
    )
    url = _pick_access_url(col, "https://example.com")
    assert url.startswith("https://example.com/items?")
    assert "f=json" in url and "limit=" in url


@pytest.mark.unit
def test_pick_access_url_prefers_geojson_items_link_and_keeps_query():
    col = _make_collection(
        "rivers",
        "Rivers",
        links=[
            {"rel": "items", "type": "text/html", "href": "https://example.com/html"},
            {
                "rel": "items",
                "type": "application/geo+json",
                "href": "https://example.com/items?token=abc&f=html",
            },
        ],
    )
    url = _pick_access_url(col, "https://example.com")
    assert url.startswith("https://example.com/items?")
    assert "token=abc" in url and "f=json" in url and "f=html" not in url


@pytest.mark.unit
def test_pick_access_url_resolves_relative_href():
    col = _make_collection("r", "R", links=[{"rel": "items", "href": "collections/r/items"}])
    url = _pick_access_url(col, "https://example.com/v1")
    assert url.startswith("https://example.com/v1/collections/r/items?")


@pytest.mark.unit
def test_pick_access_url_fallback_to_constructed():
    col = _make_collection("rivers", "Rivers")
    result = _pick_access_url(col, "https://example.com/v1")
    assert result.startswith("https://example.com/v1/collections/rivers/items?")
    assert "f=json" in result


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
    assert obj.layer_type == "WFS"  # renderable GeoJSON feature layer
    assert "f=json" in obj.data_link
    assert obj.data_source == "ogcapi"
    assert obj.name == "kba"
    assert obj.data_source_id.startswith("ogcapi:")
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
    unfiltered = _mock_http_response(
        {"collections": collections + [_make_collection("airports", "Airports")]}
    )

    snapshot = _make_snapshot([MOCK_BACKEND])
    state = _make_state(snapshot)

    with _patch_client([resp, unfiltered]):
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
def test_search_maps_items_link_to_geojson_layer():
    """Tiles + items links → data_link is a GeoJSON items URL and layer_type is set."""
    collections = [
        _make_collection(
            "wdpa",
            "WDPA Protected Areas",
            links=[
                {"rel": "tiles", "href": "https://ogcapi.example.com/v1/collections/wdpa/tiles"},
                {
                    "rel": "items",
                    "type": "application/geo+json",
                    "href": "https://ogcapi.example.com/v1/collections/wdpa/items",
                },
            ],
        ),
        _make_collection("other", "Other"),
    ]
    resp = _mock_http_response({"collections": collections[:1]})
    unfiltered = _mock_http_response({"collections": collections})

    snapshot = _make_snapshot([MOCK_BACKEND])
    state = _make_state(snapshot)

    with _patch_client([resp, unfiltered]):
        result = _search_ogcapi_layers_impl(
            state=state, tool_call_id="test-call-id", query="wdpa", max_results=20
        )

    assert isinstance(result, Command)
    geo_results = result.update["geodata_last_results"]
    assert len(geo_results) == 1
    assert geo_results[0].layer_type == "WFS"
    assert geo_results[0].data_link.startswith(
        "https://ogcapi.example.com/v1/collections/wdpa/items?"
    )
    assert "f=json" in geo_results[0].data_link


@pytest.mark.unit
def test_search_filters_locally_when_backend_ignores_q():
    """HTTP 200 with the normal listing (q ignored) → local predicate still applied."""
    all_collections = [
        _make_collection("rivers", "Rivers", "German rivers"),
        _make_collection("airports", "Airports", "International airports"),
    ]
    ignored = _mock_http_response({"collections": all_collections})
    unfiltered = _mock_http_response({"collections": all_collections})

    snapshot = _make_snapshot([MOCK_BACKEND])
    state = _make_state(snapshot)

    with _patch_client([ignored, unfiltered]):
        result = _search_ogcapi_layers_impl(
            state=state, tool_call_id="test-call-id", query="rivers", max_results=20
        )

    assert isinstance(result, Command)
    geo_results = result.update["geodata_last_results"]
    assert [g.name for g in geo_results] == ["rivers"]


@pytest.mark.unit
def test_search_trusts_server_side_search_when_it_narrows_results():
    """A server-side hit that does not literally contain the query (e.g. fuzzy) is kept."""
    fuzzy = [_make_collection("hydro", "Hydrography", "Streams and waterways")]
    all_collections = fuzzy + [_make_collection("airports", "Airports")]
    resp = _mock_http_response({"collections": fuzzy})
    unfiltered = _mock_http_response({"collections": all_collections})

    snapshot = _make_snapshot([MOCK_BACKEND])
    state = _make_state(snapshot)

    with _patch_client([resp, unfiltered]):
        result = _search_ogcapi_layers_impl(
            state=state, tool_call_id="test-call-id", query="rivers", max_results=20
        )

    assert isinstance(result, Command)
    assert [g.name for g in result.update["geodata_last_results"]] == ["hydro"]


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


# ---------------------------------------------------------------------------
# SSRF protection
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data",
        "http://127.0.0.1:8000",
        "http://localhost/x",
        "http://10.0.0.5/ogc",
        "http://[::1]/x",
        "http://[::ffff:127.0.0.1]/x",
        "http://0.0.0.0/x",
        "file:///etc/passwd",
        "ftp://example.com/x",
    ],
)
def test_validate_outbound_url_blocks_internal(url):
    from services.tools.ogcapi_tools import _validate_outbound_url

    with pytest.raises(UnsafeURLError):
        _validate_outbound_url(url)


@pytest.mark.unit
def test_validate_outbound_url_blocks_hostname_resolving_to_private():
    from services.tools.ogcapi_tools import _validate_outbound_url

    with patch(
        "services.tools.ogcapi_tools._resolve_host", return_value=["93.184.216.34", "10.1.2.3"]
    ):
        with pytest.raises(UnsafeURLError):
            _validate_outbound_url("https://evil.example.com/v1")


@pytest.mark.unit
def test_search_internal_backend_makes_no_request():
    backend = OGCAPIBackend(url="http://169.254.169.254/latest", name="evil")
    state = _make_state(_make_snapshot([backend]))
    with _patch_client([]) as client:
        result = _search_ogcapi_layers_impl(state=state, tool_call_id="x", query="a")
    assert isinstance(result, ToolMessage)
    assert "evil" in result.content
    client.get.assert_not_called()


@pytest.mark.unit
def test_redirect_to_internal_host_is_blocked():
    redirect = MagicMock()
    redirect.status_code = 302
    redirect.headers = {"location": "http://169.254.169.254/latest/meta-data"}
    state = _make_state(_make_snapshot([MOCK_BACKEND]))
    with _patch_client([redirect]) as client:
        result = _search_ogcapi_layers_impl(state=state, tool_call_id="x", query="a")
    assert isinstance(result, ToolMessage)
    assert client.get.call_count == 1


@pytest.mark.unit
def test_safe_redirect_is_followed():
    redirect = MagicMock()
    redirect.status_code = 301
    redirect.headers = {"location": "https://ogcapi2.example.com/v1/collections"}
    ok = _mock_http_response({"collections": [_make_collection("rivers", "Rivers")]})
    state = _make_state(_make_snapshot([MOCK_BACKEND]))
    # q request: redirect -> ok ; unfiltered request: ok
    with _patch_client([redirect, ok, ok]):
        result = _search_ogcapi_layers_impl(state=state, tool_call_id="x", query="rivers")
    assert isinstance(result, Command)


# ---------------------------------------------------------------------------
# Pagination of the client-side fallback
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_fallback_follows_next_links():
    bad = _mock_http_response({}, status_code=400)
    page1 = _mock_http_response(
        {
            "collections": [_make_collection("a", "Alpha")],
            "links": [{"rel": "next", "href": "https://ogcapi.example.com/v1/collections?o=1"}],
        }
    )
    page2 = _mock_http_response({"collections": [_make_collection("rivers", "Rivers")]})
    state = _make_state(_make_snapshot([MOCK_BACKEND]))
    with _patch_client([bad, page1, page2]) as client:
        result = _search_ogcapi_layers_impl(state=state, tool_call_id="x", query="rivers")
    assert isinstance(result, Command)
    assert [g.name for g in result.update["geodata_last_results"]] == ["rivers"]
    assert client.get.call_args_list[-1].args[0].endswith("?o=1")


@pytest.mark.unit
def test_fallback_next_link_to_internal_host_is_blocked():
    bad = _mock_http_response({}, status_code=400)
    page1 = _mock_http_response(
        {
            "collections": [_make_collection("a", "Alpha")],
            "links": [{"rel": "next", "href": "http://169.254.169.254/x"}],
        }
    )
    state = _make_state(_make_snapshot([MOCK_BACKEND]))
    with _patch_client([bad, page1]) as client:
        result = _search_ogcapi_layers_impl(state=state, tool_call_id="x", query="rivers")
    assert isinstance(result, ToolMessage)
    assert client.get.call_count == 2


@pytest.mark.unit
def test_fallback_uses_offset_when_no_next_link():
    bad = _mock_http_response({}, status_code=400)
    page1 = _mock_http_response(
        {"collections": [_make_collection("a", "Alpha")], "numberMatched": 2}
    )
    page2 = _mock_http_response({"collections": [_make_collection("rivers", "Rivers")]})
    state = _make_state(_make_snapshot([MOCK_BACKEND]))
    with _patch_client([bad, page1, page2]) as client:
        result = _search_ogcapi_layers_impl(state=state, tool_call_id="x", query="rivers")
    assert [g.name for g in result.update["geodata_last_results"]] == ["rivers"]
    assert client.get.call_args_list[-1].kwargs["params"]["offset"] == 1


@pytest.mark.unit
def test_fallback_stops_once_max_results_reached():
    bad = _mock_http_response({}, status_code=400)
    page1 = _mock_http_response(
        {
            "collections": [_make_collection("r1", "River 1"), _make_collection("r2", "River 2")],
            "links": [{"rel": "next", "href": "https://ogcapi.example.com/v1/collections?o=2"}],
        }
    )
    state = _make_state(_make_snapshot([MOCK_BACKEND]))
    with _patch_client([bad, page1]) as client:
        result = _search_ogcapi_layers_impl(
            state=state, tool_call_id="x", query="river", max_results=2
        )
    assert len(result.update["geodata_last_results"]) == 2
    assert client.get.call_count == 2


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_same_name_same_collection_different_endpoints_have_distinct_identity():
    a = OGCAPIBackend(url="https://a.example.com/v1", name="Shared")
    b = OGCAPIBackend(url="https://b.example.com/v1", name="Shared")
    col = _make_collection("rivers", "Rivers")
    oa, ob = _collection_to_geodata(col, a), _collection_to_geodata(col, b)
    assert oa.id != ob.id
    assert oa.data_source_id != ob.data_source_id


@pytest.mark.unit
def test_identity_stable_across_url_normalization_and_rename():
    a = OGCAPIBackend(url="https://A.example.com/v1/", name="One")
    b = OGCAPIBackend(url="https://a.example.com/v1", name="Two")
    col = _make_collection("rivers", "Rivers")
    oa, ob = _collection_to_geodata(col, a), _collection_to_geodata(col, b)
    assert (oa.id, oa.data_source_id) == (ob.id, ob.data_source_id)
