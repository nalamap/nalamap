"""
Dynamic Tool Selector for NaLaMap Agent.

Intelligently selects relevant tools based on query analysis using semantic similarity
instead of keyword matching to support multiple languages.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from langchain_core.tools import BaseTool
from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)

# Module-level storage for last selector metrics (Week 3 - Performance Monitoring)
_last_selector_metrics: Optional[Dict[str, Any]] = None


def get_last_selector_metrics() -> Optional[Dict[str, Any]]:
    """
    Get metrics from the last tool selection operation.

    Returns:
        Dictionary with tool selector metrics or None if no selection occurred
    """
    return _last_selector_metrics


class SelectionStrategy(str, Enum):
    """Tool selection strategies."""

    ALL = "all"  # Load all tools (default/fallback)
    SEMANTIC = "semantic"  # Use semantic similarity with embeddings
    CONSERVATIVE = "conservative"  # Always include common tools + semantic
    MINIMAL = "minimal"  # Only most relevant tools


@dataclass
class ToolMetadata:
    """Metadata for semantic tool matching."""

    name: str
    category: str
    description: str  # Semantic description for embedding
    always_include: bool = False  # Core tools that should always be available
    usage_weight: float = 1.0  # Boost factor based on usage frequency


# Tool metadata for semantic matching
# These descriptions are semantic and work across languages
TOOL_METADATA = {
    # Geocoding & Location Tools
    "geocode_using_nominatim_to_geostate": ToolMetadata(
        name="geocode_using_nominatim_to_geostate",
        category="geocoding",
        description=(
            "Find geographic coordinates and locations by address or place name. "
            "Search for cities, countries, addresses, points of interest. "
            "Convert text location to map coordinates."
        ),
    ),
    "geocode_using_overpass_to_geostate": ToolMetadata(
        name="geocode_using_overpass_to_geostate",
        category="geocoding",
        description=(
            "Search OpenStreetMap for places, buildings, amenities, natural features. "
            "Find restaurants, shops, parks, rivers, mountains by name or type. "
            "Query geographic features from OpenStreetMap database."
        ),
    ),
    # Metadata & Discovery
    "metadata_search": ToolMetadata(
        name="metadata_search",
        category="metadata",
        description=(
            "Search for geographic datasets, layers, and data sources. "
            "Find available data portals, geospatial data catalogs. "
            "Discover what geographic data is available."
        ),
        always_include=True,  # Core tool
    ),
    # Geoprocessing & Analysis
    "geoprocess_tool": ToolMetadata(
        name="geoprocess_tool",
        category="geoprocessing",
        description=(
            "Perform spatial analysis operations: buffer, clip, intersect, union, difference. "
            "Calculate distances, areas, create zones around features. "
            "Combine, overlay, and analyze geographic layers."
        ),
    ),
    # Styling & Visualization
    "style_map_layers": ToolMetadata(
        name="style_map_layers",
        category="styling",
        description=(
            "Change colors, symbols, and appearance of map layers. "
            "Apply visual styles, themes, and color schemes to geographic data. "
            "Customize how layers are displayed on the map."
        ),
    ),
    "auto_style_new_layers": ToolMetadata(
        name="auto_style_new_layers",
        category="styling",
        description=(
            "Automatically apply appropriate visual styles to newly loaded data. "
            "Smart styling based on data type and attributes. "
            "Color and symbolize new layers intelligently."
        ),
    ),
    "check_and_auto_style_layers": ToolMetadata(
        name="check_and_auto_style_layers",
        category="styling",
        description=(
            "Verify and improve existing layer styling. "
            "Check if layers have good visual appearance and update if needed. "
            "Ensure all layers are properly styled and visible."
        ),
    ),
    "apply_intelligent_color_scheme": ToolMetadata(
        name="apply_intelligent_color_scheme",
        category="styling",
        description=(
            "Apply sophisticated color schemes and palettes to layers. "
            "Use color theory for better visualization and data distinction. "
            "Create visually harmonious and accessible map colors."
        ),
    ),
    # Attributes & Data
    "attribute_tool": ToolMetadata(
        name="attribute_tool",
        category="attributes",
        description=(
            "Work with attribute data, properties, and fields of geographic features. "
            "Query, filter, and analyze feature attributes and metadata. "
            "Access data values associated with map features."
        ),
    ),
    "attribute_tool2": ToolMetadata(
        name="attribute_tool2",
        category="attributes",
        description=(
            "Advanced attribute operations: get unique values, filter by properties. "
            "Analyze feature characteristics and data fields. "
            "Extract specific attribute information from layers."
        ),
    ),
}


class DynamicToolSelector:
    """
    Intelligently select tools based on query analysis.

    Uses semantic similarity (embeddings) instead of keyword matching
    to support multiple languages and natural language understanding.
    """

    def __init__(
        self,
        embeddings: Optional[Embeddings] = None,
        strategy: SelectionStrategy = SelectionStrategy.CONSERVATIVE,
        similarity_threshold: float = 0.3,
        max_tools: Optional[int] = None,
    ):
        """
        Initialize tool selector.

        Args:
            embeddings: Embedding model for semantic similarity (optional)
            strategy: Selection strategy to use
            similarity_threshold: Minimum similarity score for tool inclusion
            max_tools: Maximum number of tools to select (None = unlimited)
        """
        self.embeddings = embeddings
        self.strategy = strategy
        self.similarity_threshold = similarity_threshold
        self.max_tools = max_tools
        self._tool_embeddings_cache: Optional[Dict[str, List[float]]] = None

        # Metrics tracking for Week 3
        self.metrics = {
            "total_selections": 0,
            "avg_tools_selected": 0.0,
            "avg_selection_time_ms": 0.0,
            "fallback_count": 0,
            "strategy_usage": {"all": 0, "semantic": 0, "conservative": 0, "minimal": 0},
        }

    async def _compute_tool_embeddings(self) -> Dict[str, List[float]]:
        """Compute and cache embeddings for all tool descriptions."""
        if self._tool_embeddings_cache is not None:
            return self._tool_embeddings_cache

        if not self.embeddings:
            return {}

        try:
            # Gather all tool descriptions
            tool_descriptions = [metadata.description for metadata in TOOL_METADATA.values()]
            tool_names = list(TOOL_METADATA.keys())

            # Compute embeddings in batch
            embeddings_list = await self.embeddings.aembed_documents(tool_descriptions)

            # Cache results
            self._tool_embeddings_cache = dict(zip(tool_names, embeddings_list))
            logger.info(f"Computed embeddings for {len(self._tool_embeddings_cache)} tools")

            return self._tool_embeddings_cache

        except Exception as e:
            logger.error(f"Failed to compute tool embeddings: {e}")
            return {}

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        import math

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    async def _semantic_tool_selection(
        self, query: str, available_tools: Dict[str, BaseTool]
    ) -> Tuple[List[str], Dict[str, float]]:
        """
        Select tools using semantic similarity.

        Args:
            query: User query to analyze
            available_tools: Dictionary of available tools

        Returns:
            Tuple of (selected tool names, similarity scores)
        """
        if not self.embeddings:
            logger.warning("No embeddings model provided, falling back to ALL strategy")
            return list(available_tools.keys()), {}

        try:
            # Compute query embedding
            query_embedding = await self.embeddings.aembed_query(query)

            # Get tool embeddings
            tool_embeddings = await self._compute_tool_embeddings()

            if not tool_embeddings:
                return list(available_tools.keys()), {}

            # Calculate similarities
            similarities: Dict[str, float] = {}
            for tool_name, tool_embedding in tool_embeddings.items():
                if tool_name in available_tools:
                    similarity = self._cosine_similarity(query_embedding, tool_embedding)
                    similarities[tool_name] = similarity

            # Select tools above threshold
            selected_tools = [
                tool_name
                for tool_name, score in similarities.items()
                if score >= self.similarity_threshold
            ]

            # Always include core tools
            core_tools = [
                name
                for name, metadata in TOOL_METADATA.items()
                if metadata.always_include and name in available_tools
            ]
            selected_tools.extend([t for t in core_tools if t not in selected_tools])

            # Apply max_tools limit if set
            if self.max_tools and len(selected_tools) > self.max_tools:
                # Sort by similarity and take top N
                selected_tools = sorted(
                    selected_tools, key=lambda x: similarities.get(x, 0), reverse=True
                )[: self.max_tools]

            return selected_tools, similarities

        except Exception as e:
            logger.error(f"Semantic tool selection failed: {e}")
            # Fallback to all tools
            return list(available_tools.keys()), {}

    def _conservative_selection(
        self, semantic_tools: List[str], available_tools: Dict[str, BaseTool]
    ) -> List[str]:
        """
        Conservative strategy: include core tools + semantic matches.

        Args:
            semantic_tools: Tools selected by semantic analysis
            available_tools: All available tools

        Returns:
            List of tool names to include
        """
        selected = set(semantic_tools)

        # Always include core/common tools
        core_tools = [
            name
            for name, metadata in TOOL_METADATA.items()
            if metadata.always_include and name in available_tools
        ]
        selected.update(core_tools)

        # Include at least one tool from each major category
        categories_included = {TOOL_METADATA[t].category for t in selected if t in TOOL_METADATA}

        major_categories = {"geocoding", "metadata", "geoprocessing"}
        for category in major_categories - categories_included:
            # Find first available tool in this category
            for tool_name, metadata in TOOL_METADATA.items():
                if metadata.category == category and tool_name in available_tools:
                    selected.add(tool_name)
                    break

        return list(selected)

    def _minimal_selection(
        self, semantic_tools: List[str], similarities: Dict[str, float]
    ) -> List[str]:
        """
        Minimal strategy: only most relevant tools.

        Args:
            semantic_tools: Tools selected by semantic analysis
            similarities: Similarity scores for each tool

        Returns:
            List of tool names to include
        """
        # Take top 3 semantic matches + core tools
        sorted_tools = sorted(semantic_tools, key=lambda x: similarities.get(x, 0), reverse=True)

        selected = set(sorted_tools[:3])

        # Add core tools
        core_tools = [name for name, metadata in TOOL_METADATA.items() if metadata.always_include]
        selected.update(core_tools)

        return list(selected)

    async def select_tools(
        self, query: str, available_tools: Dict[str, BaseTool]
    ) -> List[BaseTool]:
        """
        Select appropriate tools based on query analysis.

        Args:
            query: User query to analyze
            available_tools: Dictionary mapping tool names to tool instances

        Returns:
            List of selected tool instances
        """
        import time

        start_time = time.time()
        used_fallback = False

        # Strategy: ALL - return all tools
        if self.strategy == SelectionStrategy.ALL:
            logger.info(f"Tool selection strategy: ALL ({len(available_tools)} tools)")
            selected_tools = list(available_tools.values())
        else:
            # Semantic analysis
            semantic_tools, similarities = await self._semantic_tool_selection(
                query, available_tools
            )

            # Check if fallback occurred (no embeddings available)
            if not similarities:
                used_fallback = True

            # Apply strategy-specific filtering
            if self.strategy == SelectionStrategy.CONSERVATIVE:
                selected_names = self._conservative_selection(semantic_tools, available_tools)
            elif self.strategy == SelectionStrategy.MINIMAL:
                selected_names = self._minimal_selection(semantic_tools, similarities)
            else:  # SEMANTIC
                selected_names = semantic_tools

            # Get tool instances
            selected_tools = [
                available_tools[name] for name in selected_names if name in available_tools
            ]

            # Log selection details
            logger.info(
                f"Tool selection for query: '{query[:50]}...'",
                extra={
                    "strategy": self.strategy,
                    "total_tools": len(available_tools),
                    "selected_tools": len(selected_tools),
                    "tool_names": selected_names,
                    "top_similarities": {
                        k: round(v, 3)
                        for k, v in sorted(similarities.items(), key=lambda x: x[1], reverse=True)[
                            :5
                        ]
                    },
                },
            )

        # Track metrics
        selection_time_ms = (time.time() - start_time) * 1000
        self._update_metrics(len(selected_tools), selection_time_ms, used_fallback)

        return selected_tools

    def _update_metrics(
        self, tools_selected: int, selection_time_ms: float, used_fallback: bool
    ) -> None:
        """Update selection metrics."""
        global _last_selector_metrics

        n = self.metrics["total_selections"]

        # Update rolling averages
        self.metrics["avg_tools_selected"] = (
            self.metrics["avg_tools_selected"] * n + tools_selected
        ) / (n + 1)
        self.metrics["avg_selection_time_ms"] = (
            self.metrics["avg_selection_time_ms"] * n + selection_time_ms
        ) / (n + 1)

        # Update counters
        self.metrics["total_selections"] += 1
        self.metrics["strategy_usage"][self.strategy.value] += 1

        if used_fallback:
            self.metrics["fallback_count"] += 1

        # Store metrics in module-level variable for later retrieval
        _last_selector_metrics = self.get_metrics()

    def get_metrics(self) -> Dict[str, Any]:
        """Get tool selection performance metrics."""
        return {
            "total_selections": self.metrics["total_selections"],
            "avg_tools_selected": round(self.metrics["avg_tools_selected"], 2),
            "avg_selection_time_ms": round(self.metrics["avg_selection_time_ms"], 2),
            "fallback_count": self.metrics["fallback_count"],
            "fallback_rate": (
                round(self.metrics["fallback_count"] / self.metrics["total_selections"], 3)
                if self.metrics["total_selections"] > 0
                else 0.0
            ),
            "strategy_usage": self.metrics["strategy_usage"].copy(),
        }

    def get_tool_categories(self) -> Dict[str, List[str]]:
        """Get tools organized by category."""
        categories: Dict[str, List[str]] = {}
        for tool_name, metadata in TOOL_METADATA.items():
            if metadata.category not in categories:
                categories[metadata.category] = []
            categories[metadata.category].append(tool_name)
        return categories


# Factory function for easy creation
def create_tool_selector(
    embeddings: Optional[Embeddings] = None,
    strategy: str = "conservative",
    similarity_threshold: float = 0.3,
    max_tools: Optional[int] = None,
) -> DynamicToolSelector:
    """
    Create a tool selector with specified configuration.

    Args:
        embeddings: Embedding model for semantic similarity
        strategy: Selection strategy ("all", "semantic", "conservative", "minimal")
        similarity_threshold: Minimum similarity score (0.0-1.0)
        max_tools: Maximum number of tools to select

    Returns:
        Configured DynamicToolSelector instance
    """
    try:
        strategy_enum = SelectionStrategy(strategy.lower())
    except ValueError:
        logger.warning(f"Invalid strategy '{strategy}', using 'conservative'")
        strategy_enum = SelectionStrategy.CONSERVATIVE

    return DynamicToolSelector(
        embeddings=embeddings,
        strategy=strategy_enum,
        similarity_threshold=similarity_threshold,
        max_tools=max_tools,
    )
