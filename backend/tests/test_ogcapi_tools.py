import json

import pytest
from langchain_core.messages import HumanMessage

from models.geodata import GeoDataObject
from services.tools import ogcapi_tools
from services.tools.ogcapi_tools import build_ogcapi_tools


class MockResponse:
    def __init__(self, status_code=200, payload=None, headers=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("No JSON payload")
        return self._payload


def _message_payload(command):
    msg = command.update["messages"][0]
    return json.loads(msg.content)


def test_runtime_request_url_remaps_localhost_in_container(monkeypatch):
    monkeypatch.setattr("services.tools.ogcapi_tools._is_container_runtime", lambda: True)
    monkeypatch.setattr("services.tools.ogcapi_tools.OGCAPI_BASE_URL", "http://ogcapi:8000/v1")

    runtime_url = ogcapi_tools._runtime_request_url("http://localhost:8081/v1")
    assert runtime_url == "http://ogcapi:8000/v1"


def test_runtime_request_url_unchanged_outside_container(monkeypatch):
    monkeypatch.setattr("services.tools.ogcapi_tools._is_container_runtime", lambda: False)
    monkeypatch.setattr("services.tools.ogcapi_tools.OGCAPI_BASE_URL", "http://ogcapi:8000/v1")

    runtime_url = ogcapi_tools._runtime_request_url("http://localhost:8081/v1")
    assert runtime_url == "http://localhost:8081/v1"


def test_layer_aliases_hide_opaque_identifiers():
    layer = {
        "id": "0309c151bad845ca86d90100b7a42e21",
        "name": "points_simple.geojson",
        "data_link": "http://localhost:8081/v1/uploads/files/0309c151bad845ca86d90100b7a42e21_points_simple.geojson",
    }
    aliases = ogcapi_tools._layer_aliases(layer)
    assert "points_simple.geojson" in aliases
    assert "points_simple" in aliases
    assert "0309c151bad845ca86d90100b7a42e21" not in aliases
    assert (
        "0309c151bad845ca86d90100b7a42e21_points_simple.geojson"
        not in aliases
    )


def test_fetch_feature_collection_remaps_backend_stream_in_container(monkeypatch):
    calls = []

    def fake_get(url, timeout=None, headers=None):
        calls.append(url)
        if url.startswith("http://backend:8000/api/stream/"):
            return MockResponse(
                status_code=200,
                payload={"type": "FeatureCollection", "features": []},
            )
        return MockResponse(status_code=404, payload={"detail": "not found"})

    monkeypatch.setattr("services.tools.ogcapi_tools._is_container_runtime", lambda: True)
    monkeypatch.setattr("services.tools.ogcapi_tools.OGCAPI_BASE_URL", "http://ogcapi:8000/v1")
    monkeypatch.setattr("services.tools.ogcapi_tools.requests.get", fake_get)

    payload = ogcapi_tools._fetch_feature_collection(
        "http://localhost:8000/api/stream/7e19ab7d417144da8c87706f677dc8f7_points_simple.geojson"
    )
    assert payload is not None
    assert payload["type"] == "FeatureCollection"
    assert any(url.startswith("http://backend:8000/api/stream/") for url in calls)


def test_fetch_feature_collection_remaps_ogc_upload_candidate_in_container(monkeypatch):
    calls = []

    def fake_get(url, timeout=None, headers=None):
        calls.append(url)
        if url.startswith("http://ogcapi:8000/v1/uploads/files/"):
            return MockResponse(
                status_code=200,
                payload={"type": "FeatureCollection", "features": []},
            )
        return MockResponse(status_code=404, payload={"detail": "not found"})

    monkeypatch.setattr("services.tools.ogcapi_tools._is_container_runtime", lambda: True)
    monkeypatch.setattr("services.tools.ogcapi_tools.OGCAPI_BASE_URL", "http://localhost:8081/v1")
    monkeypatch.setattr("services.tools.ogcapi_tools.requests.get", fake_get)

    payload = ogcapi_tools._fetch_feature_collection(
        "http://localhost:8000/api/stream/7e19ab7d417144da8c87706f677dc8f7_points_simple.geojson"
    )
    assert payload is not None
    assert payload["type"] == "FeatureCollection"
    assert any(url.startswith("http://ogcapi:8000/v1/uploads/files/") for url in calls)


def test_prepare_geospatial_context_caches_manifest(monkeypatch):
    calls = {"count": 0}

    def fake_request(method, url, headers=None, params=None, json=None, timeout=None):
        calls["count"] += 1
        assert method == "GET"
        assert url.endswith("/v1/agent/capabilities")
        return MockResponse(
            status_code=200,
            payload={
                "service": {"apiPrefix": "/v1"},
                "capabilities": {"processes": [{"id": "vector-buffer"}]},
                "hashes": {"manifest": "sha256:test-manifest"},
            },
            headers={"ETag": 'W/"manifest-test"', "x-request-id": "req-1", "x-trace-id": "trace-1"},
        )

    monkeypatch.setattr("services.tools.ogcapi_tools.requests.request", fake_request)

    class Server:
        url = "http://mock-ogc.local/v1"
        name = "mock"
        api_key = None
        headers = None
        description = "mock"

    tools = build_ogcapi_tools([Server()], default_session_id="session-1")
    prepare_tool = tools[0]

    state = {"messages": [], "geodata_results": [], "options": {"session_id": "session-1"}}
    first = prepare_tool.func(state=state, tool_call_id="call-1")
    second = prepare_tool.func(state=state, tool_call_id="call-2")

    first_payload = _message_payload(first)
    second_payload = _message_payload(second)
    assert first_payload["status"] == "ok"
    assert first_payload["process_count"] == 1
    assert second_payload["status"] == "ok"
    # Second call should use in-memory cache, no additional network call
    assert calls["count"] == 1


def test_filter_geodata_returns_filtered_ref_and_ids(monkeypatch):
    def fake_request(method, url, headers=None, params=None, json=None, timeout=None):
        if url.endswith("/v1/agent/capabilities"):
            return MockResponse(
                status_code=200,
                payload={"service": {"apiPrefix": "/v1"}, "capabilities": {"processes": []}},
                headers={"ETag": 'W/"manifest-2"', "x-request-id": "req-cap", "x-trace-id": "trace-cap"},
            )
        if url.endswith("/v1/collections"):
            return MockResponse(
                status_code=200,
                payload={"collections": [{"id": "places", "title": "Places"}]},
                headers={"x-request-id": "req-col", "x-trace-id": "trace-col"},
            )
        if url.endswith("/v1/collections/places/queryables"):
            return MockResponse(
                status_code=200,
                payload={"properties": {"name": {"type": "string"}, "population": {"type": "number"}}},
                headers={"x-request-id": "req-q", "x-trace-id": "trace-q"},
            )
        if url.endswith("/v1/collections/places/items"):
            assert params.get("name") == "Berlin"
            return MockResponse(
                status_code=200,
                payload={
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "id": "place-1",
                            "geometry": {"type": "Point", "coordinates": [13.4, 52.5]},
                            "properties": {"name": "Berlin"},
                        }
                    ],
                    "numberReturned": 1,
                },
                headers={"x-request-id": "req-items", "x-trace-id": "trace-items"},
            )
        raise AssertionError(f"Unexpected request: {method} {url}")

    monkeypatch.setattr("services.tools.ogcapi_tools.requests.request", fake_request)

    class Server:
        url = "http://mock-ogc.local/v1"
        name = "mock"
        api_key = None
        headers = None
        description = "mock"

    tools = build_ogcapi_tools([Server()], default_session_id="session-2")
    filter_tool = tools[1]
    state = {"messages": [], "geodata_results": [], "options": {"session_id": "session-2"}}

    command = filter_tool.func(
        state=state,
        tool_call_id="filter-call",
        collection_id="places",
        attribute_filter={"name": "Berlin"},
        output_mode="ids",
        limit=10,
    )

    payload = _message_payload(command)
    assert payload["status"] == "ok"
    assert payload["collection_id"] == "places"
    assert payload["ids"] == ["place-1"]
    assert payload["filtered_ref"].startswith("tmp:session-2:subset")


def test_process_geodata_sync_with_filtered_ref(monkeypatch):
    def fake_sleep(_seconds):
        return None

    def fake_request(method, url, headers=None, params=None, json=None, timeout=None):
        if url.endswith("/v1/agent/capabilities"):
            return MockResponse(
                status_code=200,
                payload={"service": {"apiPrefix": "/v1"}, "capabilities": {"processes": []}},
                headers={"ETag": 'W/"manifest-3"', "x-request-id": "req-cap", "x-trace-id": "trace-cap"},
            )
        if url.endswith("/v1/collections"):
            return MockResponse(
                status_code=200,
                payload={"collections": [{"id": "places"}]},
                headers={"x-request-id": "req-col", "x-trace-id": "trace-col"},
            )
        if url.endswith("/v1/collections/places/queryables"):
            return MockResponse(
                status_code=200,
                payload={"properties": {"name": {"type": "string"}}},
                headers={"x-request-id": "req-q", "x-trace-id": "trace-q"},
            )
        if url.endswith("/v1/collections/places/items"):
            return MockResponse(
                status_code=200,
                payload={
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "id": "place-1",
                            "geometry": {"type": "Point", "coordinates": [13.4, 52.5]},
                            "properties": {"name": "Berlin"},
                        }
                    ],
                },
                headers={"x-request-id": "req-items", "x-trace-id": "trace-items"},
            )
        if url.endswith("/v1/processes/vector-buffer/validate"):
            assert "inputs" in json
            assert "feature_collection" in json["inputs"]
            return MockResponse(
                status_code=200,
                payload={
                    "valid": True,
                    "dryRun": True,
                    "normalizedInputs": json["inputs"],
                },
                headers={"x-request-id": "req-val", "x-trace-id": "trace-val"},
            )
        if url.endswith("/v1/processes/vector-buffer/jobs"):
            return MockResponse(
                status_code=201,
                payload={"jobID": "job-123", "status": "accepted"},
                headers={"x-request-id": "req-job", "x-trace-id": "trace-job"},
            )
        if url.endswith("/v1/processes/vector-buffer/jobs/job-123"):
            return MockResponse(
                status_code=200,
                payload={"jobID": "job-123", "status": "successful"},
                headers={"x-request-id": "req-status", "x-trace-id": "trace-status"},
            )
        if url.endswith("/v1/processes/vector-buffer/jobs/job-123/results"):
            return MockResponse(
                status_code=200,
                payload={
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "id": "buffer-1",
                            "geometry": {"type": "Polygon", "coordinates": []},
                            "properties": {"name": "buffer"},
                        }
                    ],
                },
                headers={"x-request-id": "req-results", "x-trace-id": "trace-results"},
            )
        raise AssertionError(f"Unexpected request: {method} {url}")

    monkeypatch.setattr("services.tools.ogcapi_tools.requests.request", fake_request)
    monkeypatch.setattr("services.tools.ogcapi_tools.time.sleep", fake_sleep)

    class Server:
        url = "http://mock-ogc.local/v1"
        name = "mock"
        api_key = None
        headers = None
        description = "mock"

    tools = build_ogcapi_tools([Server()], default_session_id="session-3")
    filter_tool = tools[1]
    process_tool = tools[2]

    state = {"messages": [], "geodata_results": [], "options": {"session_id": "session-3"}}

    filter_command = filter_tool.func(
        state=state,
        tool_call_id="filter-call",
        collection_id="places",
        output_mode="feature_ref",
    )
    filter_payload = _message_payload(filter_command)
    filtered_ref = filter_payload["filtered_ref"]

    process_command = process_tool.func(
        state=state,
        tool_call_id="process-call",
        process_id="vector-buffer",
        input_refs=[filtered_ref],
        prefer_async=False,
        result_format="stats_only",
    )
    process_payload = _message_payload(process_command)

    assert process_payload["status"] == "ok"
    assert process_payload["job_id"] == "job-123"
    assert process_payload["result_ref"].startswith("tmp:session-3:job")
    assert (
        process_payload["job_results_url"]
        == "http://mock-ogc.local/v1/processes/vector-buffer/jobs/job-123/results"
    )
    assert "stats" in process_payload

    geodata_results = process_command.update.get("geodata_results")
    assert geodata_results is not None
    assert len(geodata_results) == 1
    assert isinstance(geodata_results[0], GeoDataObject)
    assert geodata_results[0].data_source_id == "ogcapi-process"
    assert (
        geodata_results[0].data_link
        == "http://mock-ogc.local/v1/processes/vector-buffer/jobs/job-123/results"
    )


def test_process_geodata_short_circuits_duplicate_async_calls(monkeypatch):
    calls = {"validate": 0, "jobs": 0}

    def fake_request(method, url, headers=None, params=None, json=None, timeout=None):
        if url.endswith("/v1/agent/capabilities"):
            return MockResponse(
                status_code=200,
                payload={
                    "service": {"apiPrefix": "/v1"},
                    "capabilities": {"processes": [{"id": "vector-buffer"}]},
                },
                headers={"ETag": 'W/"manifest-dup"', "x-request-id": "req-cap", "x-trace-id": "trace-cap"},
            )
        if url.endswith("/v1/collections/points_upload"):
            return MockResponse(
                status_code=200,
                payload={"id": "points_upload"},
                headers={"x-request-id": "req-col", "x-trace-id": "trace-col"},
            )
        if url.endswith("/v1/processes/vector-buffer/validate"):
            calls["validate"] += 1
            return MockResponse(
                status_code=200,
                payload={"valid": True, "dryRun": True, "normalizedInputs": json["inputs"]},
                headers={"x-request-id": "req-val", "x-trace-id": "trace-val"},
            )
        if url.endswith("/v1/processes/vector-buffer/jobs"):
            calls["jobs"] += 1
            return MockResponse(
                status_code=201,
                payload={"jobID": "job-dup-1", "status": "accepted"},
                headers={"x-request-id": "req-job", "x-trace-id": "trace-job"},
            )
        raise AssertionError(f"Unexpected request: {method} {url}")

    monkeypatch.setattr("services.tools.ogcapi_tools.requests.request", fake_request)

    class Server:
        url = "http://mock-ogc.local/v1"
        name = "mock"
        api_key = None
        headers = None
        description = "mock"

    tools = build_ogcapi_tools(
        [Server()],
        default_session_id="session-dup",
        include_prepare=False,
        include_filter=False,
        include_process=True,
    )
    process_tool = tools[0]
    state = {"messages": [], "geodata_results": [], "options": {"session_id": "session-dup"}}

    first = process_tool.func(
        state=state,
        tool_call_id="process-call-1",
        process_id="vector-buffer",
        inputs={"collection_id": "points_upload", "distance": 4000},
        prefer_async=True,
    )
    second = process_tool.func(
        state=state,
        tool_call_id="process-call-2",
        process_id="vector-buffer",
        inputs={"collection_id": "points_upload", "distance": 4000},
        prefer_async=True,
    )

    first_payload = _message_payload(first)
    second_payload = _message_payload(second)

    assert first_payload["status"] == "accepted"
    assert first_payload["job_id"] == "job-dup-1"
    assert first_payload.get("duplicate_call") is None
    first_geodata_results = first.update.get("geodata_results")
    assert first_geodata_results is not None
    assert len(first_geodata_results) == 1
    assert first_geodata_results[0].data_source_id == "ogcapi-process"
    assert (
        first_geodata_results[0].data_link
        == "http://mock-ogc.local/v1/processes/vector-buffer/jobs/job-dup-1/results"
    )

    assert second_payload["status"] == "accepted"
    assert second_payload["job_id"] == "job-dup-1"
    assert second_payload["duplicate_call"] is True
    assert second_payload["replay_count"] == 1
    second_geodata_results = second.update.get("geodata_results")
    assert second_geodata_results is not None
    assert len(second_geodata_results) == 1
    assert (
        second_geodata_results[0].data_link
        == "http://mock-ogc.local/v1/processes/vector-buffer/jobs/job-dup-1/results"
    )
    assert calls["validate"] == 1
    assert calls["jobs"] == 1


def test_process_geodata_resolves_state_layer_ref(monkeypatch):
    def fake_request(method, url, headers=None, params=None, json=None, timeout=None):
        if url.endswith("/v1/agent/capabilities"):
            return MockResponse(
                status_code=200,
                payload={"service": {"apiPrefix": "/v1"}, "capabilities": {"processes": []}},
                headers={"ETag": 'W/"manifest-ref"', "x-request-id": "req-cap", "x-trace-id": "trace-cap"},
            )
        if url.endswith("/v1/collections/points_upload"):
            return MockResponse(
                status_code=200,
                payload={"id": "points_upload"},
                headers={"x-request-id": "req-col", "x-trace-id": "trace-col"},
            )
        if url.endswith("/v1/processes/vector-buffer/validate"):
            assert json["inputs"]["collection_id"] == "points_upload"
            return MockResponse(
                status_code=200,
                payload={"valid": True, "dryRun": True, "normalizedInputs": json["inputs"]},
                headers={"x-request-id": "req-val", "x-trace-id": "trace-val"},
            )
        if url.endswith("/v1/processes/vector-buffer/jobs"):
            return MockResponse(
                status_code=201,
                payload={"jobID": "job-ref-1", "status": "accepted"},
                headers={"x-request-id": "req-job", "x-trace-id": "trace-job"},
            )
        raise AssertionError(f"Unexpected request: {method} {url}")

    monkeypatch.setattr("services.tools.ogcapi_tools.requests.request", fake_request)

    class Server:
        url = "http://mock-ogc.local/v1"
        name = "mock"
        api_key = None
        headers = None
        description = "mock"

    tools = build_ogcapi_tools(
        [Server()],
        default_session_id="session-4",
        include_prepare=False,
        include_filter=False,
        include_process=True,
    )
    process_tool = tools[0]

    state = {
        "messages": [],
        "geodata_results": [],
        "geodata_layers": [
            {
                "id": "layer-1",
                "name": "points_simple.geojson",
                "data_link": "http://ogcapi:8000/v1/uploads/files/example.geojson",
                "properties": {"ogc_collection_id": "points_upload"},
            }
        ],
        "options": {"session_id": "session-4"},
    }

    process_command = process_tool.func(
        state=state,
        tool_call_id="process-call",
        process_id="vector-buffer",
        input_refs=["points_simple.geojson"],
        prefer_async=True,
    )
    process_payload = _message_payload(process_command)

    assert process_payload["status"] == "accepted"
    assert process_payload["job_id"] == "job-ref-1"
    geodata_results = process_command.update.get("geodata_results")
    assert geodata_results is not None
    assert len(geodata_results) == 1
    assert geodata_results[0].data_source_id == "ogcapi-process"
    assert (
        geodata_results[0].data_link
        == "http://mock-ogc.local/v1/processes/vector-buffer/jobs/job-ref-1/results"
    )
    assert geodata_results[0].properties.get("ogc_job_status") == "accepted"


def test_process_geodata_resolves_fuzzy_state_layer_ref(monkeypatch):
    def fake_request(method, url, headers=None, params=None, json=None, timeout=None):
        if url.endswith("/v1/agent/capabilities"):
            return MockResponse(
                status_code=200,
                payload={"service": {"apiPrefix": "/v1"}, "capabilities": {"processes": []}},
                headers={"ETag": 'W/"manifest-ref-fuzzy"', "x-request-id": "req-cap", "x-trace-id": "trace-cap"},
            )
        if url.endswith("/v1/collections/points_upload"):
            return MockResponse(
                status_code=200,
                payload={"id": "points_upload"},
                headers={"x-request-id": "req-col", "x-trace-id": "trace-col"},
            )
        if url.endswith("/v1/processes/vector-buffer/validate"):
            assert json["inputs"]["collection_id"] == "points_upload"
            return MockResponse(
                status_code=200,
                payload={"valid": True, "dryRun": True, "normalizedInputs": json["inputs"]},
                headers={"x-request-id": "req-val", "x-trace-id": "trace-val"},
            )
        if url.endswith("/v1/processes/vector-buffer/jobs"):
            return MockResponse(
                status_code=201,
                payload={"jobID": "job-ref-fuzzy-1", "status": "accepted"},
                headers={"x-request-id": "req-job", "x-trace-id": "trace-job"},
            )
        raise AssertionError(f"Unexpected request: {method} {url}")

    monkeypatch.setattr("services.tools.ogcapi_tools.requests.request", fake_request)

    class Server:
        url = "http://mock-ogc.local/v1"
        name = "mock"
        api_key = None
        headers = None
        description = "mock"

    tools = build_ogcapi_tools(
        [Server()],
        default_session_id="session-4-fuzzy",
        include_prepare=False,
        include_filter=False,
        include_process=True,
    )
    process_tool = tools[0]

    state = {
        "messages": [],
        "geodata_results": [],
        "geodata_layers": [
            {
                "id": "layer-1",
                "name": "points_simple.geojson",
                "data_link": "http://ogcapi:8000/v1/uploads/files/example.geojson",
                "properties": {"ogc_collection_id": "points_upload"},
            }
        ],
        "options": {"session_id": "session-4-fuzzy"},
    }

    process_command = process_tool.func(
        state=state,
        tool_call_id="process-call",
        process_id="vector-buffer",
        input_refs=["points simple"],
        prefer_async=True,
    )
    process_payload = _message_payload(process_command)

    assert process_payload["status"] == "accepted"
    assert process_payload["job_id"] == "job-ref-fuzzy-1"


def test_process_geodata_autobinds_single_state_layer_without_input_refs(monkeypatch):
    def fake_request(method, url, headers=None, params=None, json=None, timeout=None):
        if url.endswith("/v1/agent/capabilities"):
            return MockResponse(
                status_code=200,
                payload={
                    "service": {"apiPrefix": "/v1"},
                    "capabilities": {"processes": [{"id": "vector-buffer"}]},
                },
                headers={"ETag": 'W/"manifest-autobind"', "x-request-id": "req-cap", "x-trace-id": "trace-cap"},
            )
        if url.endswith("/v1/collections/points_upload"):
            return MockResponse(
                status_code=200,
                payload={"id": "points_upload"},
                headers={"x-request-id": "req-col", "x-trace-id": "trace-col"},
            )
        if url.endswith("/v1/processes/vector-buffer/validate"):
            assert json["inputs"]["collection_id"] == "points_upload"
            assert json["inputs"]["distance"] == 5000
            return MockResponse(
                status_code=200,
                payload={"valid": True, "dryRun": True, "normalizedInputs": json["inputs"]},
                headers={"x-request-id": "req-val", "x-trace-id": "trace-val"},
            )
        if url.endswith("/v1/processes/vector-buffer/jobs"):
            return MockResponse(
                status_code=201,
                payload={"jobID": "job-autobind-1", "status": "accepted"},
                headers={"x-request-id": "req-job", "x-trace-id": "trace-job"},
            )
        raise AssertionError(f"Unexpected request: {method} {url}")

    monkeypatch.setattr("services.tools.ogcapi_tools.requests.request", fake_request)

    class Server:
        url = "http://mock-ogc.local/v1"
        name = "mock"
        api_key = None
        headers = None
        description = "mock"

    tools = build_ogcapi_tools(
        [Server()],
        default_session_id="session-4b",
        include_prepare=False,
        include_filter=False,
        include_process=True,
    )
    process_tool = tools[0]

    state = {
        "messages": [],
        "geodata_results": [],
        "geodata_layers": [
            {
                "id": "layer-1",
                "name": "points_simple.geojson",
                "data_link": "http://localhost:8081/v1/collections/points_upload/items",
                "visible": True,
                "properties": {"ogc_collection_id": "points_upload"},
            }
        ],
        "options": {"session_id": "session-4b"},
    }

    process_command = process_tool.func(
        state=state,
        tool_call_id="process-call",
        process_id="vector-buffer",
        inputs={"distance": 5000},
        prefer_async=True,
    )
    process_payload = _message_payload(process_command)

    assert process_payload["status"] == "accepted"
    assert process_payload["job_id"] == "job-autobind-1"


def test_process_geodata_autobinds_from_query_when_multiple_layers(monkeypatch):
    def fake_request(method, url, headers=None, params=None, json=None, timeout=None):
        if url.endswith("/v1/agent/capabilities"):
            return MockResponse(
                status_code=200,
                payload={
                    "service": {"apiPrefix": "/v1"},
                    "capabilities": {"processes": [{"id": "vector-buffer"}]},
                },
                headers={"ETag": 'W/"manifest-query-autobind"', "x-request-id": "req-cap", "x-trace-id": "trace-cap"},
            )
        if url.endswith("/v1/collections/points_upload"):
            return MockResponse(
                status_code=200,
                payload={"id": "points_upload"},
                headers={"x-request-id": "req-col-points", "x-trace-id": "trace-col-points"},
            )
        if url.endswith("/v1/collections/roads_upload"):
            return MockResponse(
                status_code=200,
                payload={"id": "roads_upload"},
                headers={"x-request-id": "req-col-roads", "x-trace-id": "trace-col-roads"},
            )
        if url.endswith("/v1/processes/vector-buffer/validate"):
            assert json["inputs"]["collection_id"] == "points_upload"
            assert json["inputs"]["distance"] == 5000
            return MockResponse(
                status_code=200,
                payload={"valid": True, "dryRun": True, "normalizedInputs": json["inputs"]},
                headers={"x-request-id": "req-val", "x-trace-id": "trace-val"},
            )
        if url.endswith("/v1/processes/vector-buffer/jobs"):
            return MockResponse(
                status_code=201,
                payload={"jobID": "job-query-autobind-1", "status": "accepted"},
                headers={"x-request-id": "req-job", "x-trace-id": "trace-job"},
            )
        raise AssertionError(f"Unexpected request: {method} {url}")

    monkeypatch.setattr("services.tools.ogcapi_tools.requests.request", fake_request)

    class Server:
        url = "http://mock-ogc.local/v1"
        name = "mock"
        api_key = None
        headers = None
        description = "mock"

    tools = build_ogcapi_tools(
        [Server()],
        default_session_id="session-4q",
        include_prepare=False,
        include_filter=False,
        include_process=True,
    )
    process_tool = tools[0]

    state = {
        "messages": [HumanMessage(content="please buffer points simple by 5km")],
        "geodata_results": [],
        "geodata_layers": [
            {
                "id": "layer-1",
                "name": "points_simple.geojson",
                "data_link": "http://localhost:8081/v1/collections/points_upload/items",
                "visible": True,
                "properties": {"ogc_collection_id": "points_upload"},
            },
            {
                "id": "layer-2",
                "name": "roads_major.geojson",
                "data_link": "http://localhost:8081/v1/collections/roads_upload/items",
                "visible": True,
                "properties": {"ogc_collection_id": "roads_upload"},
            },
        ],
        "options": {"session_id": "session-4q"},
    }

    process_command = process_tool.func(
        state=state,
        tool_call_id="process-call",
        process_id="vector-buffer",
        inputs={"distance": 5000},
        prefer_async=True,
    )
    process_payload = _message_payload(process_command)

    assert process_payload["status"] == "accepted"
    assert process_payload["job_id"] == "job-query-autobind-1"


def test_process_geodata_autobinds_from_explicit_layer_refs(monkeypatch):
    def fake_request(method, url, headers=None, params=None, json=None, timeout=None):
        if url.endswith("/v1/agent/capabilities"):
            return MockResponse(
                status_code=200,
                payload={
                    "service": {"apiPrefix": "/v1"},
                    "capabilities": {"processes": [{"id": "vector-buffer"}]},
                },
                headers={"ETag": 'W/"manifest-query-explicit"', "x-request-id": "req-cap", "x-trace-id": "trace-cap"},
            )
        if url.endswith("/v1/collections/points_upload"):
            return MockResponse(
                status_code=200,
                payload={"id": "points_upload"},
                headers={"x-request-id": "req-col-points", "x-trace-id": "trace-col-points"},
            )
        if url.endswith("/v1/collections/roads_upload"):
            return MockResponse(
                status_code=200,
                payload={"id": "roads_upload"},
                headers={"x-request-id": "req-col-roads", "x-trace-id": "trace-col-roads"},
            )
        if url.endswith("/v1/processes/vector-buffer/validate"):
            assert json["inputs"]["collection_id"] == "roads_upload"
            assert json["inputs"]["distance"] == 5000
            return MockResponse(
                status_code=200,
                payload={"valid": True, "dryRun": True, "normalizedInputs": json["inputs"]},
                headers={"x-request-id": "req-val", "x-trace-id": "trace-val"},
            )
        if url.endswith("/v1/processes/vector-buffer/jobs"):
            return MockResponse(
                status_code=201,
                payload={"jobID": "job-query-explicit-1", "status": "accepted"},
                headers={"x-request-id": "req-job", "x-trace-id": "trace-job"},
            )
        raise AssertionError(f"Unexpected request: {method} {url}")

    monkeypatch.setattr("services.tools.ogcapi_tools.requests.request", fake_request)

    class Server:
        url = "http://mock-ogc.local/v1"
        name = "mock"
        api_key = None
        headers = None
        description = "mock"

    tools = build_ogcapi_tools(
        [Server()],
        default_session_id="session-4q2",
        include_prepare=False,
        include_filter=False,
        include_process=True,
    )
    process_tool = tools[0]

    explicit_refs = json.dumps(
        {
            "layer_refs": [
                {"title": "Major Roads", "name": "roads_major.geojson", "id": "layer-2"}
            ]
        }
    )
    state = {
        "messages": [
            HumanMessage(
                content=(
                    "please buffer by 5km\n\n"
                    f"[EXPLICIT_LAYER_REFS_JSON]{explicit_refs}[/EXPLICIT_LAYER_REFS_JSON]"
                )
            )
        ],
        "geodata_results": [],
        "geodata_layers": [
            {
                "id": "layer-1",
                "name": "points_simple.geojson",
                "title": "Points",
                "data_link": "http://localhost:8081/v1/collections/points_upload/items",
                "visible": True,
                "properties": {"ogc_collection_id": "points_upload"},
            },
            {
                "id": "layer-2",
                "name": "roads_major.geojson",
                "title": "Major Roads",
                "data_link": "http://localhost:8081/v1/collections/roads_upload/items",
                "visible": True,
                "properties": {"ogc_collection_id": "roads_upload"},
            },
        ],
        "options": {"session_id": "session-4q2"},
    }

    process_command = process_tool.func(
        state=state,
        tool_call_id="process-call",
        process_id="vector-buffer",
        inputs={"distance": 5000},
        prefer_async=True,
    )
    process_payload = _message_payload(process_command)

    assert process_payload["status"] == "accepted"
    assert process_payload["job_id"] == "job-query-explicit-1"


def test_process_geodata_disables_fuzzy_input_ref_when_explicit_refs_present(monkeypatch):
    def fake_request(method, url, headers=None, params=None, json=None, timeout=None):
        if url.endswith("/v1/agent/capabilities"):
            return MockResponse(
                status_code=200,
                payload={"service": {"apiPrefix": "/v1"}, "capabilities": {"processes": []}},
                headers={"ETag": 'W/"manifest-ref-strict"', "x-request-id": "req-cap", "x-trace-id": "trace-cap"},
            )
        raise AssertionError(f"Unexpected request: {method} {url}")

    monkeypatch.setattr("services.tools.ogcapi_tools.requests.request", fake_request)

    class Server:
        url = "http://mock-ogc.local/v1"
        name = "mock"
        api_key = None
        headers = None
        description = "mock"

    tools = build_ogcapi_tools(
        [Server()],
        default_session_id="session-4s",
        include_prepare=False,
        include_filter=False,
        include_process=True,
    )
    process_tool = tools[0]

    explicit_refs = json.dumps(
        {"layer_refs": [{"title": "Points", "name": "points_simple.geojson", "id": "layer-1"}]}
    )
    state = {
        "messages": [
            HumanMessage(
                content=(
                    "buffer selected points\n\n"
                    f"[EXPLICIT_LAYER_REFS_JSON]{explicit_refs}[/EXPLICIT_LAYER_REFS_JSON]"
                )
            )
        ],
        "geodata_results": [],
        "geodata_layers": [
            {
                "id": "layer-1",
                "name": "points_simple.geojson",
                "title": "Points",
                "data_link": "http://ogcapi:8000/v1/uploads/files/example.geojson",
                "properties": {"ogc_collection_id": "points_upload"},
            }
        ],
        "options": {"session_id": "session-4s"},
    }

    process_command = process_tool.func(
        state=state,
        tool_call_id="process-call",
        process_id="vector-buffer",
        input_refs=["points simple"],
        prefer_async=True,
    )
    process_payload = _message_payload(process_command)

    assert process_payload["status"] == "error"
    assert process_payload["error"]["code"] == "unknown_input_ref"


def test_process_geodata_autobinds_from_state_explicit_layer_refs(monkeypatch):
    def fake_request(method, url, headers=None, params=None, json=None, timeout=None):
        if url.endswith("/v1/agent/capabilities"):
            return MockResponse(
                status_code=200,
                payload={
                    "service": {"apiPrefix": "/v1"},
                    "capabilities": {"processes": [{"id": "vector-buffer"}]},
                },
                headers={"ETag": 'W/"manifest-state-explicit"', "x-request-id": "req-cap", "x-trace-id": "trace-cap"},
            )
        if url.endswith("/v1/collections/roads_upload"):
            return MockResponse(
                status_code=200,
                payload={"id": "roads_upload"},
                headers={"x-request-id": "req-col-roads", "x-trace-id": "trace-col-roads"},
            )
        if url.endswith("/v1/processes/vector-buffer/validate"):
            assert json["inputs"]["collection_id"] == "roads_upload"
            return MockResponse(
                status_code=200,
                payload={"valid": True, "dryRun": True, "normalizedInputs": json["inputs"]},
                headers={"x-request-id": "req-val", "x-trace-id": "trace-val"},
            )
        if url.endswith("/v1/processes/vector-buffer/jobs"):
            return MockResponse(
                status_code=201,
                payload={"jobID": "job-state-explicit-1", "status": "accepted"},
                headers={"x-request-id": "req-job", "x-trace-id": "trace-job"},
            )
        raise AssertionError(f"Unexpected request: {method} {url}")

    monkeypatch.setattr("services.tools.ogcapi_tools.requests.request", fake_request)

    class Server:
        url = "http://mock-ogc.local/v1"
        name = "mock"
        api_key = None
        headers = None
        description = "mock"

    tools = build_ogcapi_tools(
        [Server()],
        default_session_id="session-state-explicit",
        include_prepare=False,
        include_filter=False,
        include_process=True,
    )
    process_tool = tools[0]

    state = {
        "messages": [HumanMessage(content="buffer with 4km")],
        "explicit_layer_refs": ["Major Roads", "roads_major.geojson"],
        "geodata_results": [],
        "geodata_layers": [
            {
                "id": "layer-2",
                "name": "roads_major.geojson",
                "title": "Major Roads",
                "data_link": "http://localhost:8081/v1/collections/roads_upload/items",
                "visible": True,
                "properties": {"ogc_collection_id": "roads_upload"},
            }
        ],
        "options": {"session_id": "session-state-explicit"},
    }

    process_command = process_tool.func(
        state=state,
        tool_call_id="process-call",
        process_id="vector-buffer",
        inputs={"distance": 4000},
        prefer_async=True,
    )
    process_payload = _message_payload(process_command)

    assert process_payload["status"] == "accepted"
    assert process_payload["job_id"] == "job-state-explicit-1"


def test_process_geodata_autobinds_from_explicit_refs_with_prefixed_layer_name(monkeypatch):
    def fake_request(method, url, headers=None, params=None, json=None, timeout=None):
        if url.endswith("/v1/agent/capabilities"):
            return MockResponse(
                status_code=200,
                payload={
                    "service": {"apiPrefix": "/v1"},
                    "capabilities": {"processes": [{"id": "vector-buffer"}]},
                },
                headers={"ETag": 'W/"manifest-prefixed-name"', "x-request-id": "req-cap", "x-trace-id": "trace-cap"},
            )
        if url.endswith("/v1/collections/points_upload"):
            return MockResponse(
                status_code=200,
                payload={"id": "points_upload"},
                headers={"x-request-id": "req-col", "x-trace-id": "trace-col"},
            )
        if url.endswith("/v1/processes/vector-buffer/validate"):
            assert json["inputs"]["collection_id"] == "points_upload"
            return MockResponse(
                status_code=200,
                payload={"valid": True, "dryRun": True, "normalizedInputs": json["inputs"]},
                headers={"x-request-id": "req-val", "x-trace-id": "trace-val"},
            )
        if url.endswith("/v1/processes/vector-buffer/jobs"):
            return MockResponse(
                status_code=201,
                payload={"jobID": "job-prefixed-name-1", "status": "accepted"},
                headers={"x-request-id": "req-job", "x-trace-id": "trace-job"},
            )
        raise AssertionError(f"Unexpected request: {method} {url}")

    monkeypatch.setattr("services.tools.ogcapi_tools.requests.request", fake_request)

    class Server:
        url = "http://mock-ogc.local/v1"
        name = "mock"
        api_key = None
        headers = None
        description = "mock"

    tools = build_ogcapi_tools(
        [Server()],
        default_session_id="session-prefixed-name",
        include_prepare=False,
        include_filter=False,
        include_process=True,
    )
    process_tool = tools[0]

    state = {
        "messages": [HumanMessage(content="buffer with 4km")],
        "explicit_layer_refs": ["points_simple.geojson"],
        "geodata_results": [],
        "geodata_layers": [
            {
                "id": "layer-1",
                "name": "4fc167270a7540a886c10abcd9e95dad_points_simple.geojson",
                "title": "",
                "data_link": "http://localhost:8081/v1/collections/points_upload/items",
                "visible": True,
                "properties": {"ogc_collection_id": "points_upload"},
            }
        ],
        "options": {"session_id": "session-prefixed-name"},
    }

    process_command = process_tool.func(
        state=state,
        tool_call_id="process-call",
        process_id="vector-buffer",
        inputs={"distance": 4000},
        prefer_async=True,
    )
    process_payload = _message_payload(process_command)

    assert process_payload["status"] == "accepted"
    assert process_payload["job_id"] == "job-prefixed-name-1"


def test_process_geodata_returns_error_when_source_input_missing(monkeypatch):
    calls = []

    def fake_request(method, url, headers=None, params=None, json=None, timeout=None):
        calls.append(url)
        if url.endswith("/v1/agent/capabilities"):
            return MockResponse(
                status_code=200,
                payload={
                    "service": {"apiPrefix": "/v1"},
                    "capabilities": {"processes": [{"id": "vector-buffer"}]},
                },
                headers={"ETag": 'W/"manifest-missing-source"', "x-request-id": "req-cap", "x-trace-id": "trace-cap"},
            )
        raise AssertionError(f"Unexpected request: {method} {url}")

    monkeypatch.setattr("services.tools.ogcapi_tools.requests.request", fake_request)

    class Server:
        url = "http://mock-ogc.local/v1"
        name = "mock"
        api_key = None
        headers = None
        description = "mock"

    tools = build_ogcapi_tools(
        [Server()],
        default_session_id="session-4c",
        include_prepare=False,
        include_filter=False,
        include_process=True,
    )
    process_tool = tools[0]
    state = {"messages": [], "geodata_results": [], "options": {"session_id": "session-4c"}}

    process_command = process_tool.func(
        state=state,
        tool_call_id="process-call",
        process_id="vector-buffer",
        inputs={"distance": 5000},
        prefer_async=True,
    )
    process_payload = _message_payload(process_command)

    assert process_payload["status"] == "error"
    assert process_payload["error"]["code"] == "missing_process_source_input"
    assert process_payload["detail"]["required_one_of"] == [
        "collection_id",
        "feature_collection",
        "feature_collection_path",
    ]
    assert len(calls) == 1


def test_process_geodata_rebinds_missing_collection_id_from_state(monkeypatch):
    def fake_request(method, url, headers=None, params=None, json=None, timeout=None):
        if url.endswith("/v1/agent/capabilities"):
            return MockResponse(
                status_code=200,
                payload={
                    "service": {"apiPrefix": "/v1"},
                    "capabilities": {"processes": [{"id": "vector-buffer"}]},
                },
                headers={"ETag": 'W/"manifest-rebind"', "x-request-id": "req-cap", "x-trace-id": "trace-cap"},
            )
        if url.endswith("/v1/collections/missing_collection"):
            return MockResponse(
                status_code=404,
                payload={"detail": "Collection not found"},
                headers={"x-request-id": "req-col-missing", "x-trace-id": "trace-col-missing"},
            )
        if url.endswith("/v1/collections/points_upload"):
            return MockResponse(
                status_code=200,
                payload={"id": "points_upload"},
                headers={"x-request-id": "req-col", "x-trace-id": "trace-col"},
            )
        if url.endswith("/v1/processes/vector-buffer/validate"):
            assert json["inputs"]["collection_id"] == "points_upload"
            assert json["inputs"]["distance"] == 5000
            return MockResponse(
                status_code=200,
                payload={"valid": True, "dryRun": True, "normalizedInputs": json["inputs"]},
                headers={"x-request-id": "req-val", "x-trace-id": "trace-val"},
            )
        if url.endswith("/v1/processes/vector-buffer/jobs"):
            return MockResponse(
                status_code=201,
                payload={"jobID": "job-rebind-1", "status": "accepted"},
                headers={"x-request-id": "req-job", "x-trace-id": "trace-job"},
            )
        raise AssertionError(f"Unexpected request: {method} {url}")

    monkeypatch.setattr("services.tools.ogcapi_tools.requests.request", fake_request)

    class Server:
        url = "http://mock-ogc.local/v1"
        name = "mock"
        api_key = None
        headers = None
        description = "mock"

    tools = build_ogcapi_tools(
        [Server()],
        default_session_id="session-4d",
        include_prepare=False,
        include_filter=False,
        include_process=True,
    )
    process_tool = tools[0]

    state = {
        "messages": [],
        "geodata_results": [],
        "geodata_layers": [
            {
                "id": "layer-1",
                "name": "points_simple.geojson",
                "data_link": "http://localhost:8081/v1/collections/points_upload/items",
                "visible": True,
                "properties": {"ogc_collection_id": "points_upload"},
            }
        ],
        "options": {"session_id": "session-4d"},
    }

    process_command = process_tool.func(
        state=state,
        tool_call_id="process-call",
        process_id="vector-buffer",
        inputs={"distance": 5000, "collection_id": "missing_collection"},
        prefer_async=True,
    )
    process_payload = _message_payload(process_command)

    assert process_payload["status"] == "accepted"
    assert process_payload["job_id"] == "job-rebind-1"


def test_process_geodata_rejects_ambiguous_source_inputs(monkeypatch):
    def fake_request(method, url, headers=None, params=None, json=None, timeout=None):
        if url.endswith("/v1/agent/capabilities"):
            return MockResponse(
                status_code=200,
                payload={
                    "service": {"apiPrefix": "/v1"},
                    "capabilities": {"processes": [{"id": "vector-buffer"}]},
                },
                headers={"ETag": 'W/"manifest-ambiguous"', "x-request-id": "req-cap", "x-trace-id": "trace-cap"},
            )
        raise AssertionError(f"Unexpected request: {method} {url}")

    monkeypatch.setattr("services.tools.ogcapi_tools.requests.request", fake_request)

    class Server:
        url = "http://mock-ogc.local/v1"
        name = "mock"
        api_key = None
        headers = None
        description = "mock"

    tools = build_ogcapi_tools(
        [Server()],
        default_session_id="session-4e",
        include_prepare=False,
        include_filter=False,
        include_process=True,
    )
    process_tool = tools[0]
    state = {"messages": [], "geodata_results": [], "options": {"session_id": "session-4e"}}

    process_command = process_tool.func(
        state=state,
        tool_call_id="process-call",
        process_id="vector-buffer",
        inputs={
            "distance": 5000,
            "collection_id": "points_upload",
            "feature_collection": {"type": "FeatureCollection", "features": []},
        },
        prefer_async=True,
    )
    process_payload = _message_payload(process_command)

    assert process_payload["status"] == "error"
    assert process_payload["error"]["code"] == "ambiguous_source_inputs"
    assert sorted(process_payload["detail"]["provided_keys"]) == ["collection_id", "feature_collection"]


def test_process_geodata_resolves_legacy_process_alias(monkeypatch):
    def fake_request(method, url, headers=None, params=None, json=None, timeout=None):
        if url.endswith("/v1/agent/capabilities"):
            return MockResponse(
                status_code=200,
                payload={
                    "service": {"apiPrefix": "/v1"},
                    "capabilities": {"processes": [{"id": "vector-buffer"}]},
                },
                headers={"ETag": 'W/"manifest-alias"', "x-request-id": "req-cap", "x-trace-id": "trace-cap"},
            )
        if url.endswith("/v1/processes/vector-buffer/validate"):
            return MockResponse(
                status_code=200,
                payload={"valid": True, "dryRun": True, "normalizedInputs": json["inputs"]},
                headers={"x-request-id": "req-val", "x-trace-id": "trace-val"},
            )
        if url.endswith("/v1/processes/vector-buffer/jobs"):
            return MockResponse(
                status_code=201,
                payload={"jobID": "job-alias-1", "status": "accepted"},
                headers={"x-request-id": "req-job", "x-trace-id": "trace-job"},
            )
        raise AssertionError(f"Unexpected request: {method} {url}")

    monkeypatch.setattr("services.tools.ogcapi_tools.requests.request", fake_request)

    class Server:
        url = "http://mock-ogc.local/v1"
        name = "mock"
        api_key = None
        headers = None
        description = "mock"

    tools = build_ogcapi_tools(
        [Server()],
        default_session_id="session-5",
        include_prepare=False,
        include_filter=False,
        include_process=True,
    )
    process_tool = tools[0]
    state = {"messages": [], "geodata_results": [], "options": {"session_id": "session-5"}}

    process_command = process_tool.func(
        state=state,
        tool_call_id="process-call",
        process_id="buffer_geometries",
        inputs={"feature_collection": {"type": "FeatureCollection", "features": []}},
        prefer_async=True,
    )
    process_payload = _message_payload(process_command)

    assert process_payload["status"] == "accepted"
    assert process_payload["process_id"] == "vector-buffer"
    assert process_payload["requested_process_id"] == "buffer_geometries"


def test_process_geodata_rejects_unknown_process_id_without_validate_call(monkeypatch):
    calls = []

    def fake_request(method, url, headers=None, params=None, json=None, timeout=None):
        calls.append(url)
        if url.endswith("/v1/agent/capabilities"):
            return MockResponse(
                status_code=200,
                payload={
                    "service": {"apiPrefix": "/v1"},
                    "capabilities": {"processes": [{"id": "vector-buffer"}]},
                },
                headers={"ETag": 'W/"manifest-unknown"', "x-request-id": "req-cap", "x-trace-id": "trace-cap"},
            )
        raise AssertionError(f"Unexpected request: {method} {url}")

    monkeypatch.setattr("services.tools.ogcapi_tools.requests.request", fake_request)

    class Server:
        url = "http://mock-ogc.local/v1"
        name = "mock"
        api_key = None
        headers = None
        description = "mock"

    tools = build_ogcapi_tools(
        [Server()],
        default_session_id="session-6",
        include_prepare=False,
        include_filter=False,
        include_process=True,
    )
    process_tool = tools[0]
    state = {"messages": [], "geodata_results": [], "options": {"session_id": "session-6"}}

    process_command = process_tool.func(
        state=state,
        tool_call_id="process-call",
        process_id="totally_missing_process",
        inputs={"feature_collection": {"type": "FeatureCollection", "features": []}},
        prefer_async=True,
    )
    process_payload = _message_payload(process_command)

    assert process_payload["status"] == "error"
    assert process_payload["error"]["code"] == "unknown_process_id"
    assert "available_processes" in process_payload["detail"]
    assert process_payload["detail"]["available_processes"] == ["vector-buffer"]
    assert len(calls) == 1


def test_process_geodata_falls_back_to_feature_collection_when_collection_missing(monkeypatch):
    def fake_request(method, url, headers=None, params=None, json=None, timeout=None):
        if url.endswith("/v1/agent/capabilities"):
            return MockResponse(
                status_code=200,
                payload={
                    "service": {"apiPrefix": "/v1"},
                    "capabilities": {"processes": [{"id": "vector-buffer"}]},
                },
                headers={"ETag": 'W/"manifest-fallback"', "x-request-id": "req-cap", "x-trace-id": "trace-cap"},
            )
        if url.endswith("/v1/collections/missing_collection"):
            return MockResponse(
                status_code=404,
                payload={"detail": "Collection not found"},
                headers={"x-request-id": "req-col", "x-trace-id": "trace-col"},
            )
        if url.endswith("/v1/processes/vector-buffer/validate"):
            assert "feature_collection" in json["inputs"]
            assert "collection_id" not in json["inputs"]
            return MockResponse(
                status_code=200,
                payload={"valid": True, "dryRun": True, "normalizedInputs": json["inputs"]},
                headers={"x-request-id": "req-val", "x-trace-id": "trace-val"},
            )
        if url.endswith("/v1/processes/vector-buffer/jobs"):
            return MockResponse(
                status_code=201,
                payload={"jobID": "job-fallback-1", "status": "accepted"},
                headers={"x-request-id": "req-job", "x-trace-id": "trace-job"},
            )
        raise AssertionError(f"Unexpected request: {method} {url}")

    def fake_get(url, timeout=None, headers=None):
        assert url.endswith("/v1/uploads/files/forest.geojson")
        return MockResponse(
            status_code=200,
            payload={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [10, 10]},
                        "properties": {"name": "forest"},
                    }
                ],
            },
        )

    monkeypatch.setattr("services.tools.ogcapi_tools.requests.request", fake_request)
    monkeypatch.setattr("services.tools.ogcapi_tools.requests.get", fake_get)

    class Server:
        url = "http://mock-ogc.local/v1"
        name = "mock"
        api_key = None
        headers = None
        description = "mock"

    tools = build_ogcapi_tools(
        [Server()],
        default_session_id="session-7",
        include_prepare=False,
        include_filter=False,
        include_process=True,
    )
    process_tool = tools[0]
    state = {
        "messages": [],
        "geodata_results": [],
        "geodata_layers": [
            {
                "id": "layer-forest",
                "name": "forest.geojson",
                "data_link": "http://localhost:8081/v1/uploads/files/forest.geojson",
                "properties": {"ogc_collection_id": "missing_collection"},
            }
        ],
        "options": {"session_id": "session-7"},
    }

    process_command = process_tool.func(
        state=state,
        tool_call_id="process-call",
        process_id="vector-buffer",
        input_refs=["forest.geojson"],
        prefer_async=True,
    )
    process_payload = _message_payload(process_command)

    assert process_payload["status"] == "accepted"
    assert process_payload["process_id"] == "vector-buffer"
