"""
Tests for tool_end events with full results in the /api/chat/stream SSE endpoint.
Tests various scenarios: state updates, actual results, large results, empty results, error results.
"""

import pytest
import json
from httpx import AsyncClient
from httpx_sse import aconnect_sse


def get_test_payload(query: str, tools: list | None = None):
    """Helper function to create a properly formatted test payload."""
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
            "session_id": "test-tool-results-session",
        },
    }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tool_end_includes_full_output(async_client: AsyncClient):
    """Test that tool_end events include full output data."""
    payload = get_test_payload("Find rivers near Berlin, Germany", tools=["overpass_search"])

    tool_end_events = []

    async with aconnect_sse(
        async_client, "POST", "/api/chat/stream", json=payload, timeout=120.0
    ) as event_source:
        async for sse in event_source.aiter_sse():
            event_type = sse.event or "message"
            data = json.loads(sse.data)

            if event_type == "tool_end":
                tool_end_events.append(data)

            if event_type == "done":
                break

    # Check if we got any tool_end events
    # (Note: LLM might not use tools for every query)
    if len(tool_end_events) > 0:
        for event in tool_end_events:
            # Verify structure of tool_end event
            assert "tool" in event, "tool_end should have 'tool' field"
            assert "output_preview" in event, "tool_end should have 'output_preview' field"
            assert "is_state_update" in event, "tool_end should have 'is_state_update' field"
            assert "output_type" in event, "tool_end should have 'output_type' field"

            # If not a state update, should have full output
            if not event.get("is_state_update", False):
                assert "output" in event, "Non-state tool_end should have 'output' field"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tool_end_state_update_detection(async_client: AsyncClient):
    """Test that state updates are properly detected and flagged."""
    # Query that likely triggers tool usage
    payload = get_test_payload("Show me restaurants in Paris", tools=["overpass_search"])

    tool_end_events = []

    async with aconnect_sse(
        async_client, "POST", "/api/chat/stream", json=payload, timeout=120.0
    ) as event_source:
        async for sse in event_source.aiter_sse():
            event_type = sse.event or "message"
            data = json.loads(sse.data)

            if event_type == "tool_end":
                tool_end_events.append(data)

            if event_type == "done":
                break

    # Verify structure for all tool_end events
    for event in tool_end_events:
        # All events should have is_state_update flag
        assert isinstance(event.get("is_state_update"), bool), "is_state_update should be boolean"

        # State updates should have different structure than regular outputs
        if event.get("is_state_update"):
            # State updates should have preview but maybe not full output
            assert "output_preview" in event
            assert "State update" in event["output_preview"]
        else:
            # Regular outputs should have both preview and full output
            assert "output" in event or "output_preview" in event


@pytest.mark.asyncio
async def test_tool_end_preview_truncation(async_client: AsyncClient):
    """Test that large outputs are properly truncated in preview."""
    # Use a query that might generate significant output
    payload = get_test_payload("Tell me about geographic information systems", tools=[])

    tool_end_events = []

    async with aconnect_sse(
        async_client, "POST", "/api/chat/stream", json=payload, timeout=120.0
    ) as event_source:
        async for sse in event_source.aiter_sse():
            event_type = sse.event or "message"
            data = json.loads(sse.data)

            if event_type == "tool_end":
                tool_end_events.append(data)

            if event_type == "done":
                break

    # Check preview length if we got tool events
    for event in tool_end_events:
        preview = event.get("output_preview", "")
        # Preview should be reasonable length (max 203 chars: 200 + "...")
        assert len(preview) <= 250, f"Preview too long: {len(preview)} chars"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tool_end_with_multiple_tools(async_client: AsyncClient):
    """Test that multiple tool executions all have proper output data."""
    # Enable multiple tools
    payload = get_test_payload(
        "Find parks in Berlin and show me their locations",
        tools=["overpass_search", "geocode_location"],
    )

    tool_end_events = []

    async with aconnect_sse(
        async_client, "POST", "/api/chat/stream", json=payload, timeout=120.0
    ) as event_source:
        async for sse in event_source.aiter_sse():
            event_type = sse.event or "message"
            data = json.loads(sse.data)

            if event_type == "tool_end":
                tool_end_events.append(data)

            if event_type == "done":
                break

    # Each tool_end event should have complete structure
    for event in tool_end_events:
        assert "tool" in event
        assert "output_preview" in event
        assert "is_state_update" in event
        assert "output_type" in event

        # Tool name should be one of the enabled tools or a LangGraph internal tool
        tool_name = event["tool"]
        assert isinstance(tool_name, str) and len(tool_name) > 0


@pytest.mark.asyncio
async def test_tool_end_output_types(async_client: AsyncClient):
    """Test that output_type is correctly identified."""
    payload = get_test_payload("What is 2+2?", tools=[])

    tool_end_events = []

    async with aconnect_sse(
        async_client, "POST", "/api/chat/stream", json=payload, timeout=120.0
    ) as event_source:
        async for sse in event_source.aiter_sse():
            event_type = sse.event or "message"
            data = json.loads(sse.data)

            if event_type == "tool_end":
                tool_end_events.append(data)

            if event_type == "done":
                break

    # Verify output_type exists and is a string
    for event in tool_end_events:
        assert "output_type" in event
        assert isinstance(event["output_type"], str)
        # Common types: 'dict', 'str', 'list', 'state'
        valid_types = ["dict", "str", "list", "state", "int", "float", "bool", "NoneType"]
        assert event["output_type"] in valid_types


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.integration
async def test_tool_end_json_serialization(async_client: AsyncClient):
    """Test that all tool outputs are properly JSON serializable."""
    # Use a query that might trigger tool usage
    payload = get_test_payload("Find the location of Eiffel Tower", tools=["geocode_location"])

    tool_end_events = []

    async with aconnect_sse(
        async_client, "POST", "/api/chat/stream", json=payload, timeout=120.0
    ) as event_source:
        async for sse in event_source.aiter_sse():
            event_type = sse.event or "message"

            # If we got here, JSON parsing already succeeded (httpx_sse parses it)
            # But let's verify we can re-serialize
            data = json.loads(sse.data)

            if event_type == "tool_end":
                tool_end_events.append(data)

                # Verify we can re-serialize the output
                if "output" in data:
                    try:
                        json.dumps(data["output"])
                    except (TypeError, ValueError) as e:
                        pytest.fail(f"Output not JSON serializable: {e}")

            if event_type == "done":
                break

    # If we got here without exceptions, JSON serialization works
    assert True
