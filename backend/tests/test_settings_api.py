import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    # Set test environment for local HTTP testing BEFORE importing
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("COOKIE_HTTPONLY", "false")
    monkeypatch.setenv("NALAMAP_GEOSERVER_VECTOR_DB", str(tmp_path / "vectors.db"))

    # Force reload of config to pick up test environment variables
    import importlib

    import core.config

    importlib.reload(core.config)

    # Now import the router
    from api.settings import router as settings_router

    app = FastAPI()
    app.include_router(settings_router)
    return TestClient(app)


def test_options_endpoint_creates_session_cookie(api_client):
    response = api_client.get("/settings/options")
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert data["session_id"]
    assert api_client.cookies.get("session_id") == data["session_id"]


def test_options_endpoint_returns_example_geoservers(api_client):
    response = api_client.get("/settings/options")
    assert response.status_code == 200
    data = response.json()
    assert "example_geoserver_backends" in data
    assert isinstance(data["example_geoserver_backends"], list)
    assert len(data["example_geoserver_backends"]) > 0

    # Check the first example (MapX)
    mapx = data["example_geoserver_backends"][0]
    assert "url" in mapx
    assert "name" in mapx
    assert "description" in mapx
    assert mapx["name"] == "MapX"
    assert mapx["url"] == "https://geoserver.mapx.org/geoserver/"


def test_preload_endpoint_uses_session_cookie(api_client, monkeypatch):
    session_response = api_client.get("/settings/options")
    session_id = session_response.json()["session_id"]

    called = {}

    # Mock the capability fetching to avoid network calls
    def fake_fetch_capabilities(backend, search_term=None):
        from models.geodata import DataOrigin, DataType, GeoDataObject

        layers = [
            GeoDataObject(
                id="test_layer_1",
                data_source_id="test_1",
                data_type=DataType.RASTER,
                data_origin=DataOrigin.TOOL.value,
                data_source="Test",
                data_link="http://example.com",
                name="Test Layer 1",
                title="Test Layer 1",
                description="Test",
                layer_type="WMS",
            ),
            GeoDataObject(
                id="test_layer_2",
                data_source_id="test_2",
                data_type=DataType.LAYER,
                data_origin=DataOrigin.TOOL.value,
                data_source="Test",
                data_link="http://example.com",
                name="Test Layer 2",
                title="Test Layer 2",
                description="Test",
                layer_type="WFS",
            ),
        ]
        status = {"WMS": True, "WFS": True, "WCS": False, "WMTS": False}
        errors = {}  # No errors
        return layers, status, errors

    # Mock delete_layers and store_layers
    def fake_delete_layers(session, urls):
        pass

    def fake_store_layers(session, backend_url, backend_name, layers):
        called["session"] = session
        called["backend_url"] = backend_url
        called["stored_layers"] = len(layers)
        return len(layers)

    # Mock the task manager to execute synchronously for testing
    class MockTaskManager:
        def submit_task(self, func, *args, priority=None, task_id=None, **kwargs):
            # Execute immediately for testing
            func(*args, **kwargs)
            called["executed"] = True
            return None

        def get_stats(self):
            return {}

    def mock_get_task_manager():
        return MockTaskManager()

    # Mock all the required functions
    monkeypatch.setattr("api.settings.get_task_manager", mock_get_task_manager)
    monkeypatch.setattr("api.settings.set_processing_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "services.tools.geoserver.custom_geoserver.fetch_all_service_capabilities_with_status",
        fake_fetch_capabilities,
    )
    monkeypatch.setattr(
        "services.tools.geoserver.custom_geoserver.delete_layers", fake_delete_layers
    )
    monkeypatch.setattr("services.tools.geoserver.custom_geoserver.store_layers", fake_store_layers)

    payload = {
        "backend": {
            "url": "http://example.com/geoserver",
            "name": "Example",
            "description": "",
            "username": None,
            "password": None,
        }
    }

    response = api_client.post("/settings/geoserver/preload", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Note: The endpoint now returns immediately with total_layers=0
    # The actual processing happens in the background (but we execute it sync in test)
    assert data["session_id"] == session_id
    assert data["backend_url"] == "http://example.com/geoserver"

    # Verify the background task was executed and used the correct session
    assert called["executed"] is True
    assert called["session"] == session_id
    assert called["stored_layers"] == 2


def test_options_endpoint_returns_example_mcp_servers(api_client):
    """Test that the /settings/options endpoint returns example MCP servers."""
    response = api_client.get("/settings/options")
    assert response.status_code == 200
    data = response.json()
    assert "example_mcp_servers" in data
    assert isinstance(data["example_mcp_servers"], list)
    # Example list can be empty (users add their own custom servers)
    assert len(data["example_mcp_servers"]) >= 0
