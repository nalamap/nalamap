"""
Integration tests for dynamic tool selection functionality.
Tests the complete flow from API request to agent creation with filtered tools.
"""

import pytest
from httpx import AsyncClient


def get_test_payload_with_dynamic_tools(
    query: str,
    enable_dynamic_tools: bool = True,
    tool_selection_strategy: str = "conservative",
    tool_similarity_threshold: float = 0.3,
    max_tools_per_query: int | None = None,
):
    """Helper to create payload with dynamic tool settings.

    Args:
        query: The user query
        enable_dynamic_tools: Whether to enable dynamic tool selection
        tool_selection_strategy: Strategy to use (all, semantic, conservative, minimal)
        tool_similarity_threshold: Minimum similarity score (0.0-1.0)
        max_tools_per_query: Maximum tools to select (None = unlimited)
    """
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
                "system_prompt": "",
                "enable_dynamic_tools": enable_dynamic_tools,
                "tool_selection_strategy": tool_selection_strategy,
                "tool_similarity_threshold": tool_similarity_threshold,
                "max_tools_per_query": max_tools_per_query,
            },
            "tools": [],  # Empty = all tools enabled
            "tool_options": {},
            "session_id": "test-dynamic-tools-session",
        },
    }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_dynamic_tools_disabled_uses_all_tools(async_client: AsyncClient):
    """Test that disabling dynamic tools provides all available tools."""
    payload = get_test_payload_with_dynamic_tools(
        query="Show me rivers in Berlin", enable_dynamic_tools=False, tool_selection_strategy="all"
    )

    response = await async_client.post("/api/chat", json=payload, timeout=60.0)
    assert response.status_code == 200

    data = response.json()
    # API returns messages array, not a single response field
    assert "messages" in data
    assert len(data["messages"]) > 0
    # When dynamic tools disabled, agent should have access to all tools
    # This is the default behavior


@pytest.mark.asyncio
@pytest.mark.integration
async def test_dynamic_tools_semantic_strategy(async_client: AsyncClient):
    """Test semantic tool selection strategy."""
    payload = get_test_payload_with_dynamic_tools(
        query="Find all parks in Munich",
        enable_dynamic_tools=True,
        tool_selection_strategy="semantic",
        tool_similarity_threshold=0.3,
    )

    response = await async_client.post("/api/chat", json=payload, timeout=60.0)
    assert response.status_code == 200

    data = response.json()
    assert "messages" in data
    assert len(data["messages"]) > 0
    # Semantic strategy should select relevant tools based on query


@pytest.mark.asyncio
@pytest.mark.integration
async def test_dynamic_tools_conservative_strategy(async_client: AsyncClient):
    """Test conservative tool selection strategy."""
    payload = get_test_payload_with_dynamic_tools(
        query="Calculate the area of this polygon",
        enable_dynamic_tools=True,
        tool_selection_strategy="conservative",
        tool_similarity_threshold=0.3,
    )

    response = await async_client.post("/api/chat", json=payload, timeout=60.0)
    assert response.status_code == 200

    data = response.json()
    assert "messages" in data
    assert len(data["messages"]) > 0
    # Conservative strategy should include common tools + relevant ones


@pytest.mark.asyncio
@pytest.mark.integration
async def test_dynamic_tools_minimal_strategy(async_client: AsyncClient):
    """Test minimal tool selection strategy."""
    payload = get_test_payload_with_dynamic_tools(
        query="Geocode the address: Berlin, Germany",
        enable_dynamic_tools=True,
        tool_selection_strategy="minimal",
        tool_similarity_threshold=0.5,
    )

    response = await async_client.post("/api/chat", json=payload, timeout=60.0)
    assert response.status_code == 200

    data = response.json()
    assert "messages" in data
    assert len(data["messages"]) > 0
    # Minimal strategy should select only most relevant tools


@pytest.mark.asyncio
@pytest.mark.integration
async def test_dynamic_tools_all_strategy(async_client: AsyncClient):
    """Test 'all' strategy (provides all tools)."""
    payload = get_test_payload_with_dynamic_tools(
        query="Any query",
        enable_dynamic_tools=True,
        tool_selection_strategy="all",
    )

    response = await async_client.post("/api/chat", json=payload, timeout=60.0)
    assert response.status_code == 200

    data = response.json()
    assert "messages" in data
    assert len(data["messages"]) > 0
    # 'all' strategy should provide all available tools


@pytest.mark.asyncio
@pytest.mark.integration
async def test_dynamic_tools_max_tools_limit(async_client: AsyncClient):
    """Test max_tools_per_query limit."""
    payload = get_test_payload_with_dynamic_tools(
        query="Find restaurants and parks near me",
        enable_dynamic_tools=True,
        tool_selection_strategy="semantic",
        tool_similarity_threshold=0.2,
        max_tools_per_query=3,
    )

    response = await async_client.post("/api/chat", json=payload, timeout=60.0)
    assert response.status_code == 200

    data = response.json()
    assert "messages" in data
    assert len(data["messages"]) > 0
    # Agent should receive at most 3 tools


@pytest.mark.asyncio
@pytest.mark.integration
async def test_dynamic_tools_high_threshold(async_client: AsyncClient):
    """Test with high similarity threshold (more selective)."""
    payload = get_test_payload_with_dynamic_tools(
        query="Buffer this layer by 100 meters",
        enable_dynamic_tools=True,
        tool_selection_strategy="semantic",
        tool_similarity_threshold=0.7,
    )

    response = await async_client.post("/api/chat", json=payload, timeout=60.0)
    assert response.status_code == 200

    data = response.json()
    assert "messages" in data
    assert len(data["messages"]) > 0
    # High threshold should select fewer, more relevant tools


@pytest.mark.asyncio
@pytest.mark.integration
async def test_dynamic_tools_low_threshold(async_client: AsyncClient):
    """Test with low similarity threshold (more inclusive)."""
    payload = get_test_payload_with_dynamic_tools(
        query="Show me some data",
        enable_dynamic_tools=True,
        tool_selection_strategy="semantic",
        tool_similarity_threshold=0.1,
    )

    response = await async_client.post("/api/chat", json=payload, timeout=60.0)
    assert response.status_code == 200

    data = response.json()
    assert "messages" in data
    assert len(data["messages"]) > 0
    # Low threshold should include more tools


@pytest.mark.asyncio
@pytest.mark.integration
async def test_dynamic_tools_multilingual_german(async_client: AsyncClient):
    """Test dynamic tool selection with German query."""
    payload = get_test_payload_with_dynamic_tools(
        query="Zeige mir Parks in Berlin",
        enable_dynamic_tools=True,
        tool_selection_strategy="semantic",
        tool_similarity_threshold=0.3,
    )

    response = await async_client.post("/api/chat", json=payload, timeout=60.0)
    assert response.status_code == 200

    data = response.json()
    assert "messages" in data
    assert len(data["messages"]) > 0
    # Semantic selection should work with German queries


@pytest.mark.asyncio
@pytest.mark.integration
async def test_dynamic_tools_multilingual_french(async_client: AsyncClient):
    """Test dynamic tool selection with French query."""
    payload = get_test_payload_with_dynamic_tools(
        query="Calculer la surface de ce polygone",
        enable_dynamic_tools=True,
        tool_selection_strategy="semantic",
        tool_similarity_threshold=0.3,
    )

    response = await async_client.post("/api/chat", json=payload, timeout=60.0)
    assert response.status_code == 200

    data = response.json()
    assert "messages" in data
    assert len(data["messages"]) > 0
    # Semantic selection should work with French queries


@pytest.mark.asyncio
@pytest.mark.integration
async def test_dynamic_tools_geocoding_query(async_client: AsyncClient):
    """Test tool selection for geocoding-specific query."""
    payload = get_test_payload_with_dynamic_tools(
        query="Geocode: 123 Main Street, London, UK",
        enable_dynamic_tools=True,
        tool_selection_strategy="semantic",
        tool_similarity_threshold=0.4,
    )

    response = await async_client.post("/api/chat", json=payload, timeout=60.0)
    assert response.status_code == 200

    data = response.json()
    assert "messages" in data
    assert len(data["messages"]) > 0
    # Should select geocoding-related tools


@pytest.mark.asyncio
@pytest.mark.integration
async def test_dynamic_tools_geoprocessing_query(async_client: AsyncClient):
    """Test tool selection for geoprocessing-specific query."""
    payload = get_test_payload_with_dynamic_tools(
        query="Buffer the roads layer by 500 meters and clip to city boundary",
        enable_dynamic_tools=True,
        tool_selection_strategy="semantic",
        tool_similarity_threshold=0.4,
    )

    response = await async_client.post("/api/chat", json=payload, timeout=60.0)
    assert response.status_code == 200

    data = response.json()
    assert "messages" in data
    assert len(data["messages"]) > 0
    # Should select geoprocessing tools like buffer, clip


@pytest.mark.asyncio
@pytest.mark.integration
async def test_dynamic_tools_styling_query(async_client: AsyncClient):
    """Test tool selection for styling-specific query."""
    payload = get_test_payload_with_dynamic_tools(
        query="Color the layer by population density using a gradient",
        enable_dynamic_tools=True,
        tool_selection_strategy="semantic",
        tool_similarity_threshold=0.4,
    )

    response = await async_client.post("/api/chat", json=payload, timeout=60.0)
    assert response.status_code == 200

    data = response.json()
    assert "messages" in data
    assert len(data["messages"]) > 0
    # Should select styling-related tools


@pytest.mark.asyncio
@pytest.mark.integration
async def test_dynamic_tools_fallback_on_error(async_client: AsyncClient):
    """Test that system falls back to all tools if dynamic selection fails."""
    payload = get_test_payload_with_dynamic_tools(
        query="Any query",
        enable_dynamic_tools=True,
        tool_selection_strategy="semantic",
        tool_similarity_threshold=0.3,
    )

    response = await async_client.post("/api/chat", json=payload, timeout=60.0)
    assert response.status_code == 200

    data = response.json()
    assert "messages" in data
    assert len(data["messages"]) > 0
    # Should complete successfully even if tool selection has issues


@pytest.mark.asyncio
@pytest.mark.integration
async def test_dynamic_tools_empty_query(async_client: AsyncClient):
    """Test behavior with empty query string."""
    payload = get_test_payload_with_dynamic_tools(
        query="",
        enable_dynamic_tools=True,
        tool_selection_strategy="semantic",
        tool_similarity_threshold=0.3,
    )

    response = await async_client.post("/api/chat", json=payload, timeout=60.0)
    # Should handle gracefully (likely fall back to all tools)
    assert response.status_code in [200, 400]

    if response.status_code == 200:
        data = response.json()
        assert "messages" in data or "error" in data
