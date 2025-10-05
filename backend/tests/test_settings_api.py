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


def test_preload_endpoint_uses_session_cookie(api_client, monkeypatch):
    session_response = api_client.get("/settings/options")
    session_id = session_response.json()["session_id"]

    called = {}

    def fake_preload(session, backend, search_term=None):
        called["session"] = session
        called["backend"] = backend
        return {
            "session_id": session,
            "backend_url": backend.url,
            "backend_name": backend.name,
            "total_layers": 2,
            "service_status": {"WMS": True},
            "service_counts": {"WMS": 2},
        }

    monkeypatch.setattr("api.settings.preload_backend_layers", fake_preload)

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
    assert data["total_layers"] == 2
    assert called["session"] == session_id
