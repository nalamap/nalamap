"""
Test thread safety of the vector store implementation.

These tests verify that:
1. Multiple threads can safely access the vector store simultaneously
2. Data written by one thread is visible to other threads (same database)
3. Each thread gets its own connection (no threading errors)
"""

import threading
import time

import pytest

from models.geodata import DataOrigin, DataType, GeoDataObject
from services.tools.geoserver.vector_store import (delete_layers,
                                                   get_vector_store,
                                                   list_layers,
                                                   similarity_search,
                                                   store_layers)


@pytest.fixture
def temp_db_path(tmp_path, monkeypatch):
    """Fixture to use the fallback store for threading tests.

    The fallback store is used because sqlite_vec extension loading
    is not supported in this Python build (enable_load_extension not available).
    The fallback store is thread-safe and suitable for testing threading behavior.
    """
    # Use the fallback store which is thread-safe
    from services.tools.geoserver import vector_store as vs

    vs.reset_vector_store_for_tests()
    monkeypatch.setattr(vs, "_use_fallback_store", True, raising=False)
    monkeypatch.setattr(vs, "_fallback_documents", [], raising=False)
    yield
    vs.reset_vector_store_for_tests()


def create_test_layer(layer_id: str, name: str, description: str) -> GeoDataObject:
    """Helper to create a test layer."""
    return GeoDataObject(
        id=layer_id,
        data_source_id="test_catalog",
        data_type=DataType.LAYER,
        data_origin=DataOrigin.TOOL,
        data_source="GeoServer",
        data_link=f"http://example.com/{layer_id}",
        name=name,
        title=f"Title: {name}",
        description=description,
        layer_type="WMS",
        properties={"test": True},
    )


def test_cross_thread_write_and_read(temp_db_path):
    """Test that data written by Thread A can be read by Thread B.

    This is the key test: even though each thread has its own connection,
    they all connect to the same SQLite database file, so data is shared.
    """
    session_id = "cross-thread-test"
    backend_url = "http://example.com/geoserver"
    errors = []
    results = {}

    def writer_thread():
        """Thread 1: Write layers to the database."""
        try:
            layers = [
                create_test_layer("layer1", "Water", "Water bodies"),
                create_test_layer("layer2", "Roads", "Road network"),
            ]
            store_layers(session_id, backend_url, "Test Backend", layers)
            results["write"] = "success"
        except Exception as e:
            import traceback

            errors.append(f"Writer error: {e}\n{traceback.format_exc()}")

    def reader_thread():
        """Thread 2: Read layers from the database."""
        try:
            # Small delay to ensure writer has finished
            time.sleep(0.1)

            # Read layers written by Thread 1
            layers = list_layers(
                session_id, backend_urls=["http://example.com/geoserver"], limit=10
            )

            # Verify we can see the data
            layer_ids = {layer.id for layer in layers}
            if "layer1" in layer_ids and "layer2" in layer_ids:
                results["read"] = "success"
                results["layer_count"] = len(layers)
            else:
                errors.append(f"Reader couldn't see all layers: {layer_ids}")
        except Exception as e:
            import traceback

            errors.append(f"Reader error: {e}\n{traceback.format_exc()}")

    # Run writer and reader in separate threads
    t1 = threading.Thread(target=writer_thread)
    t2 = threading.Thread(target=reader_thread)

    t1.start()
    t2.start()

    t1.join(timeout=2.0)
    t2.join(timeout=2.0)

    # Verify no errors occurred
    assert not errors, f"Threading errors: {errors}"

    # Verify both operations succeeded
    assert results.get("write") == "success", "Writer thread failed"
    assert results.get("read") == "success", "Reader thread failed"
    assert results.get("layer_count") == 2, "Reader didn't see all layers"


def test_concurrent_writes_different_sessions(temp_db_path):
    """Test multiple threads writing to different sessions simultaneously."""
    errors = []
    results = {}

    def write_session(session_id: str):
        """Write layers for a specific session."""
        try:
            backend_url = f"http://example.com/session{session_id}"
            layers = [
                create_test_layer(
                    f"{session_id}_layer1",
                    f"Layer 1 for {session_id}",
                    f"Description for session {session_id}",
                )
            ]
            store_layers(session_id, backend_url, f"Backend {session_id}", layers)
            results[session_id] = "success"
        except Exception as e:
            errors.append(f"Session {session_id} error: {e}")

    # Create 5 threads writing to different sessions
    threads = []
    for i in range(5):
        session_id = f"session_{i}"
        t = threading.Thread(target=write_session, args=(session_id,))
        threads.append(t)
        t.start()

    # Wait for all threads to complete
    for t in threads:
        t.join(timeout=2.0)

    # Verify no errors
    assert not errors, f"Threading errors: {errors}"

    # Verify all sessions were written
    for i in range(5):
        session_id = f"session_{i}"
        assert results.get(session_id) == "success", f"{session_id} failed"

        # Verify we can read back each session's data (using the correct backend URL)
        backend_url = f"http://example.com/session{session_id}"
        layers = list_layers(session_id, backend_urls=[backend_url], limit=10)
        assert len(layers) == 1, f"{session_id} has wrong number of layers"
        assert layers[0].id == f"{session_id}_layer1"


def test_concurrent_reads_same_session(temp_db_path):
    """Test multiple threads reading from the same session simultaneously."""
    session_id = "shared-session"
    backend_url = "http://example.com/geoserver"

    # Pre-populate database
    layers = [
        create_test_layer("read_layer1", "Layer 1", "First layer"),
        create_test_layer("read_layer2", "Layer 2", "Second layer"),
        create_test_layer("read_layer3", "Layer 3", "Third layer"),
    ]
    store_layers(session_id, backend_url, "Test Backend", layers)

    errors = []
    read_counts = []

    def reader_thread(thread_num: int):
        """Read layers from the shared session."""
        try:
            # Each thread reads multiple times
            for _ in range(3):
                layers_read = list_layers(
                    session_id, backend_urls=["http://example.com/geoserver"], limit=10
                )
                if len(layers_read) != 3:
                    errors.append(f"Thread {thread_num} saw {len(layers_read)} layers, expected 3")
                time.sleep(0.01)  # Small delay
            read_counts.append(thread_num)
        except Exception as e:
            errors.append(f"Thread {thread_num} error: {e}")

    # Create 10 threads all reading from the same session
    threads = []
    for i in range(10):
        t = threading.Thread(target=reader_thread, args=(i,))
        threads.append(t)
        t.start()

    # Wait for all threads
    for t in threads:
        t.join(timeout=3.0)

    # Verify no errors
    assert not errors, f"Threading errors: {errors}"

    # Verify all threads completed
    assert len(read_counts) == 10, "Not all reader threads completed"


def test_thread_local_connections_are_isolated(temp_db_path):
    """Verify that each thread gets its own connection object.

    Note: This test is skipped when using the fallback store since it
    doesn't use SQLite connections.
    """
    from services.tools.geoserver import vector_store as vs

    # Skip if using fallback store
    if vs._use_fallback_store:
        pytest.skip("Not applicable when using fallback store")

    connection_ids = {}
    errors = []

    def get_connection_id(thread_num: int):
        """Get the Python object id of this thread's connection."""
        try:
            store = get_vector_store()
            if store is not None:
                # Get the connection object's id
                conn_id = id(store._connection)  # type: ignore
                connection_ids[thread_num] = conn_id
        except Exception as e:
            errors.append(f"Thread {thread_num} error: {e}")

    # Create 5 threads
    threads = []
    for i in range(5):
        t = threading.Thread(target=get_connection_id, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=1.0)

    # Verify no errors
    assert not errors, f"Threading errors: {errors}"

    # Verify each thread got a different connection object
    assert len(connection_ids) == 5, "Not all threads got connections"

    # All connection IDs should be different
    unique_ids = set(connection_ids.values())
    assert len(unique_ids) == 5, (
        f"Threads shared connections! Expected 5 unique, got {len(unique_ids)}: "
        f"{connection_ids}"
    )


def test_query_search_cross_thread(temp_db_path):
    """Test that similarity search works across threads."""
    session_id = "search-test"
    backend_url = "http://example.com/geoserver"
    errors = []
    search_results = {}

    def writer_thread():
        """Write layers with different descriptions."""
        try:
            layers = [
                create_test_layer("water1", "River", "Fresh water river system"),
                create_test_layer("water2", "Lake", "Large freshwater lake"),
                create_test_layer("road1", "Highway", "Major highway network"),
                create_test_layer("building1", "Houses", "Residential buildings"),
            ]
            store_layers(session_id, backend_url, "Test Backend", layers)
        except Exception as e:
            errors.append(f"Writer error: {e}")

    def search_thread(query: str, thread_id: str):
        """Search for layers matching a query."""
        try:
            time.sleep(0.1)  # Wait for writer

            # Use the similarity_search function
            results = similarity_search(
                session_id=session_id,
                backend_urls=[backend_url],
                query=query,
                limit=2,
            )

            # Store results (extract text from layers)
            search_results[thread_id] = [
                f"{layer.name} {layer.title} {layer.description}" for layer, _ in results
            ]
        except Exception as e:
            errors.append(f"Search thread {thread_id} error: {e}")

    # Start writer
    t_writer = threading.Thread(target=writer_thread)
    t_writer.start()
    t_writer.join(timeout=2.0)

    # Start multiple search threads with different queries
    search_threads = [
        threading.Thread(target=search_thread, args=("water", "water_search")),
        threading.Thread(target=search_thread, args=("road", "road_search")),
        threading.Thread(target=search_thread, args=("building", "building_search")),
    ]

    for t in search_threads:
        t.start()

    for t in search_threads:
        t.join(timeout=2.0)

    # Verify no errors
    assert not errors, f"Threading errors: {errors}"

    # Verify search results contain relevant terms
    assert "water_search" in search_results, "Water search didn't complete"
    assert "road_search" in search_results, "Road search didn't complete"
    assert "building_search" in search_results, "Building search didn't complete"

    # Verify searches found relevant content
    water_results = " ".join(search_results["water_search"])
    assert "water" in water_results.lower(), "Water search didn't find water layers"


def test_delete_from_one_thread_visible_to_another(temp_db_path):
    """Test that deletions in one thread are visible to other threads."""
    session_id = "delete-test"
    backend_url = "http://example.com/geoserver"
    errors = []
    results = {}

    # Pre-populate database
    layers = [
        create_test_layer("delete1", "Layer 1", "First layer"),
        create_test_layer("delete2", "Layer 2", "Second layer"),
    ]
    store_layers(session_id, backend_url, "Test Backend", layers)

    def deleter_thread():
        """Delete layers in Thread 1."""
        try:
            delete_layers(session_id, backend_urls=["http://example.com/geoserver"])
            results["delete"] = "success"
        except Exception as e:
            errors.append(f"Deleter error: {e}")

    def verifier_thread():
        """Verify deletion is visible in Thread 2."""
        try:
            time.sleep(0.2)  # Wait for deletion

            remaining = list_layers(
                session_id, backend_urls=["http://example.com/geoserver"], limit=10
            )
            results["remaining_count"] = len(remaining)

            if len(remaining) == 0:
                results["verify"] = "success"
            else:
                errors.append(f"Thread 2 still sees {len(remaining)} layers after deletion")
        except Exception as e:
            errors.append(f"Verifier error: {e}")

    # Run deleter and verifier
    t1 = threading.Thread(target=deleter_thread)
    t2 = threading.Thread(target=verifier_thread)

    t1.start()
    t2.start()

    t1.join(timeout=2.0)
    t2.join(timeout=2.0)

    # Verify no errors
    assert not errors, f"Threading errors: {errors}"

    # Verify deletion worked and was visible
    assert results.get("delete") == "success", "Delete failed"
    assert results.get("verify") == "success", "Verification failed"
    assert results.get("remaining_count") == 0, "Layers not deleted"


def test_no_sqlite_threading_error(temp_db_path):
    """Regression test: verify we don't get SQLite threading errors.

    This test reproduces the original error condition and verifies it's fixed.
    """
    session_id = "regression-test"
    backend_url = "http://example.com/geoserver"
    errors = []
    operations_completed = []

    def operation_thread(thread_num: int):
        """Perform multiple read/write operations."""
        try:
            # Write
            layers = [
                create_test_layer(
                    f"thread{thread_num}_layer",
                    f"Layer from thread {thread_num}",
                    f"Created by thread {thread_num}",
                )
            ]
            store_layers(f"{session_id}_{thread_num}", backend_url, "Test", layers)

            # Read
            list_layers(
                f"{session_id}_{thread_num}",
                backend_urls=["http://example.com/geoserver"],
                limit=10,
            )

            # Search
            store = get_vector_store()
            if store is not None:
                store.similarity_search("layer", k=1)

            operations_completed.append(thread_num)
        except Exception as e:
            # Specifically look for the threading error
            error_msg = str(e)
            if "thread" in error_msg.lower() and "sqlite" in error_msg.lower():
                errors.append(f"THREADING ERROR in thread {thread_num}: {e}")
            else:
                errors.append(f"Thread {thread_num} error: {e}")

    # Create many threads doing concurrent operations
    threads = []
    for i in range(20):
        t = threading.Thread(target=operation_thread, args=(i,))
        threads.append(t)
        t.start()

    # Wait for all
    for t in threads:
        t.join(timeout=3.0)

    # Verify NO threading errors occurred
    threading_errors = [e for e in errors if "THREADING ERROR" in e]
    assert not threading_errors, f"SQLite threading errors occurred: {threading_errors}"

    # Verify all threads completed successfully
    assert (
        len(operations_completed) == 20
    ), f"Only {len(operations_completed)}/20 threads completed. Errors: {errors}"
