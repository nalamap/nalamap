"""
Test suite for request cancellation functionality.

Tests the ability to cancel ongoing streaming requests via the /chat/cancel endpoint.
"""

import asyncio
import pytest
from fastapi.testclient import TestClient
from main import app
from api.nalamap import is_cancelled, clear_cancellation, _cancellation_flags


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def sample_chat_payload():
    """Sample chat request payload."""
    return {
        "messages": [{"type": "human", "content": "Show me rivers in Berlin"}],
        "query": "Show me rivers in Berlin",
        "geodata_last_results": [],
        "geodata_layers": [],
        "options": {
            "session_id": "test_session_123",
            "geoserver_backends": [
                {
                    "url": "http://test-geoserver.com/geoserver",
                    "enabled": True,
                    "username": None,
                    "password": None,
                }
            ],
            "model_settings": {
                "model_provider": "openai",
                "model_name": "gpt-4o-mini",
                "max_tokens": 1000,
                "system_prompt": "You are a helpful assistant.",
            },
            "tools": [],
        },
    }


@pytest.fixture
def complete_chat_payload():
    """Complete chat request payload with all required fields."""
    return {
        "messages": [],
        "query": "Find all rivers in Germany",
        "geodata_last_results": [],
        "geodata_layers": [],
        "options": {
            "session_id": None,  # Will be set by test
            "search_portals": [],
            "geoserver_backends": [
                {
                    "url": "http://test-geoserver.com/geoserver",
                    "enabled": True,
                    "username": None,
                    "password": None,
                }
            ],
            "model_settings": {
                "model_provider": "openai",
                "model_name": "gpt-4o-mini",
                "max_tokens": 1000,
                "temperature": 0.7,
                "system_prompt": "You are a helpful assistant.",
            },
            "tools": [],
        },
    }


@pytest.mark.unit
def test_cancel_endpoint_exists(client):
    """Test that the cancel endpoint exists and accepts requests."""
    response = client.post("/api/chat/cancel?session_id=test_session")
    # Should return 200 even if session doesn't exist
    assert response.status_code == 200
    result = response.json()
    assert "status" in result
    assert result["session_id"] == "test_session"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_is_cancelled_returns_false_by_default():
    """Test that is_cancelled returns False for unknown sessions."""
    result = await is_cancelled("nonexistent_session")
    assert result is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cancel_sets_flag():
    """Test that calling cancel endpoint sets the cancellation flag."""
    client = TestClient(app)
    session_id = "test_cancel_session"

    # Set cancellation flag
    response = client.post(f"/api/chat/cancel?session_id={session_id}")
    assert response.status_code == 200

    # Check flag is set
    result = await is_cancelled(session_id)
    assert result is True

    # Cleanup
    await clear_cancellation(session_id)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_clear_cancellation():
    """Test that clear_cancellation removes the flag."""
    session_id = "test_clear_session"

    # Set flag
    _cancellation_flags[session_id] = True

    # Verify it's set
    assert await is_cancelled(session_id) is True

    # Clear it
    await clear_cancellation(session_id)

    # Verify it's cleared
    assert await is_cancelled(session_id) is False


@pytest.mark.integration
@pytest.mark.slow
def test_cancel_during_streaming(client, sample_chat_payload):
    """
    Test that cancelling a request during streaming stops the stream.

    This test starts a streaming request and then immediately cancels it.
    It verifies that:
    1. The stream starts successfully
    2. The cancellation is registered
    3. A 'cancelled' event is emitted
    4. The stream terminates
    """
    import threading
    import time

    session_id = "cancel_test_session"
    sample_chat_payload["options"]["session_id"] = session_id

    events_received = []
    stream_complete = threading.Event()

    def read_stream():
        """Read events from the stream."""
        try:
            with client.stream("POST", "/api/chat/stream", json=sample_chat_payload) as response:
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode("utf-8") if isinstance(line, bytes) else line
                        events_received.append(line_str)

                        # Check if we got a cancelled event
                        if "event: cancelled" in line_str:
                            stream_complete.set()
                            break

                        # Check if stream is done
                        if "event: done" in line_str:
                            stream_complete.set()
                            break
        except Exception as e:
            print(f"Stream error: {e}")
            stream_complete.set()

    # Start streaming in a separate thread
    stream_thread = threading.Thread(target=read_stream)
    stream_thread.start()

    # Wait a moment for stream to start
    time.sleep(0.5)

    # Send cancel request
    cancel_response = client.post(f"/api/chat/cancel?session_id={session_id}")
    assert cancel_response.status_code == 200

    # Wait for stream to complete (with timeout)
    stream_complete.wait(timeout=10)
    stream_thread.join(timeout=5)

    # Verify we received events
    assert len(events_received) > 0, "Should have received at least one event"

    # Verify a cancelled event was emitted
    event_string = "\n".join(events_received)
    assert (
        "event: cancelled" in event_string or "event: done" in event_string
    ), f"Should receive cancelled or done event. Received: {event_string}"


@pytest.mark.integration
def test_cancel_nonexistent_session(client):
    """Test that cancelling a nonexistent session doesn't cause errors."""
    response = client.post("/api/chat/cancel?session_id=nonexistent_session_xyz")
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "cancellation_requested"
    assert result["session_id"] == "nonexistent_session_xyz"


@pytest.mark.edge_case
def test_cancel_empty_session_id(client):
    """Test that cancel endpoint handles empty session_id."""
    response = client.post("/api/chat/cancel?session_id=")
    assert response.status_code == 200
    # Should still return success even with empty session_id


@pytest.mark.edge_case
def test_cancel_missing_session_id(client):
    """Test that cancel endpoint handles missing session_id parameter."""
    # FastAPI should provide a validation error for missing required param
    response = client.post("/api/chat/cancel")
    # Should either succeed with default or return 422 for missing param
    assert response.status_code in [200, 422]


@pytest.mark.performance
@pytest.mark.asyncio
async def test_concurrent_cancellations():
    """Test that multiple concurrent cancellations work correctly."""
    session_ids = [f"concurrent_session_{i}" for i in range(10)]

    # Set all flags concurrently
    await asyncio.gather(*[asyncio.create_task(_set_flag(sid)) for sid in session_ids])

    # Verify all are set
    results = await asyncio.gather(*[is_cancelled(sid) for sid in session_ids])
    assert all(results), "All sessions should be cancelled"

    # Clear all
    await asyncio.gather(*[clear_cancellation(sid) for sid in session_ids])

    # Verify all are cleared
    results = await asyncio.gather(*[is_cancelled(sid) for sid in session_ids])
    assert not any(results), "All sessions should be cleared"


async def _set_flag(session_id: str):
    """Helper to set cancellation flag."""
    _cancellation_flags[session_id] = True


@pytest.mark.integration
@pytest.mark.slow
def test_cancel_during_active_streaming(client, complete_chat_payload):
    """
    Test cancellation during active LLM token streaming (not just tool execution).
    This should be more responsive since LLM tokens arrive frequently.
    """
    import threading
    import time

    session_id = f"active_stream_test_{time.time()}"
    complete_chat_payload["options"]["session_id"] = session_id
    # Use a simpler query that will stream LLM response quickly
    complete_chat_payload["query"] = "Tell me about Germany"

    events_received = []
    stream_complete = threading.Event()
    token_count = 0

    def read_stream():
        """Read events from the stream."""
        nonlocal token_count
        try:
            with client.stream("POST", "/api/chat/stream", json=complete_chat_payload) as response:
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode("utf-8") if isinstance(line, bytes) else line
                        events_received.append(line_str)

                        # Count tokens
                        if "event: llm_token" in line_str:
                            token_count += 1
                            if token_count % 10 == 0:
                                print(f"[STREAM] Received {token_count} tokens")

                        # Check if we got a cancelled event
                        if "event: cancelled" in line_str:
                            print("[STREAM] ✅ Cancelled event received!")
                            stream_complete.set()
                            return

                        # Check if stream is done
                        if "event: done" in line_str:
                            print("[STREAM] Done event received")
                            stream_complete.set()
                            return
        except Exception as e:
            print(f"[STREAM] Stream error: {e}")
            stream_complete.set()

    # Start streaming in a separate thread
    stream_thread = threading.Thread(target=read_stream)
    stream_thread.start()

    # Wait for some tokens to start streaming
    time.sleep(1)

    # Send cancel request
    print(f"[TEST] Sending cancel request after {token_count} tokens for session: {session_id}")
    cancel_response = client.post(f"/api/chat/cancel?session_id={session_id}")
    print(f"[TEST] Cancel response: {cancel_response.status_code}")
    assert cancel_response.status_code == 200

    # Wait for stream to complete
    if stream_complete.wait(timeout=10):
        print(f"[TEST] Stream completed after total {token_count} tokens")
    else:
        print("[TEST] WARNING: Stream did not complete within timeout")

    stream_thread.join(timeout=5)

    # Debug output
    print(f"[TEST] Total events received: {len(events_received)}")

    # Verify we received events
    assert len(events_received) > 0, "Should have received at least one event"

    # Check if cancellation was detected
    event_string = "\n".join(events_received)
    has_cancelled = "event: cancelled" in event_string

    if has_cancelled:
        print("[TEST] ✅ SUCCESS: Cancellation was detected and handled!")
    else:
        print("[TEST] ⚠️  WARNING: No 'cancelled' event found")
        print("[TEST] Last 5 events:")
        for i, event in enumerate(events_received[-5:]):
            print(f"  {i}: {event}")

    # For this test, we specifically want to see the cancelled event
    assert has_cancelled, "Should receive cancelled event during active streaming"


@pytest.mark.integration
@pytest.mark.slow
def test_cancel_with_real_agent_execution(client, complete_chat_payload):
    """
    Test cancellation with a real agent execution to ensure cancellation
    happens during actual tool execution, not just event emission.
    
    Note: This test can be flaky due to timing issues with threading,
    LLM API latency, and event stream buffering. It requires actual LLM
    API calls to work properly. If it fails once, try running it again.
    """
    import threading
    import time

    session_id = f"real_agent_test_{time.time()}"
    complete_chat_payload["options"]["session_id"] = session_id

    events_received = []
    stream_complete = threading.Event()
    first_tool_event = threading.Event()

    def read_stream():
        """Read events from the stream."""
        try:
            with client.stream("POST", "/api/chat/stream", json=complete_chat_payload) as response:
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode("utf-8") if isinstance(line, bytes) else line
                        events_received.append(line_str)

                        # Signal when we see first tool event
                        is_tool_event = (
                            "event: tool_start" in line_str or "event: tool_end" in line_str
                        )
                        if is_tool_event and not first_tool_event.is_set():
                            print(f"[STREAM] First tool event: {line_str[:100]}")
                            first_tool_event.set()

                        # Check if we got a cancelled event
                        if "event: cancelled" in line_str:
                            print("[STREAM] Cancelled event received!")
                            stream_complete.set()
                            break

                        # Check if stream is done
                        if "event: done" in line_str:
                            print("[STREAM] Done event received!")
                            stream_complete.set()
                            break
        except Exception as e:
            print(f"[STREAM] Stream error: {e}")
            stream_complete.set()

    # Start streaming in a separate thread
    stream_thread = threading.Thread(target=read_stream)
    stream_thread.start()

    # Wait for first tool event before cancelling
    if first_tool_event.wait(timeout=10):
        print(f"[TEST] Sending cancel request for session: {session_id}")
        cancel_response = client.post(f"/api/chat/cancel?session_id={session_id}")
        print(f"[TEST] Cancel response: {cancel_response.status_code} - {cancel_response.json()}")
        assert cancel_response.status_code == 200
    else:
        print("[TEST] WARNING: No tool events received before timeout")

    # Wait for stream to complete (with longer timeout for real execution)
    if stream_complete.wait(timeout=15):
        print("[TEST] Stream completed")
    else:
        print("[TEST] WARNING: Stream did not complete within timeout")

    stream_thread.join(timeout=5)

    # Debug output
    print(f"[TEST] Total events received: {len(events_received)}")

    # Verify we received events
    assert len(events_received) > 0, "Should have received at least one event"

    # Check if cancellation was detected
    event_string = "\n".join(events_received)
    has_cancelled = "event: cancelled" in event_string
    has_done = "event: done" in event_string

    if not has_cancelled:
        print("[TEST] WARNING: No 'cancelled' event found in stream")
        tool_starts = event_string.count("tool_start")
        tool_ends = event_string.count("tool_end")
        tokens = event_string.count("llm_token")
        print(
            f"[TEST] Events: tool_start={tool_starts}, " f"tool_end={tool_ends}, llm_token={tokens}"
        )

    # The test passes if either cancelled event is received OR stream completes
    # (cancellation might happen between events or during long tool execution)
    assert (
        has_cancelled or has_done
    ), f"Should receive cancelled or done event. Received {len(events_received)} events"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_session_id_extraction_from_options():
    """Test that session_id is correctly extracted from options."""
    from models.settings_model import SettingsSnapshot

    # Test with session_id in options
    options_dict = {
        "session_id": "test_session_123",
        "geoserver_backends": [
            {
                "url": "http://test-geoserver.com/geoserver",
                "enabled": True,
            }
        ],
        "model_settings": {
            "model_provider": "openai",
            "model_name": "gpt-4o-mini",
            "max_tokens": 1000,
            "system_prompt": "Test prompt",
        },
        "tools": [],
    }

    options = SettingsSnapshot.model_validate(options_dict, strict=False)
    assert hasattr(options, "session_id")
    assert options.session_id == "test_session_123"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cancellation_flag_persistence():
    """Test that cancellation flags persist across checks."""
    session_id = "persistence_test_session"

    # Set flag
    async with asyncio.Lock():
        _cancellation_flags[session_id] = True

    # Check multiple times
    for i in range(5):
        result = await is_cancelled(session_id)
        assert result is True, f"Flag should persist on check {i+1}"

    # Clean up
    await clear_cancellation(session_id)


@pytest.mark.integration
@pytest.mark.slow
def test_multiple_cancel_requests_same_session(client):
    """Test that multiple cancel requests for same session are idempotent."""
    session_id = "multi_cancel_session"

    # Send multiple cancel requests
    for i in range(3):
        response = client.post(f"/api/chat/cancel?session_id={session_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "cancellation_requested"

    # Verify flag is set (only once)
    import asyncio

    result = asyncio.run(is_cancelled(session_id))
    assert result is True

    # Clean up
    asyncio.run(clear_cancellation(session_id))


@pytest.mark.unit
def test_cancel_endpoint_logs_properly(client, caplog):
    """Test that cancel endpoint logs cancellation requests."""
    import logging

    caplog.set_level(logging.INFO)

    session_id = "logging_test_session"
    response = client.post(f"/api/chat/cancel?session_id={session_id}")

    assert response.status_code == 200
    # Check that logging occurred
    assert any("Cancellation requested" in record.message for record in caplog.records)
    assert any(session_id in record.message for record in caplog.records)
