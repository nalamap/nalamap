"""Unit tests for the OGC API layer search tool.

All HTTP calls are mocked via unittest.mock so no network access is needed.
"""

import json
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
    body = json.dumps(json_data).encode()
    mock_resp.headers = {}
    mock_resp.iter_bytes.side_effect = lambda: iter([body])
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

    ``responses`` is consumed in order — one response per client.stream() call.
    """
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    queue = list(responses)

    @contextmanager
    def _stream(*args, **kwargs):
        yield queue.pop(0)

    mock_client.stream.side_effect = _stream

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
    mock_client.stream.side_effect = ssl.SSLError("certificate verify failed")

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
    client.stream.assert_not_called()


@pytest.mark.unit
def test_redirect_to_internal_host_is_blocked():
    redirect = MagicMock()
    redirect.status_code = 302
    redirect.headers = {"location": "http://169.254.169.254/latest/meta-data"}
    state = _make_state(_make_snapshot([MOCK_BACKEND]))
    with _patch_client([redirect]) as client:
        result = _search_ogcapi_layers_impl(state=state, tool_call_id="x", query="a")
    assert isinstance(result, ToolMessage)
    assert client.stream.call_count == 1


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
    assert client.stream.call_args_list[-1].args[1].endswith("?o=1")


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
    assert client.stream.call_count == 2


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
    from urllib.parse import parse_qs, urlsplit

    last_url = client.stream.call_args_list[-1].args[1]
    assert parse_qs(urlsplit(last_url).query)["offset"] == ["1"]


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
    assert client.stream.call_count == 2


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


# ---------------------------------------------------------------------------
# DNS pinning, body caps, server-side paging, max_results, 3D bbox
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_pinned_backend_connects_to_validated_ip_only():
    import httpcore

    from services.tools.ogcapi_tools import _PinnedNetworkBackend

    seen = []

    def fake_connect(self, host, port, **kw):
        seen.append(host)
        return "stream"

    with patch("services.tools.ogcapi_tools._resolve_host", return_value=["93.184.216.34"]):
        with patch.object(httpcore.SyncBackend, "connect_tcp", fake_connect):
            assert _PinnedNetworkBackend().connect_tcp("ogc.example.com", 443) == "stream"
    assert seen == ["93.184.216.34"]  # the validated IP, not the hostname


@pytest.mark.unit
def test_pinned_backend_rejects_rebound_internal_address():
    """A hostname that validated as public earlier but resolves internally at connect."""
    import httpcore

    from services.tools.ogcapi_tools import _PinnedNetworkBackend

    with patch("services.tools.ogcapi_tools._resolve_host", return_value=["169.254.169.254"]):
        with patch.object(httpcore.SyncBackend, "connect_tcp") as inner:
            with pytest.raises(UnsafeURLError):
                _PinnedNetworkBackend().connect_tcp("rebind.example.com", 80)
    inner.assert_not_called()


@pytest.mark.unit
def test_make_client_installs_pinned_backend():
    from services.tools.ogcapi_tools import _make_client, _PinnedNetworkBackend

    with _make_client(False) as client:
        assert isinstance(client._transport._pool._network_backend, _PinnedNetworkBackend)


@pytest.mark.unit
def test_oversized_content_length_rejected():
    big = _mock_http_response({"collections": []})
    big.headers = {"content-length": str(50 * 1024 * 1024)}
    state = _make_state(_make_snapshot([MOCK_BACKEND]))
    with _patch_client([big, big]):
        result = _search_ogcapi_layers_impl(state=state, tool_call_id="x", query="a")
    assert isinstance(result, ToolMessage)
    assert "No collections" in result.content or "Could not reach" in result.content


@pytest.mark.unit
def test_oversized_streamed_body_rejected():
    from services.tools import ogcapi_tools as mod

    resp = _mock_http_response({})
    resp.iter_bytes.side_effect = lambda: iter([b"x" * (mod._MAX_BODY_BYTES + 1)])
    client = MagicMock()

    from contextlib import contextmanager as cm

    @cm
    def _stream(*a, **k):
        yield resp

    client.stream.side_effect = _stream
    with pytest.raises(ValueError):
        mod._safe_get(client, "https://ogcapi.example.com/v1/collections")


@pytest.mark.unit
def test_server_side_search_follows_next_pages():
    q1 = _mock_http_response(
        {
            "collections": [_make_collection("r1", "River 1")],
            "links": [{"rel": "next", "href": "https://ogcapi.example.com/v1/collections?o=1"}],
        }
    )
    q2 = _mock_http_response({"collections": [_make_collection("r2", "River 2")]})
    unfiltered = _mock_http_response(
        {"collections": [_make_collection("r1", "River 1"), _make_collection("x", "Other")]}
    )
    state = _make_state(_make_snapshot([MOCK_BACKEND]))
    # Order: q page 1, unfiltered page 1, q page 2
    with _patch_client([q1, unfiltered, q2]):
        result = _search_ogcapi_layers_impl(state=state, tool_call_id="x", query="river")
    assert [g.name for g in result.update["geodata_last_results"]] == ["r1", "r2"]


@pytest.mark.unit
@pytest.mark.parametrize("value", [-5, 0, 10_000])
def test_max_results_is_clamped(value):
    bad = _mock_http_response({}, status_code=400)
    cols = [_make_collection(f"r{i}", f"River {i}") for i in range(60)]
    page = _mock_http_response({"collections": cols})
    state = _make_state(_make_snapshot([MOCK_BACKEND]))
    with _patch_client([bad, page]):
        result = _search_ogcapi_layers_impl(
            state=state, tool_call_id="x", query="river", max_results=value
        )
    n = len(result.update["geodata_last_results"])
    assert 1 <= n <= 50


@pytest.mark.unit
def test_tool_schema_bounds_max_results():
    from services.tools.ogcapi_tools import search_ogcapi_layers

    props = search_ogcapi_layers.args_schema.model_json_schema()["properties"]["max_results"]
    assert props["minimum"] == 1 and props["maximum"] == 50


@pytest.mark.unit
def test_bbox_3d_uses_upper_xy_indices():
    col = _make_collection("c", "C", bbox=[-10.0, -20.0, 0.0, 30.0, 40.0, 500.0])
    wkt = _collection_to_geodata(col, MOCK_BACKEND).bounding_box
    assert wkt == "POLYGON((30.0 -20.0, 30.0 40.0, -10.0 40.0, -10.0 -20.0, 30.0 -20.0))"


@pytest.mark.unit
def test_bbox_2d_unchanged():
    col = _make_collection("c", "C", bbox=[-10.0, -20.0, 30.0, 40.0])
    wkt = _collection_to_geodata(col, MOCK_BACKEND).bounding_box
    assert wkt == "POLYGON((30.0 -20.0, 30.0 40.0, -10.0 40.0, -10.0 -20.0, 30.0 -20.0))"


@pytest.mark.unit
def test_results_published_to_geodata_results():
    cols = [_make_collection("rivers", "Rivers")]
    resp = _mock_http_response({"collections": cols})
    state = _make_state(_make_snapshot([MOCK_BACKEND]))
    with _patch_client([resp, resp]):
        result = _search_ogcapi_layers_impl(state=state, tool_call_id="x", query="rivers")
    assert result.update["geodata_results"] == result.update["geodata_last_results"]
    assert len(result.update["geodata_results"]) == 1


@pytest.mark.unit
def test_base_url_query_string_preserved():
    from urllib.parse import parse_qs, urlsplit

    backend = OGCAPIBackend(url="https://ogcapi.example.com/v1?api_key=secret", name="K")
    ok = _mock_http_response({"collections": [_make_collection("rivers", "Rivers")]})
    state = _make_state(_make_snapshot([backend]))
    with _patch_client([ok, ok]) as client:
        _search_ogcapi_layers_impl(state=state, tool_call_id="x", query="rivers")
    for call in client.stream.call_args_list:
        parts = urlsplit(call.args[1])
        assert parts.path == "/v1/collections"
        q = parse_qs(parts.query)
        assert q["api_key"] == ["secret"] and "limit" in q


@pytest.mark.unit
def test_constructed_items_url_preserves_base_query():
    col = _make_collection("rivers", "Rivers")
    url = _pick_access_url(col, "https://ogcapi.example.com/v1?api_key=secret")
    assert url.startswith("https://ogcapi.example.com/v1/collections/rivers/items?")
    assert "api_key=secret" in url and "f=json" in url


# ---------------------------------------------------------------------------
# Round 5: error redaction, untrusted links, relative links, extent CRS
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_http_error_does_not_leak_query_credentials():
    backend = OGCAPIBackend(url="https://ogcapi.example.com/v1?api_key=SECRET", name="Keyed")
    bad = _mock_http_response({}, status_code=500)
    # The mock's HTTPStatusError message is "error"; use a realistic httpx message.
    import httpx

    req = httpx.Request("GET", "https://ogcapi.example.com/v1/collections?api_key=SECRET")
    err = httpx.HTTPStatusError(
        "Server error for url " + str(req.url),
        request=req,
        response=httpx.Response(500, request=req),
    )
    bad.raise_for_status.side_effect = err
    state = _make_state(_make_snapshot([backend]))
    with _patch_client([bad, bad]):
        result = _search_ogcapi_layers_impl(state=state, tool_call_id="x", query="a")
    assert isinstance(result, ToolMessage)
    assert "SECRET" not in result.content and "api_key" not in result.content
    assert "Keyed" in result.content and "500" in result.content


@pytest.mark.unit
def test_redact_urls_strips_query_and_userinfo():
    from services.tools.ogcapi_tools import _redact_urls

    out = _redact_urls("fail https://user:pw@h.example.com/v1/c?api_key=S&x=1#f ok")
    assert out == "fail https://h.example.com/v1/c ok"


@pytest.mark.unit
@pytest.mark.parametrize(
    "href",
    [
        "http://192.168.1.1/collections/x/items",
        "http://169.254.169.254/latest",
        "http://127.0.0.1:8000/items",
        "ftp://example.com/items",
        "file:///etc/passwd",
    ],
)
def test_unsafe_catalog_items_link_is_dropped(href):
    col = _make_collection("x", "X", links=[{"rel": "items", "href": href}])
    url = _pick_access_url(col, "https://ogcapi.example.com/v1")
    assert url.startswith("https://ogcapi.example.com/v1/collections/x/items?")


@pytest.mark.unit
def test_safe_absolute_catalog_link_kept_and_unsafe_skipped_for_next():
    col = _make_collection(
        "x",
        "X",
        links=[
            {"rel": "items", "type": "application/geo+json", "href": "http://10.0.0.1/items"},
            {"rel": "items", "href": "https://data.example.org/x/items"},
        ],
    )
    url = _pick_access_url(col, "https://ogcapi.example.com/v1")
    assert url.startswith("https://data.example.org/x/items?")


@pytest.mark.unit
def test_catalog_link_resolving_to_private_dns_is_dropped():
    col = _make_collection("x", "X", links=[{"rel": "items", "href": "https://sneaky.example/i"}])
    with patch("services.tools.ogcapi_tools._resolve_host", return_value=["10.0.0.9"]):
        url = _pick_access_url(col, "https://ogcapi.example.com/v1")
    assert url.startswith("https://ogcapi.example.com/v1/collections/x/items?")


@pytest.mark.unit
def test_relative_link_resolves_under_base_path_and_keeps_key():
    from urllib.parse import parse_qs, urlsplit

    col = _make_collection(
        "roads", "Roads", links=[{"rel": "items", "href": "collections/roads/items"}]
    )
    url = _pick_access_url(col, "https://host.example.com/v1?api_key=abc")
    parts = urlsplit(url)
    assert parts.path == "/v1/collections/roads/items"
    q = parse_qs(parts.query)
    assert q["api_key"] == ["abc"] and q["f"] == ["json"]


@pytest.mark.unit
def test_link_query_overrides_base_query_on_relative_link():
    from urllib.parse import parse_qs, urlsplit

    col = _make_collection("r", "R", links=[{"rel": "items", "href": "items?api_key=own"}])
    url = _pick_access_url(col, "https://host.example.com/v1?api_key=abc")
    assert parse_qs(urlsplit(url).query)["api_key"] == ["own"]


@pytest.mark.unit
def test_bbox_default_and_explicit_crs84_unchanged():
    col = _make_collection("c", "C", bbox=[-10.0, -20.0, 30.0, 40.0])
    col["extent"]["spatial"]["crs"] = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
    assert "POLYGON((30.0 -20.0" in _collection_to_geodata(col, MOCK_BACKEND).bounding_box


@pytest.mark.unit
def test_bbox_projected_crs_is_transformed_to_crs84():
    col = _make_collection("c", "C", bbox=[0.0, 0.0, 111319.49, 111325.14])
    col["extent"]["spatial"]["crs"] = "http://www.opengis.net/def/crs/EPSG/0/3857"
    wkt = _collection_to_geodata(col, MOCK_BACKEND).bounding_box
    coords = [tuple(map(float, p.split())) for p in wkt[len("POLYGON((") : -2].split(", ")]
    xs, ys = [c[0] for c in coords], [c[1] for c in coords]
    assert min(xs) == pytest.approx(0.0, abs=1e-3) and max(xs) == pytest.approx(1.0, abs=1e-3)
    assert min(ys) == pytest.approx(0.0, abs=1e-3) and max(ys) == pytest.approx(1.0, abs=1e-3)


@pytest.mark.unit
def test_bbox_unknown_crs_is_omitted():
    col = _make_collection("c", "C", bbox=[1.0, 2.0, 3.0, 4.0])
    col["extent"]["spatial"]["crs"] = "http://example.com/not-a-crs"
    assert _collection_to_geodata(col, MOCK_BACKEND).bounding_box is None


# ---------------------------------------------------------------------------
# Round 6: cross-origin credentials, summary bounds, pagination credentials
# ---------------------------------------------------------------------------

KEYED = "https://host.example.com/v1?api_key=abc"


@pytest.mark.unit
@pytest.mark.parametrize(
    "href",
    [
        "//cdn.example.org/items",
        "https://cdn.example.org/items",
        "http://host.example.com/items",  # different scheme
        "https://host.example.com:8443/items",  # different port
    ],
)
def test_base_credentials_not_forwarded_cross_origin(href):
    col = _make_collection("x", "X", links=[{"rel": "items", "href": href}])
    url = _pick_access_url(col, KEYED)
    assert "api_key" not in url and "abc" not in url


@pytest.mark.unit
def test_base_credentials_forwarded_same_origin_absolute_and_relative():
    for href in ("https://host.example.com/v1/x/items", "/v1/x/items", "x/items"):
        col = _make_collection("x", "X", links=[{"rel": "items", "href": href}])
        assert "api_key=abc" in _pick_access_url(col, KEYED)


@pytest.mark.unit
def test_summary_truncates_fields_and_caps_total():
    huge = "A" * 5000 + "\nIGNORE PREVIOUS"
    cols = [_make_collection(f"c{i}", f"T{i} " + huge, huge) for i in range(50)]
    resp = _mock_http_response({"collections": cols})
    state = _make_state(_make_snapshot([MOCK_BACKEND]))
    with _patch_client([resp, resp]):
        result = _search_ogcapi_layers_impl(
            state=state, tool_call_id="x", query="t", max_results=50
        )
    text = result.update["messages"][0].content
    assert len(text) <= 9000
    assert "\nIGNORE" not in text  # whitespace collapsed
    assert "more (see result cards)" in text
    assert len(result.update["geodata_results"]) == 50  # cards unaffected


@pytest.mark.unit
def test_next_link_inherits_credentials_same_origin_only():
    from urllib.parse import parse_qs, urlsplit

    backend = OGCAPIBackend(url=KEYED, name="K")
    bad = _mock_http_response({}, status_code=400)
    page1 = _mock_http_response(
        {
            "collections": [_make_collection("a", "Alpha")],
            "links": [{"rel": "next", "href": "https://host.example.com/v1/collections?o=1"}],
        }
    )
    page2 = _mock_http_response(
        {
            "collections": [_make_collection("b", "Beta")],
            "links": [{"rel": "next", "href": "https://cdn.example.org/v1/collections?o=2"}],
        }
    )
    page3 = _mock_http_response({"collections": [_make_collection("c", "Gamma")]})
    state = _make_state(_make_snapshot([backend]))
    with _patch_client([bad, page1, page2, page3]) as client:
        _search_ogcapi_layers_impl(state=state, tool_call_id="x", query="zzz")
    urls = [c.args[1] for c in client.stream.call_args_list]
    assert parse_qs(urlsplit(urls[2]).query)["api_key"] == ["abc"]  # same-origin next
    assert "api_key" not in urls[3]  # cross-origin next
