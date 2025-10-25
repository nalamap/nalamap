"""
Tests for the /api/chat/stream SSE endpoint.
"""

import pytest
import json
from httpx import AsyncClient
from httpx_sse import aconnect_sse


def get_test_payload(query: str, tools: list = None):
    """Helper function to create a properly formatted test payload.

    Args:
        query: The query string
        tools: List of tool names (strings) to enable, e.g., ["overpass_search"]
    """
    if tools is None:
        tools = []

    # Convert tool names to ToolConfig format
    tool_configs = [{"name": tool, "enabled": True} for tool in tools]

    return {
        "messages": [],
        "query": query,
        "geodata_last_results": [],
        "geodata_layers": [],
        "options": {
            "search_portals": [],
            "geoserver_backends": [],
            "model_settings": {
                "llm_provider": "openai",
                "model_provider": "openai",
                "model_name": "gpt-4o-mini",
                "max_tokens": 4096,
                "enable_performance_metrics": True,
            },
            "tools": tool_configs,
            "tool_options": {},
            "session_id": "test-streaming-session",
        },
    }


@pytest.mark.asyncio
async def test_streaming_endpoint_basic(async_client: AsyncClient):
    """Test basic streaming endpoint functionality."""
    payload = get_test_payload("What is the capital of France?")

    events_received = []

    async with aconnect_sse(
        async_client, "POST", "/api/chat/stream", json=payload, timeout=120.0
    ) as event_source:
        async for sse in event_source.aiter_sse():
            event_type = sse.event or "message"
            data = json.loads(sse.data)
            events_received.append({"type": event_type, "data": data})

            # Stop after receiving done event
            if event_type == "done":
                break

    # Verify we received events
    assert len(events_received) > 0, "Should receive at least one event"

    # Verify done event was received
    done_events = [e for e in events_received if e["type"] == "done"]
    assert len(done_events) == 1, "Should receive exactly one done event"
    assert done_events[0]["data"]["status"] == "complete"


@pytest.mark.asyncio
async def test_streaming_endpoint_with_tools(async_client: AsyncClient):
    """Test streaming endpoint with tool execution."""
    # Note: This test passes ["overpass_search"] but the actual tool usage
    # depends on the LLM deciding to call it
    payload = get_test_payload("Show me rivers in Germany", tools=["overpass_search"])

    events_received = []
    tool_events = []
    llm_tokens = []

    async with aconnect_sse(
        async_client, "POST", "/api/chat/stream", json=payload, timeout=120.0
    ) as event_source:
        async for sse in event_source.aiter_sse():
            event_type = sse.event or "message"
            data = json.loads(sse.data)
            events_received.append({"type": event_type, "data": data})

            if event_type == "tool_start" or event_type == "tool_end":
                tool_events.append({"type": event_type, "data": data})
            elif event_type == "llm_token":
                llm_tokens.append(data.get("token", ""))
            elif event_type == "done":
                break

    # Verify event sequence
    assert len(events_received) > 0, "Should receive events"

    # Check for tool events (might use overpass_search)
    # Note: This depends on LLM deciding to use tools
    if len(tool_events) > 0:
        # Verify tool_start comes before tool_end
        tool_starts = [e for e in tool_events if e["type"] == "tool_start"]
        tool_ends = [e for e in tool_events if e["type"] == "tool_end"]
        assert len(tool_starts) > 0, "Should have tool_start events"
        assert len(tool_ends) > 0, "Should have tool_end events"

    # Check for LLM tokens
    assert len(llm_tokens) > 0, "Should receive LLM tokens"

    # Verify final result
    result_events = [e for e in events_received if e["type"] == "result"]
    assert len(result_events) == 1, "Should receive exactly one result event"

    result_data = result_events[0]["data"]
    assert "messages" in result_data
    assert "geodata_results" in result_data
    assert "geodata_layers" in result_data


@pytest.mark.asyncio
async def test_streaming_endpoint_performance_metrics(async_client: AsyncClient):
    """Test that streaming endpoint includes performance metrics."""
    payload = get_test_payload("Hello")

    result_data = None

    async with aconnect_sse(
        async_client, "POST", "/api/chat/stream", json=payload, timeout=120.0
    ) as event_source:
        async for sse in event_source.aiter_sse():
            event_type = sse.event or "message"

            if event_type == "result":
                result_data = json.loads(sse.data)
            elif event_type == "done":
                break

    # Verify metrics are included
    assert result_data is not None, "Should receive result event"
    assert "metrics" in result_data, "Result should include metrics"

    metrics = result_data["metrics"]
    # Check for either old name (agent_execution_time) or new name (agent_execution)
    assert (
        "agent_execution" in metrics or "agent_execution_time" in metrics
    ), "Metrics should include agent execution time"
    assert "token_usage" in metrics
    # Note: token_usage might be 0 if using a mock/test model
    assert "total_tokens" in metrics["token_usage"]


@pytest.mark.asyncio
async def test_streaming_endpoint_error_handling(async_client: AsyncClient):
    """Test streaming endpoint error handling with invalid payload.

    Note: The streaming endpoint returns 200 OK and then sends error events
    via SSE, rather than returning 422 before starting the stream.
    """
    # Invalid payload - missing options field which is required
    payload = {
        "messages": [],
        "query": "test",
        "geodata_last_results": [],
        "geodata_layers": [],
        # Missing options field entirely
    }

    events_received = []

    async with aconnect_sse(
        async_client, "POST", "/api/chat/stream", json=payload, timeout=30.0
    ) as event_source:
        async for sse in event_source.aiter_sse():
            event_type = sse.event or "message"
            data = json.loads(sse.data)
            events_received.append({"type": event_type, "data": data})

            if event_type == "done":
                break

    # Should receive an error event due to invalid options
    error_events = [e for e in events_received if e["type"] == "error"]
    assert len(error_events) > 0, "Should receive error event for invalid payload"

    # The done event should follow the error
    done_events = [e for e in events_received if e["type"] == "done"]
    assert len(done_events) > 0, "Should receive done event after error"

    # Verify it's marked as an error
    if len(done_events) > 0:
        assert done_events[0]["data"]["status"] == "error", "Done event should have error status"


@pytest.mark.asyncio
async def test_streaming_endpoint_empty_query(async_client: AsyncClient):
    """Test streaming endpoint with empty query."""
    payload = get_test_payload("")  # Empty query

    events_received = []

    async with aconnect_sse(
        async_client, "POST", "/api/chat/stream", json=payload, timeout=120.0
    ) as event_source:
        async for sse in event_source.aiter_sse():
            event_type = sse.event or "message"
            data = json.loads(sse.data)
            events_received.append({"type": event_type, "data": data})

            if event_type == "done":
                break

    # Should still complete successfully
    assert len(events_received) > 0
    done_events = [e for e in events_received if e["type"] == "done"]
    assert len(done_events) == 1


@pytest.mark.asyncio
async def test_streaming_event_sequence(async_client: AsyncClient):
    """Test that events arrive in expected sequence."""
    payload = get_test_payload("What is Python?")

    events_received = []

    async with aconnect_sse(
        async_client, "POST", "/api/chat/stream", json=payload, timeout=120.0
    ) as event_source:
        async for sse in event_source.aiter_sse():
            event_type = sse.event or "message"
            events_received.append(event_type)

            if event_type == "done":
                break

    # Verify sequence: should have llm_token(s), then result, then done
    assert "result" in events_received, "Should have result event"
    assert "done" in events_received, "Should have done event"

    # result should come before done
    result_idx = events_received.index("result")
    done_idx = events_received.index("done")
    assert result_idx < done_idx, "result should come before done"
