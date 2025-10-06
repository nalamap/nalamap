"""Tests for embedding progress tracking functionality."""

import pytest

from models.geodata import DataOrigin, DataType, GeoDataObject
from services.tools.geoserver import vector_store as vs


def make_layer(layer_id: str, name: str, title: str) -> GeoDataObject:
    """Helper to create test GeoDataObject instances."""
    return GeoDataObject(
        id=layer_id,
        data_source_id="test-catalog",
        data_type=DataType.LAYER,
        data_origin=DataOrigin.TOOL,
        data_source="TestGeoServer",
        data_link=f"https://example.com/geoserver/{layer_id}",
        name=name,
        title=title,
        description=f"Description for {name}",
        layer_type="WMS",
    )


@pytest.fixture(autouse=True)
def reset_store(monkeypatch):
    """Clean up before and after each test and force fallback mode."""
    vs.reset_vector_store_for_tests()
    # Force fallback mode to avoid extension loading issues in tests
    monkeypatch.setattr(vs, "_use_fallback_store", True, raising=False)
    monkeypatch.setattr(vs, "_fallback_documents", [], raising=False)
    monkeypatch.setattr(vs, "_embedding_progress", {}, raising=False)
    yield
    vs.reset_vector_store_for_tests()


def test_embedding_progress_tracking():
    """Test that store_layers tracks embedding progress."""
    session_id = "test-session"
    backend_url = "https://example.com/geoserver"

    layers = [
        make_layer("1", "layer_1", "Layer 1"),
        make_layer("2", "layer_2", "Layer 2"),
        make_layer("3", "layer_3", "Layer 3"),
    ]

    # Store layers
    vs.store_layers(session_id, backend_url, "Test Server", layers)

    # Check progress
    status = vs.get_embedding_status(session_id, [backend_url])

    assert backend_url in status
    assert status[backend_url]["total"] == 3
    assert status[backend_url]["encoded"] == 3
    assert status[backend_url]["percentage"] == 100
    assert status[backend_url]["complete"] is True
    assert status[backend_url]["in_progress"] is False


def test_embedding_status_for_nonexistent_backend():
    """Test that get_embedding_status returns empty status for non-existent backends."""
    session_id = "test-session"
    backend_url = "https://nonexistent.com/geoserver"

    status = vs.get_embedding_status(session_id, [backend_url])

    assert backend_url in status
    assert status[backend_url]["total"] == 0
    assert status[backend_url]["encoded"] == 0
    assert status[backend_url]["percentage"] == 0
    assert status[backend_url]["complete"] is False
    assert status[backend_url]["in_progress"] is False


def test_is_fully_encoded_returns_true_when_complete():
    """Test that is_fully_encoded returns True when all layers are encoded."""
    session_id = "test-session"
    backend_url = "https://example.com/geoserver"

    layers = [make_layer("1", "layer_1", "Layer 1")]
    vs.store_layers(session_id, backend_url, "Test Server", layers)

    assert vs.is_fully_encoded(session_id, [backend_url]) is True


def test_is_fully_encoded_returns_true_when_no_progress():
    """Test that is_fully_encoded returns True when there's no progress data."""
    session_id = "test-session"
    backend_url = "https://example.com/geoserver"

    # No layers stored, no progress data
    assert vs.is_fully_encoded(session_id, [backend_url]) is True


def test_embedding_progress_multiple_backends():
    """Test embedding progress tracking for multiple backends."""
    session_id = "test-session"
    backend1 = "https://backend1.com/geoserver"
    backend2 = "https://backend2.com/geoserver"

    layers1 = [make_layer("1", "layer_1", "Layer 1")]
    layers2 = [
        make_layer("2", "layer_2", "Layer 2"),
        make_layer("3", "layer_3", "Layer 3"),
    ]

    vs.store_layers(session_id, backend1, "Backend 1", layers1)
    vs.store_layers(session_id, backend2, "Backend 2", layers2)

    status = vs.get_embedding_status(session_id, [backend1, backend2])

    assert status[backend1]["total"] == 1
    assert status[backend1]["encoded"] == 1
    assert status[backend2]["total"] == 2
    assert status[backend2]["encoded"] == 2
    assert vs.is_fully_encoded(session_id, [backend1, backend2]) is True


def test_embedding_progress_different_sessions():
    """Test that embedding progress is tracked per session."""
    session1 = "session-1"
    session2 = "session-2"
    backend_url = "https://example.com/geoserver"

    layers1 = [make_layer("1", "layer_1", "Layer 1")]
    layers2 = [
        make_layer("2", "layer_2", "Layer 2"),
        make_layer("3", "layer_3", "Layer 3"),
    ]

    vs.store_layers(session1, backend_url, "Server", layers1)
    vs.store_layers(session2, backend_url, "Server", layers2)

    status1 = vs.get_embedding_status(session1, [backend_url])
    status2 = vs.get_embedding_status(session2, [backend_url])

    assert status1[backend_url]["total"] == 1
    assert status2[backend_url]["total"] == 2


def test_reset_clears_embedding_progress():
    """Test that reset_vector_store_for_tests clears embedding progress."""
    session_id = "test-session"
    backend_url = "https://example.com/geoserver"

    layers = [make_layer("1", "layer_1", "Layer 1")]
    vs.store_layers(session_id, backend_url, "Test Server", layers)

    # Verify progress exists
    status = vs.get_embedding_status(session_id, [backend_url])
    assert status[backend_url]["total"] > 0

    # Reset
    vs.reset_vector_store_for_tests()

    # Progress should be cleared
    status = vs.get_embedding_status(session_id, [backend_url])
    assert status[backend_url]["total"] == 0
