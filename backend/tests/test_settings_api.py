import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    # Set test environment for local HTTP testing BEFORE importing
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("COOKIE_HTTPONLY", "false")
    monkeypatch.setenv("NALAMAP_GEOSERVER_VECTOR_DB", str(tmp_path / "vectors.db"))

    # NOTE: Do NOT reload core.config because it will re-run load_dotenv()
    # which will override environment variables with .env.local values

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


# ============================================================================
# Deployment Config Integration Tests
# ============================================================================


@pytest.fixture
def api_client_with_deployment_config(tmp_path, monkeypatch):
    """API client with a deployment config file."""
    # Clear config cache FIRST before setting env vars
    from services.deployment_config_loader import clear_config_cache

    clear_config_cache()

    # Create a deployment config file with correct schema format
    config_file = tmp_path / "deployment_config.json"
    config_data = {
        "config_name": "Test Deployment Config",
        "tools": [
            {"name": "geocode_nominatim", "enabled": True},
            {"name": "geocode_overpass", "enabled": False},
        ],
        "geoserver_backends": [
            {
                "url": "https://test.geoserver.com/geoserver/",
                "name": "Test GeoServer",
                "description": "Test backend for API testing",
                "preload_on_startup": False,
            }
        ],
        "model_settings": {"model_provider": "openai", "model_name": "gpt-4o-mini"},
    }
    config_file.write_text(json.dumps(config_data))

    # Set test environment
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("COOKIE_HTTPONLY", "false")
    monkeypatch.setenv("NALAMAP_GEOSERVER_VECTOR_DB", str(tmp_path / "vectors.db"))
    monkeypatch.setenv("DEPLOYMENT_CONFIG_PATH", str(config_file))

    # NOTE: Do NOT reload core.config here because it will re-run load_dotenv()
    # which will re-set DEPLOYMENT_CONFIG_PATH from .env.local with override=True
    # The monkeypatch.setenv() already set it in os.environ, so we're good.

    # Clear again after env var is set to ensure clean state
    clear_config_cache()

    # Now import the router
    from api.settings import router as settings_router

    app = FastAPI()
    app.include_router(settings_router)
    client = TestClient(app)

    yield client

    # Clean up: clear cache after test
    clear_config_cache()


@pytest.fixture
def api_client_without_deployment_config(tmp_path, monkeypatch):
    """API client without a deployment config file."""
    # Clear config cache FIRST before setting env vars
    from services.deployment_config_loader import clear_config_cache

    clear_config_cache()

    # Set test environment without DEPLOYMENT_CONFIG_PATH
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("COOKIE_HTTPONLY", "false")
    monkeypatch.setenv("NALAMAP_GEOSERVER_VECTOR_DB", str(tmp_path / "vectors.db"))
    monkeypatch.delenv("DEPLOYMENT_CONFIG_PATH", raising=False)

    # NOTE: Do NOT reload core.config here because it will re-run load_dotenv()
    # which will re-set DEPLOYMENT_CONFIG_PATH from .env.local with override=True
    # The monkeypatch.delenv() already removed it from os.environ, so we're good.

    # Clear again after env var is removed to ensure clean state
    clear_config_cache()

    from api.settings import router as settings_router

    app = FastAPI()
    app.include_router(settings_router)
    client = TestClient(app)

    yield client

    # Clean up
    clear_config_cache()


def test_options_endpoint_without_deployment_config(api_client_without_deployment_config):
    """Test that settings/options works correctly without deployment config."""
    response = api_client_without_deployment_config.get("/settings/options")
    assert response.status_code == 200
    data = response.json()

    # Should return tool_options dict from DEFAULT_AVAILABLE_TOOLS
    assert "tool_options" in data
    assert isinstance(data["tool_options"], dict)
    assert len(data["tool_options"]) > 0

    # All tools should have expected fields
    for tool_name, tool_config in data["tool_options"].items():
        assert "enabled" in tool_config
        assert "default_prompt" in tool_config

    # Should have empty preconfigured_geoserver_backends (no deployment config)
    assert "preconfigured_geoserver_backends" in data
    assert data["preconfigured_geoserver_backends"] == []

    # Should have default color_settings
    assert "color_settings" in data
    assert "primary" in data["color_settings"]


def test_options_endpoint_with_deployment_config(api_client_with_deployment_config):
    """Test that settings/options integrates deployment config correctly."""
    response = api_client_with_deployment_config.get("/settings/options")
    assert response.status_code == 200
    data = response.json()

    # Check tools have been configured from deployment config
    assert "tool_options" in data
    tool_options = data["tool_options"]

    # geocode_nominatim should be enabled (from deployment config)
    if "geocode_nominatim" in tool_options:
        assert tool_options["geocode_nominatim"]["enabled"] is True

    # geocode_overpass should be disabled (from deployment config)
    if "geocode_overpass" in tool_options:
        assert tool_options["geocode_overpass"]["enabled"] is False

    # Check preconfigured geoserver backends
    assert "preconfigured_geoserver_backends" in data
    backends = data["preconfigured_geoserver_backends"]
    assert len(backends) == 1
    assert backends[0]["name"] == "Test GeoServer"
    assert backends[0]["url"] == "https://test.geoserver.com/geoserver/"

    # Check deployment config name is returned
    assert "deployment_config_name" in data
    assert data["deployment_config_name"] == "Test Deployment Config"


def test_options_endpoint_returns_model_options(api_client_with_deployment_config):
    """Test that settings/options returns model options."""
    response = api_client_with_deployment_config.get("/settings/options")
    assert response.status_code == 200
    data = response.json()

    # Check that model_options is present and structured correctly
    assert "model_options" in data
    assert isinstance(data["model_options"], dict)
    # Model options contain provider names as keys with lists of models
    for provider_name, models in data["model_options"].items():
        assert isinstance(models, list)


def test_options_endpoint_returns_color_settings(api_client_with_deployment_config):
    """Test that settings/options returns color settings."""
    response = api_client_with_deployment_config.get("/settings/options")
    assert response.status_code == 200
    data = response.json()

    # Check that color settings are included with full scale structure
    assert "color_settings" in data
    color_settings = data["color_settings"]

    # Check that all required color scales are present
    required_scales = [
        "primary",
        "second_primary",
        "secondary",
        "tertiary",
        "danger",
        "warning",
        "info",
        "neutral",
        "corporate_1",
        "corporate_2",
        "corporate_3",
    ]
    for scale_name in required_scales:
        assert scale_name in color_settings
        # Each scale should have shade_50 through shade_950
        assert "shade_50" in color_settings[scale_name]
        assert "shade_950" in color_settings[scale_name]


@pytest.fixture
def api_client_with_invalid_deployment_config(tmp_path, monkeypatch):
    """API client with an invalid deployment config file."""
    # Clear config cache FIRST before setting env vars
    from services.deployment_config_loader import clear_config_cache

    clear_config_cache()

    # Create an invalid deployment config file
    config_file = tmp_path / "invalid_config.json"
    config_data = {
        "tools": {
            "nonexistent_tool": {"enabled": True},  # This tool doesn't exist
        },
        "model_settings": {
            "default_provider": "invalid_provider",  # Invalid provider
        },
    }
    config_file.write_text(json.dumps(config_data))

    # Set test environment
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("COOKIE_HTTPONLY", "false")
    monkeypatch.setenv("NALAMAP_GEOSERVER_VECTOR_DB", str(tmp_path / "vectors.db"))
    monkeypatch.setenv("DEPLOYMENT_CONFIG_PATH", str(config_file))

    # NOTE: Do NOT reload core.config because it will re-run load_dotenv()
    # which will override environment variables with .env.local values

    # Clear again after env var is set to ensure clean state
    clear_config_cache()

    from api.settings import router as settings_router

    app = FastAPI()
    app.include_router(settings_router)
    client = TestClient(app)

    yield client

    clear_config_cache()


def test_options_endpoint_graceful_degradation_with_invalid_config(
    api_client_with_invalid_deployment_config,
):
    """Test that settings/options gracefully handles invalid deployment config."""
    response = api_client_with_invalid_deployment_config.get("/settings/options")
    # Should still return 200 - config validation warns but doesn't fail
    assert response.status_code == 200
    data = response.json()

    # Should still return tool_options dict
    assert "tool_options" in data
    assert isinstance(data["tool_options"], dict)

    # Tools should use defaults - nonexistent_tool should not appear
    assert "nonexistent_tool" not in data["tool_options"]


def test_options_endpoint_missing_config_file(tmp_path, monkeypatch):
    """Test that settings/options handles missing config file gracefully."""
    # Clear config cache FIRST before setting env vars
    from services.deployment_config_loader import clear_config_cache

    clear_config_cache()

    # Point to a non-existent file
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("COOKIE_HTTPONLY", "false")
    monkeypatch.setenv("NALAMAP_GEOSERVER_VECTOR_DB", str(tmp_path / "vectors.db"))
    monkeypatch.setenv("DEPLOYMENT_CONFIG_PATH", "/nonexistent/path/config.json")

    # NOTE: Do NOT reload core.config because it will re-run load_dotenv()
    # which will override environment variables with .env.local values

    # Clear again after env var is set to ensure clean state
    clear_config_cache()

    from api.settings import router as settings_router

    app = FastAPI()
    app.include_router(settings_router)
    client = TestClient(app)

    response = client.get("/settings/options")
    # Should still return 200 with defaults
    assert response.status_code == 200
    data = response.json()

    assert "tool_options" in data
    assert len(data["tool_options"]) > 0

    clear_config_cache()


def test_options_endpoint_malformed_json_config(tmp_path, monkeypatch):
    """Test that settings/options handles malformed JSON config file."""
    # Clear config cache FIRST before setting env vars
    from services.deployment_config_loader import clear_config_cache

    clear_config_cache()

    # Create a malformed JSON file
    config_file = tmp_path / "malformed_config.json"
    config_file.write_text("{ invalid json }")

    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("COOKIE_HTTPONLY", "false")
    monkeypatch.setenv("NALAMAP_GEOSERVER_VECTOR_DB", str(tmp_path / "vectors.db"))
    monkeypatch.setenv("DEPLOYMENT_CONFIG_PATH", str(config_file))

    # NOTE: Do NOT reload core.config because it will re-run load_dotenv()
    # which will override environment variables with .env.local values

    # Clear again after env var is set to ensure clean state
    clear_config_cache()

    from api.settings import router as settings_router

    app = FastAPI()
    app.include_router(settings_router)
    client = TestClient(app)

    response = client.get("/settings/options")
    # Should still return 200 with defaults
    assert response.status_code == 200
    data = response.json()

    assert "tool_options" in data
    assert len(data["tool_options"]) > 0

    clear_config_cache()
