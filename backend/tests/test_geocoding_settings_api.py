import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    from main import app

    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_status():
    """Reset the in-memory status tracker between tests."""
    import api.geocoding_settings as gs

    with gs._status_lock:
        gs._populate_status.update(
            {"state": "idle", "total": 0, "encoded": 0, "error_message": None}
        )
    yield


# ---------------------------------------------------------------------------
# GET /settings/geocoding/embedding-status
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_get_embedding_status_empty(client):
    """When store is empty and no task is running, state should be 'empty'."""
    with patch("api.geocoding_settings.get_tag_store_status") as mock:
        mock.return_value = {
            "state": "empty",
            "total": 0,
            "encoded": 0,
            "tag_count": 0,
            "last_updated": None,
            "error_message": None,
        }
        response = client.get("/api/settings/geocoding/embedding-status")
    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "empty"
    assert data["tag_count"] == 0
    assert data["percentage"] == 0.0


@pytest.mark.integration
def test_get_embedding_status_populated(client):
    """When store has tags, status should report populated state and count."""
    with patch("api.geocoding_settings.get_tag_store_status") as mock:
        mock.return_value = {
            "state": "populated",
            "total": 5000,
            "encoded": 5000,
            "tag_count": 5000,
            "last_updated": "2026-01-01T00:00:00",
            "error_message": None,
        }
        response = client.get("/api/settings/geocoding/embedding-status")
    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "populated"
    assert data["tag_count"] == 5000
    assert data["percentage"] == 100.0


@pytest.mark.integration
def test_get_embedding_status_processing(client):
    """During population the state and percentage should be reported correctly."""
    with patch("api.geocoding_settings.get_tag_store_status") as mock:
        mock.return_value = {
            "state": "processing",
            "total": 1000,
            "encoded": 500,
            "tag_count": 0,
            "last_updated": None,
            "error_message": None,
        }
        response = client.get("/api/settings/geocoding/embedding-status")
    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "processing"
    assert data["percentage"] == 50.0


@pytest.mark.integration
def test_get_embedding_status_error(client):
    """Error state should include an error_message."""
    with patch("api.geocoding_settings.get_tag_store_status") as mock:
        mock.return_value = {
            "state": "error",
            "total": 0,
            "encoded": 0,
            "tag_count": 0,
            "last_updated": None,
            "error_message": "Network timeout",
        }
        response = client.get("/api/settings/geocoding/embedding-status")
    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "error"
    assert "Network timeout" in data["error_message"]


# ---------------------------------------------------------------------------
# POST /settings/geocoding/populate-tags
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_populate_tags_triggers_task(client):
    """POST /populate-tags should return waiting state and a task_id."""
    with patch("api.geocoding_settings.get_tag_store_status") as mock_status:
        mock_status.return_value = {
            "state": "empty",
            "total": 0,
            "encoded": 0,
            "tag_count": 0,
            "last_updated": None,
            "error_message": None,
        }
        with patch("api.geocoding_settings.submit_populate_task") as mock_submit:
            mock_submit.return_value = "populate_osm_tags"
            response = client.post(
                "/api/settings/geocoding/populate-tags",
                json={"scope": "popular"},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "waiting"
    assert data["task_id"] == "populate_osm_tags"
    mock_submit.assert_called_once()


@pytest.mark.integration
def test_populate_tags_skips_when_already_populated(client):
    """Should skip population if store is already populated and force_refresh=False."""
    with patch("api.geocoding_settings.get_tag_store_status") as mock_status:
        mock_status.return_value = {
            "state": "populated",
            "total": 5000,
            "encoded": 5000,
            "tag_count": 5000,
            "last_updated": "2026-01-01",
            "error_message": None,
        }
        with patch("api.geocoding_settings.submit_populate_task") as mock_submit:
            response = client.post(
                "/api/settings/geocoding/populate-tags",
                json={"scope": "popular", "force_refresh": False},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "already_populated"
    assert data["task_id"] is None
    mock_submit.assert_not_called()


@pytest.mark.integration
def test_populate_tags_force_refresh_overrides_populated(client):
    """force_refresh=True should trigger population even if already populated."""
    with patch("api.geocoding_settings.get_tag_store_status") as mock_status:
        mock_status.return_value = {
            "state": "populated",
            "total": 5000,
            "encoded": 5000,
            "tag_count": 5000,
            "last_updated": "2026-01-01",
            "error_message": None,
        }
        with patch("api.geocoding_settings.submit_populate_task") as mock_submit:
            mock_submit.return_value = "populate_osm_tags"
            response = client.post(
                "/api/settings/geocoding/populate-tags",
                json={"scope": "popular", "force_refresh": True},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "waiting"
    mock_submit.assert_called_once()


@pytest.mark.integration
def test_populate_tags_default_request_body(client):
    """POST with empty body should use defaults and start a task."""
    with patch("api.geocoding_settings.get_tag_store_status") as mock_status:
        mock_status.return_value = {
            "state": "empty",
            "tag_count": 0,
            "total": 0,
            "encoded": 0,
            "last_updated": None,
            "error_message": None,
        }
        with patch("api.geocoding_settings.submit_populate_task") as mock_submit:
            mock_submit.return_value = "populate_osm_tags"
            response = client.post("/api/settings/geocoding/populate-tags", json={})

    assert response.status_code == 200
    assert response.json()["state"] == "waiting"


# ---------------------------------------------------------------------------
# get_tag_store_status unit tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_tag_store_status_merges_store_and_tracker():
    """Status should reflect store count and in-memory tracker state."""
    import api.geocoding_settings as gs

    mock_store = MagicMock()
    mock_store.get_status.return_value = {
        "state": "populated",
        "count": 3000,
        "last_updated": "2026-01-15",
    }

    with patch(
        "services.tools.geocoding.tag_vector_store.TagVectorStore.get_status",
        return_value={"state": "populated", "count": 3000, "last_updated": "2026-01-15"},
    ):
        status = gs.get_tag_store_status()

    assert status["tag_count"] == 3000
    assert status["last_updated"] == "2026-01-15"


@pytest.mark.unit
def test_get_tag_store_status_shows_processing_during_task():
    """While a task is running, state should be 'processing' not 'populated'."""
    import api.geocoding_settings as gs

    with gs._status_lock:
        gs._populate_status["state"] = "processing"
        gs._populate_status["total"] = 100
        gs._populate_status["encoded"] = 42

    with patch(
        "services.tools.geocoding.tag_vector_store.TagVectorStore.get_status",
        return_value={"state": "empty", "count": 0, "last_updated": None},
    ):
        status = gs.get_tag_store_status()

    assert status["state"] == "processing"
    assert status["encoded"] == 42
