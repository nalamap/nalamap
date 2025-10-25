"""
Tests for Dynamic Tool Selector.

Tests tool selection accuracy, multi-language support, different strategies,
and edge cases.
"""

import pytest
from unittest.mock import AsyncMock
from langchain_core.tools import BaseTool

from services.tool_selector import (
    DynamicToolSelector,
    SelectionStrategy,
    TOOL_METADATA,
    create_tool_selector,
)


# Mock tools for testing
class MockTool(BaseTool):
    """Mock tool for testing."""

    name: str
    description: str = "Mock tool"

    def _run(self, *args, **kwargs):
        return "mock result"

    async def _arun(self, *args, **kwargs):
        return "mock result"


@pytest.fixture
def mock_tools():
    """Create mock tools matching the metadata."""
    tools = {}
    for tool_name in TOOL_METADATA.keys():
        tools[tool_name] = MockTool(name=tool_name)
    return tools


@pytest.fixture
def mock_embeddings():
    """Create mock embeddings model."""
    embeddings = AsyncMock()

    # Mock query embedding
    embeddings.aembed_query = AsyncMock(return_value=[0.1] * 384)

    # Mock document embeddings with realistic similarities
    async def mock_embed_documents(texts):
        embeddings_list = []
        for text in texts:
            # Create different embeddings based on text content
            if "geocod" in text.lower() or "location" in text.lower():
                embeddings_list.append([0.8, 0.2] + [0.1] * 382)
            elif "geoprocess" in text.lower() or "buffer" in text.lower():
                embeddings_list.append([0.2, 0.8] + [0.1] * 382)
            elif "style" in text.lower() or "color" in text.lower():
                embeddings_list.append([0.1, 0.1, 0.8] + [0.1] * 381)
            else:
                embeddings_list.append([0.1] * 384)
        return embeddings_list

    embeddings.aembed_documents = mock_embed_documents

    return embeddings


def test_tool_metadata_completeness():
    """Test that all tool metadata is properly defined."""
    assert len(TOOL_METADATA) > 0

    for tool_name, metadata in TOOL_METADATA.items():
        assert metadata.name == tool_name
        assert len(metadata.description) > 0
        assert len(metadata.category) > 0
        assert isinstance(metadata.always_include, bool)


def test_selection_strategy_enum():
    """Test SelectionStrategy enum values."""
    assert SelectionStrategy.ALL == "all"
    assert SelectionStrategy.SEMANTIC == "semantic"
    assert SelectionStrategy.CONSERVATIVE == "conservative"
    assert SelectionStrategy.MINIMAL == "minimal"


@pytest.mark.asyncio
async def test_all_strategy_returns_all_tools(mock_tools):
    """Test that ALL strategy returns all available tools."""
    selector = DynamicToolSelector(embeddings=None, strategy=SelectionStrategy.ALL)

    selected = await selector.select_tools("Find Berlin", mock_tools)

    assert len(selected) == len(mock_tools)
    assert set(t.name for t in selected) == set(mock_tools.keys())


@pytest.mark.asyncio
async def test_semantic_selection_with_embeddings(mock_tools, mock_embeddings):
    """Test semantic tool selection with embeddings."""
    selector = DynamicToolSelector(
        embeddings=mock_embeddings,
        strategy=SelectionStrategy.SEMANTIC,
        similarity_threshold=0.5,  # Higher threshold for more selective matching
    )

    # Query about finding a location
    selected = await selector.select_tools("Find the location of Berlin, Germany", mock_tools)

    # Should select geocoding tools + core tools
    selected_names = [t.name for t in selected]

    # Core tool should always be included
    assert "metadata_search" in selected_names

    # Should have selected fewer tools with higher threshold
    assert len(selected) <= len(mock_tools)


@pytest.mark.asyncio
async def test_conservative_strategy(mock_tools, mock_embeddings):
    """Test conservative strategy includes core tools + semantic matches."""
    selector = DynamicToolSelector(
        embeddings=mock_embeddings,
        strategy=SelectionStrategy.CONSERVATIVE,
        similarity_threshold=0.5,
    )

    selected = await selector.select_tools("Show me parks", mock_tools)
    selected_names = [t.name for t in selected]

    # Core tool should be included
    assert "metadata_search" in selected_names

    # Should include at least one tool from major categories
    assert len(selected) >= 3


@pytest.mark.asyncio
async def test_minimal_strategy(mock_tools, mock_embeddings):
    """Test minimal strategy returns fewest tools."""
    selector = DynamicToolSelector(
        embeddings=mock_embeddings,
        strategy=SelectionStrategy.MINIMAL,
        similarity_threshold=0.3,
    )

    selected = await selector.select_tools("Find Berlin", mock_tools)

    # Should select minimal set (top 3 + core)
    assert len(selected) <= 5
    assert "metadata_search" in [t.name for t in selected]


@pytest.mark.asyncio
async def test_max_tools_limit(mock_tools, mock_embeddings):
    """Test max_tools parameter limits selection."""
    selector = DynamicToolSelector(
        embeddings=mock_embeddings,
        strategy=SelectionStrategy.SEMANTIC,
        similarity_threshold=0.1,  # Low threshold = more tools
        max_tools=3,
    )

    selected = await selector.select_tools("Find and style layers", mock_tools)

    # Should respect max_tools limit
    assert len(selected) <= 3


@pytest.mark.asyncio
async def test_multi_language_support(mock_tools, mock_embeddings):
    """Test that semantic selection works with different languages."""
    selector = DynamicToolSelector(
        embeddings=mock_embeddings,
        strategy=SelectionStrategy.SEMANTIC,
        similarity_threshold=0.3,
    )

    # Test with different languages (embeddings are semantic, not keyword-based)
    queries = [
        "Find Berlin, Germany",  # English
        "Finde Berlin, Deutschland",  # German
        "Trouver Berlin, Allemagne",  # French
        "Encuentra Berlín, Alemania",  # Spanish
        "ベルリンを見つける",  # Japanese
    ]

    for query in queries:
        selected = await selector.select_tools(query, mock_tools)
        # Should select tools even for non-English queries
        assert len(selected) > 0
        assert "metadata_search" in [t.name for t in selected]


@pytest.mark.asyncio
async def test_fallback_without_embeddings(mock_tools):
    """Test fallback to ALL strategy when embeddings not available."""
    selector = DynamicToolSelector(
        embeddings=None,  # No embeddings
        strategy=SelectionStrategy.SEMANTIC,
    )

    selected = await selector.select_tools("Find Berlin", mock_tools)

    # Should fall back to returning all tools
    assert len(selected) == len(mock_tools)


@pytest.mark.asyncio
async def test_empty_query(mock_tools, mock_embeddings):
    """Test handling of empty query."""
    selector = DynamicToolSelector(
        embeddings=mock_embeddings,
        strategy=SelectionStrategy.SEMANTIC,
    )

    selected = await selector.select_tools("", mock_tools)

    # Should return some tools (at least core tools)
    assert len(selected) > 0


@pytest.mark.asyncio
async def test_core_tools_always_included(mock_tools, mock_embeddings):
    """Test that core tools are always included regardless of query."""
    selector = DynamicToolSelector(
        embeddings=mock_embeddings,
        strategy=SelectionStrategy.SEMANTIC,
        similarity_threshold=0.9,  # Very high threshold
    )

    selected = await selector.select_tools("Random query", mock_tools)
    selected_names = [t.name for t in selected]

    # Core tools should always be present
    core_tools = [name for name, metadata in TOOL_METADATA.items() if metadata.always_include]

    for core_tool in core_tools:
        if core_tool in mock_tools:
            assert core_tool in selected_names


@pytest.mark.asyncio
async def test_cosine_similarity_calculation(mock_embeddings):
    """Test cosine similarity calculation."""
    selector = DynamicToolSelector(embeddings=mock_embeddings)

    vec1 = [1.0, 0.0, 0.0]
    vec2 = [1.0, 0.0, 0.0]
    similarity = selector._cosine_similarity(vec1, vec2)
    assert similarity == pytest.approx(1.0)

    vec3 = [1.0, 0.0, 0.0]
    vec4 = [0.0, 1.0, 0.0]
    similarity = selector._cosine_similarity(vec3, vec4)
    assert similarity == pytest.approx(0.0)


def test_create_tool_selector_factory():
    """Test create_tool_selector factory function."""
    selector = create_tool_selector(
        embeddings=None,
        strategy="conservative",
        similarity_threshold=0.5,
        max_tools=5,
    )

    assert isinstance(selector, DynamicToolSelector)
    assert selector.strategy == SelectionStrategy.CONSERVATIVE
    assert selector.similarity_threshold == 0.5
    assert selector.max_tools == 5


def test_create_tool_selector_invalid_strategy():
    """Test create_tool_selector with invalid strategy."""
    selector = create_tool_selector(embeddings=None, strategy="invalid_strategy")

    # Should fall back to CONSERVATIVE
    assert selector.strategy == SelectionStrategy.CONSERVATIVE


def test_get_tool_categories():
    """Test get_tool_categories method."""
    selector = DynamicToolSelector()
    categories = selector.get_tool_categories()

    assert isinstance(categories, dict)
    assert len(categories) > 0

    # Check specific categories exist
    assert "geocoding" in categories
    assert "geoprocessing" in categories
    assert "styling" in categories

    # Check tools are properly categorized
    for category, tool_names in categories.items():
        assert len(tool_names) > 0
        for tool_name in tool_names:
            assert TOOL_METADATA[tool_name].category == category


@pytest.mark.asyncio
async def test_embedding_caching(mock_tools, mock_embeddings):
    """Test that tool embeddings are cached."""
    selector = DynamicToolSelector(embeddings=mock_embeddings)

    # First call should compute embeddings
    await selector.select_tools("Find Berlin", mock_tools)
    assert selector._tool_embeddings_cache is not None

    # Second call should use cache
    cache_before = selector._tool_embeddings_cache
    await selector.select_tools("Another query", mock_tools)
    cache_after = selector._tool_embeddings_cache

    # Cache should be the same object (not recomputed)
    assert cache_before is cache_after


@pytest.mark.asyncio
async def test_geocoding_query_selects_geocoding_tools(mock_tools, mock_embeddings):
    """Test that geocoding queries select geocoding tools."""
    selector = DynamicToolSelector(
        embeddings=mock_embeddings,
        strategy=SelectionStrategy.SEMANTIC,
        similarity_threshold=0.3,
    )

    queries = [
        "Find the location of Paris",
        "Where is Tokyo?",
        "Geocode this address: 123 Main St",
        "Search for Berlin on the map",
    ]

    for query in queries:
        selected = await selector.select_tools(query, mock_tools)
        selected_names = [t.name for t in selected]

        # Should include at least one geocoding tool
        geocoding_tools = [
            "geocode_using_nominatim_to_geostate",
            "geocode_using_overpass_to_geostate",
        ]
        has_geocoding = any(tool in selected_names for tool in geocoding_tools)
        assert has_geocoding, f"No geocoding tool selected for query: {query}"


@pytest.mark.asyncio
async def test_geoprocessing_query_selects_geoprocessing_tools(mock_tools, mock_embeddings):
    """Test that geoprocessing queries select geoprocessing tools."""
    selector = DynamicToolSelector(
        embeddings=mock_embeddings,
        strategy=SelectionStrategy.SEMANTIC,
        similarity_threshold=0.3,
    )

    queries = [
        "Create a 500m buffer around the park",
        "Clip this layer by the boundary",
        "Intersect these two layers",
        "Calculate the area of this polygon",
    ]

    for query in queries:
        selected = await selector.select_tools(query, mock_tools)
        selected_names = [t.name for t in selected]

        # Should include geoprocessing tool
        assert (
            "geoprocess_tool" in selected_names
        ), f"Geoprocessing tool not selected for query: {query}"


@pytest.mark.asyncio
async def test_styling_query_selects_styling_tools(mock_tools, mock_embeddings):
    """Test that styling queries select styling tools."""
    selector = DynamicToolSelector(
        embeddings=mock_embeddings,
        strategy=SelectionStrategy.SEMANTIC,
        similarity_threshold=0.3,
    )

    queries = [
        "Change the color of this layer to blue",
        "Apply a style to the map",
        "Make this layer red",
        "Improve the visualization",
    ]

    for query in queries:
        selected = await selector.select_tools(query, mock_tools)
        selected_names = [t.name for t in selected]

        # Should include at least one styling tool
        styling_tools = [
            "style_map_layers",
            "auto_style_new_layers",
            "check_and_auto_style_layers",
            "apply_intelligent_color_scheme",
        ]
        has_styling = any(tool in selected_names for tool in styling_tools)
        assert has_styling, f"No styling tool selected for query: {query}"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_metrics_tracking(mock_tools):
    """Test that tool selector tracks performance metrics (Week 3)."""
    selector = DynamicToolSelector(embeddings=None, strategy=SelectionStrategy.ALL)

    # Initial metrics
    metrics = selector.get_metrics()
    assert metrics["total_selections"] == 0
    assert metrics["avg_tools_selected"] == 0
    assert metrics["avg_selection_time_ms"] == 0
    assert metrics["fallback_count"] == 0
    assert metrics["fallback_rate"] == 0.0

    # Perform selection
    await selector.select_tools("test query", mock_tools)

    # Check metrics updated
    metrics = selector.get_metrics()
    assert metrics["total_selections"] == 1
    assert metrics["avg_tools_selected"] > 0
    assert metrics["avg_selection_time_ms"] >= 0  # May be very fast, even 0
    assert metrics["fallback_count"] == 0  # ALL strategy doesn't use fallback
    assert "all" in metrics["strategy_usage"]

    # Multiple selections
    await selector.select_tools("another query", mock_tools)
    metrics = selector.get_metrics()
    assert metrics["total_selections"] == 2
    assert metrics["avg_tools_selected"] > 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fallback_metrics_tracking(mock_tools):
    """Test fallback tracking when embeddings unavailable (Week 3)."""
    # Selector with embeddings=None and SEMANTIC strategy should fallback
    selector = DynamicToolSelector(embeddings=None, strategy=SelectionStrategy.SEMANTIC)

    await selector.select_tools("test query", mock_tools)

    metrics = selector.get_metrics()
    assert metrics["fallback_count"] == 1
    assert metrics["fallback_rate"] == 1.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_module_level_metrics_storage(mock_tools):
    """Test that metrics are stored in module-level variable (Week 3)."""
    from services.tool_selector import get_last_selector_metrics

    # Perform selection
    selector = DynamicToolSelector(embeddings=None, strategy=SelectionStrategy.ALL)
    await selector.select_tools("test query", mock_tools)

    # Check module-level storage updated
    stored_metrics = get_last_selector_metrics()
    assert stored_metrics is not None
    assert stored_metrics["total_selections"] == 1
    assert stored_metrics["avg_tools_selected"] > 0
