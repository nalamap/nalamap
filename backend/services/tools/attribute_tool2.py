"""
Attribute Tool v2 - Simplified attribute operations for agent use.

This version provides a more straightforward interface for agents to perform
attribute operations on geospatial layers without complex planning.

Key improvements:
- Direct operation parameter instead of NL query interpretation
- Explicit, structured parameters for each operation
- Clearer error messages and validation
- Consistent return structures
- Reuses proven helper functions from attribute_tools.py
"""

import json
import logging
from typing import Any, Dict, List, Literal, Optional, Tuple, TypedDict, Union

import geopandas as gpd
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from typing_extensions import Annotated

from models.geodata import DataType
from models.states import GeoDataAgentState
from services.tools.attribute_tools import (
    _clean_layer_name,
    _generate_smart_layer_name,
    _load_gdf,
    _save_gdf_as_geojson,
    build_schema_context,
    describe_dataset_gdf,
    filter_where_gdf,
    get_attribute_values_gdf,
    list_fields_gdf,
    select_fields_gdf,
    sort_by_gdf,
    summarize_gdf,
    unique_values_gdf,
)
from services.tools.utils import match_layer_names

logger = logging.getLogger(__name__)

# Type alias for supported operations
OperationType = Literal[
    "list_fields",
    "summarize",
    "unique_values",
    "filter_where",
    "select_fields",
    "sort_by",
    "describe_dataset",
    "get_attribute_values",
]


# TypedDict for sort field specification (OpenAI function calling compatible)
class SortField(TypedDict):
    """Sort field specification."""

    field: str  # Field name to sort by
    direction: str  # Sort direction: "asc" or "desc"


@tool
def attribute_tool2(
    state: Annotated[GeoDataAgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    operation: OperationType,
    target_layer_name: Optional[str] = None,
    fields: Optional[List[str]] = None,
    field: Optional[str] = None,
    top_k: Optional[int] = None,
    where: Optional[str] = None,
    include_fields: Optional[List[str]] = None,
    exclude_fields: Optional[List[str]] = None,
    keep_geometry: bool = True,
    sort_fields: Optional[List[Dict[str, str]]] = None,
    columns: Optional[List[str]] = None,
    row_filter: Optional[str] = None,
) -> Union[Dict[str, Any], Command]:
    """
    Perform attribute operations on GeoJSON layers - Version 2 (simplified).

    This tool provides direct operations on attribute tables of geospatial layers
    without requiring natural language interpretation. Operations can return either
    chat-based summaries or create new filtered/transformed layers.

    Args:
        state: Agent state containing geodata layers and messages (auto-injected)
        tool_call_id: Tool call identifier (auto-injected)
        operation: The operation to perform. Must be one of:
            - "list_fields": List all fields/columns with types and examples
            - "summarize": Statistical summary (count, mean, min, max, quartiles) for numeric fields
            - "unique_values": Get unique values and their counts for a field
            - "filter_where": Filter features using WHERE clause (creates new layer)
            - "select_fields": Select/exclude specific columns (creates new layer)
            - "sort_by": Sort features by fields (creates new layer)
            - "describe_dataset": Get comprehensive dataset overview with suggestions
            - "get_attribute_values": Extract specific attribute values from features
        target_layer_name: Name or title of the layer to operate on (defaults to first layer)
        fields: List of field names (for "summarize" operation)
        field: Single field name (for "unique_values" operation)
        top_k: Number of top values to return (for "unique_values", default: all)
        where: WHERE clause filter expression (for "filter_where" operation)
            Examples: "value > 10", "name = 'Paris'", "type IN ('A', 'B')"
        include_fields: Fields to include (for "select_fields",
            mutually exclusive with exclude_fields)
        exclude_fields: Fields to exclude (for "select_fields",
            mutually exclusive with include_fields)
        keep_geometry: Whether to keep geometry column (for "select_fields",
            default: True)
        sort_fields: List of sort specifications (for "sort_by")
            Each item should be a dict with "field" and "direction" keys
            Example: [{"field": "population", "direction": "desc"},
                      {"field": "name", "direction": "asc"}]
        columns: Columns to retrieve (for "get_attribute_values")
        row_filter: Optional WHERE clause to filter rows first
            (for "get_attribute_values")

    Returns:
        Command with ToolMessage containing operation results.
        - For informational operations (list_fields, summarize, unique_values, describe_dataset,
          get_attribute_values): Returns JSON summary in message
        - For transformation operations (filter_where, select_fields, sort_by):
          Returns new layer in geodata_results

    Examples:
        # List all fields
        attribute_tool2(operation="list_fields", target_layer_name="rivers")

        # Get statistics
        attribute_tool2(operation="summarize", target_layer_name="cities",
                       fields=["population", "area"])

        # Filter data
        attribute_tool2(operation="filter_where", target_layer_name="countries",
                       where="gdp_per_capita > 50000")

        # Get unique categories
        attribute_tool2(operation="unique_values", target_layer_name="roads",
                       field="road_type", top_k=10)

        # Select specific columns
        attribute_tool2(operation="select_fields", target_layer_name="places",
                       include_fields=["name", "type"], keep_geometry=True)

        # Sort by field
        attribute_tool2(operation="sort_by", target_layer_name="countries",
                       sort_fields=[{"field": "population", "direction": "desc"}])

        # Get attribute values
        attribute_tool2(operation="get_attribute_values", target_layer_name="protected_areas",
                       columns=["NAME", "DESIG_ENG", "REP_AREA"],
                       row_filter="WDPA_PID = '555555'")
    """
    # Get layers from state
    layers = state.get("geodata_layers") or []
    if not layers:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        name="attribute_tool2",
                        content=(
                            "Error: No geodata layers found in state. "
                            "Add or select a layer first."
                        ),
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ]
            }
        )

    # Select target layer
    if target_layer_name:
        selected = match_layer_names(layers, [target_layer_name])
    else:
        selected = layers[:1]  # Default to first layer

    if not selected:
        avail = [{"name": layer.name, "title": layer.title} for layer in layers]
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        name="attribute_tool2",
                        content=(
                            f"Error: Target layer '{target_layer_name}' not found. "
                            f"Available layers: {json.dumps(avail)}"
                        ),
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ]
            }
        )

    layer = selected[0]

    # Validate layer type
    if layer.data_type not in (DataType.GEOJSON, DataType.UPLOADED):
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        name="attribute_tool2",
                        content=(
                            f"Error: Layer '{layer.name}' is not a GeoJSON-like dataset. "
                            f"Type: {layer.data_type}"
                        ),
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ]
            }
        )

    # Load GeoDataFrame
    try:
        gdf = _load_gdf(layer.data_link)
    except Exception as e:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        name="attribute_tool2",
                        content=f"Error loading GeoJSON into GeoDataFrame: {e}",
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ]
            }
        )

    # Execute operation
    try:
        if operation == "list_fields":
            return _handle_list_fields(gdf, layer, tool_call_id)

        elif operation == "summarize":
            return _handle_summarize(gdf, layer, fields, tool_call_id)

        elif operation == "unique_values":
            return _handle_unique_values(gdf, layer, field, top_k, tool_call_id)

        elif operation == "filter_where":
            return _handle_filter_where(gdf, layer, where, state, tool_call_id)

        elif operation == "select_fields":
            return _handle_select_fields(
                gdf, layer, include_fields, exclude_fields, keep_geometry, state, tool_call_id
            )

        elif operation == "sort_by":
            # Convert dict format to tuple format for backward compatibility
            # Handle both dict format (from OpenAI) and tuple format (from tests)
            sort_fields_tuples = None
            if sort_fields:
                sort_fields_tuples = []
                for sf in sort_fields:
                    if isinstance(sf, dict):
                        # Dict format: {"field": "name", "direction": "asc"}
                        sort_fields_tuples.append((sf.get("field", ""), sf.get("direction", "asc")))
                    elif isinstance(sf, (tuple, list)) and len(sf) == 2:
                        # Tuple/list format: ("name", "asc")
                        sort_fields_tuples.append(tuple(sf))
                    else:
                        logger.warning(f"Invalid sort field format: {sf}")
            return _handle_sort_by(gdf, layer, sort_fields_tuples, state, tool_call_id)

        elif operation == "describe_dataset":
            return _handle_describe_dataset(gdf, layer, tool_call_id)

        elif operation == "get_attribute_values":
            return _handle_get_attribute_values(gdf, layer, columns, row_filter, tool_call_id)

        else:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            name="attribute_tool2",
                            content=f"Error: Unsupported operation '{operation}'",
                            tool_call_id=tool_call_id,
                            status="error",
                        )
                    ]
                }
            )

    except Exception as e:
        logger.exception(f"Error executing attribute operation '{operation}'")
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        name="attribute_tool2",
                        content=f"Error executing operation '{operation}': {e}",
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ]
            }
        )


# =============================================================================
# Operation Handlers
# =============================================================================


def _handle_list_fields(gdf: gpd.GeoDataFrame, layer, tool_call_id: str) -> Command:
    """Handle list_fields operation."""
    result = list_fields_gdf(gdf)
    return Command(
        update={
            "messages": [
                ToolMessage(
                    name="attribute_tool2",
                    content=json.dumps(
                        {
                            "operation": "list_fields",
                            "layer": layer.name,
                            "result": result,
                        }
                    ),
                    tool_call_id=tool_call_id,
                )
            ]
        }
    )


def _handle_summarize(
    gdf: gpd.GeoDataFrame, layer, fields: Optional[List[str]], tool_call_id: str
) -> Command:
    """Handle summarize operation."""
    if not fields:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        name="attribute_tool2",
                        content=(
                            "Error: 'fields' parameter is required for summarize operation. "
                            f"Available fields: {sorted(gdf.columns.tolist())}"
                        ),
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ]
            }
        )

    # Validate fields
    missing = [f for f in fields if f not in gdf.columns]
    if missing:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        name="attribute_tool2",
                        content=(
                            f"Error: Unknown fields in summarize: {missing}. "
                            f"Available: {sorted(gdf.columns.tolist())}"
                        ),
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ]
            }
        )

    result = summarize_gdf(gdf, fields)
    return Command(
        update={
            "messages": [
                ToolMessage(
                    name="attribute_tool2",
                    content=json.dumps(
                        {
                            "operation": "summarize",
                            "layer": layer.name,
                            "result": result,
                        }
                    ),
                    tool_call_id=tool_call_id,
                )
            ]
        }
    )


def _handle_unique_values(
    gdf: gpd.GeoDataFrame,
    layer,
    field: Optional[str],
    top_k: Optional[int],
    tool_call_id: str,
) -> Command:
    """Handle unique_values operation."""
    if not field:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        name="attribute_tool2",
                        content=(
                            "Error: 'field' parameter is required for unique_values operation. "
                            f"Available fields: {sorted(gdf.columns.tolist())}"
                        ),
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ]
            }
        )

    if field not in gdf.columns:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        name="attribute_tool2",
                        content=(
                            f"Error: Field '{field}' not found. "
                            f"Available: {sorted(gdf.columns.tolist())}"
                        ),
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ]
            }
        )

    result = unique_values_gdf(gdf, field, top_k)
    return Command(
        update={
            "messages": [
                ToolMessage(
                    name="attribute_tool2",
                    content=json.dumps(
                        {
                            "operation": "unique_values",
                            "layer": layer.name,
                            "result": result,
                        }
                    ),
                    tool_call_id=tool_call_id,
                )
            ]
        }
    )


def _handle_filter_where(
    gdf: gpd.GeoDataFrame,
    layer,
    where: Optional[str],
    state: GeoDataAgentState,
    tool_call_id: str,
) -> Command:
    """Handle filter_where operation."""
    if not where:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        name="attribute_tool2",
                        content=(
                            "Error: 'where' parameter is required for filter_where operation. "
                            'Example: "population > 1000000"'
                        ),
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ]
            }
        )

    try:
        filtered_gdf, field_suggestions = filter_where_gdf(gdf, where)
    except Exception as e:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        name="attribute_tool2",
                        content=(
                            f"Error parsing/applying WHERE clause: {e}. "
                            f"Available fields: {sorted(gdf.columns.tolist())}"
                        ),
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ]
            }
        )

    # Check if filter returned any features
    if len(filtered_gdf) == 0:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        name="attribute_tool2",
                        content=(
                            f"Filter applied to '{layer.name}' but no features matched "
                            f"the condition: {where}. "
                            f"Original layer had {len(gdf)} features."
                        ),
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )

    # Save filtered result as new layer
    source_name = _clean_layer_name(layer.title or layer.name)

    # Generate smart layer name using LLM
    title = _generate_smart_layer_name(
        source_layer_name=source_name,
        operation="filtered",
        gdf=filtered_gdf,
        operation_details=where,
        state=state,
    )

    # Create detailed description
    detailed_desc = (
        f"Filtered features from '{layer.title or layer.name}' using condition: "
        f"{where}. Result contains {len(filtered_gdf)} feature(s) out of "
        f"{len(gdf)} original features."
    )

    obj = _save_gdf_as_geojson(
        filtered_gdf, title, keep_geometry=True, detailed_description=detailed_desc
    )
    new_results = (state.get("geodata_results") or []) + [obj]

    # Build actionable layer info
    actionable_layer_info = {
        "name": obj.name,
        "title": obj.title,
        "id": obj.id,
        "data_source_id": obj.data_source_id,
        "feature_count": len(filtered_gdf),
        "original_count": len(gdf),
        "filter": where,
    }

    # Add field suggestion info if fuzzy matching was used
    suggestion_info = ""
    if field_suggestions:
        suggestion_info = "\n\nNote: Field name corrections were applied:\n" + "\n".join(
            [f"  - '{req}' → '{actual}'" for req, actual in field_suggestions.items()]
        )

    # Provide user guidance
    tool_message_content = (
        f"Successfully filtered '{layer.name}' using condition: {where}. "
        f"Result contains {len(filtered_gdf)} feature(s) out of {len(gdf)} original features. "
        f"New layer '{obj.title}' created and stored in geodata_results. "
        f"Actionable layer details: {json.dumps(actionable_layer_info)}. "
        f"{suggestion_info}\n"
        "The filtered layer is now available in the result list and can be "
        "selected by the user to be added to the map."
    )

    return Command(
        update={
            "messages": [
                ToolMessage(
                    name="attribute_tool2",
                    content=tool_message_content,
                    tool_call_id=tool_call_id,
                )
            ],
            "geodata_results": new_results,
        }
    )


def _handle_select_fields(
    gdf: gpd.GeoDataFrame,
    layer,
    include_fields: Optional[List[str]],
    exclude_fields: Optional[List[str]],
    keep_geometry: bool,
    state: GeoDataAgentState,
    tool_call_id: str,
) -> Command:
    """Handle select_fields operation."""
    if not include_fields and not exclude_fields:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        name="attribute_tool2",
                        content=(
                            "Error: Either 'include_fields' or 'exclude_fields' must be provided. "
                            f"Available fields: {sorted(gdf.columns.tolist())}"
                        ),
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ]
            }
        )

    # Validate fields
    fields_to_check = (include_fields or []) + (exclude_fields or [])
    missing = [f for f in fields_to_check if f not in gdf.columns]
    if missing:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        name="attribute_tool2",
                        content=(
                            f"Error: Unknown fields in select_fields: {missing}. "
                            f"Available: {sorted(gdf.columns.tolist())}"
                        ),
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ]
            }
        )

    # Perform selection
    result_gdf = select_fields_gdf(
        gdf, include=include_fields, exclude=exclude_fields, keep_geometry=keep_geometry
    )

    # Save as new layer
    source_name = _clean_layer_name(layer.title or layer.name)

    # Generate operation details for smart naming
    op_details = []
    if include_fields:
        op_details.append(f"included: {', '.join(include_fields[:3])}")
    if exclude_fields:
        op_details.append(f"excluded: {', '.join(exclude_fields[:3])}")
    operation_details = "; ".join(op_details) if op_details else None

    # Generate smart layer name using LLM
    title = _generate_smart_layer_name(
        source_layer_name=source_name,
        operation="selected fields",
        gdf=result_gdf,
        operation_details=operation_details,
        state=state,
    )

    # Create detailed description
    field_info = []
    if include_fields:
        field_info.append(f"included fields: {', '.join(include_fields)}")
    if exclude_fields:
        field_info.append(f"excluded fields: {', '.join(exclude_fields)}")
    detailed_desc = (
        f"Selected fields from '{layer.title or layer.name}'. "
        f"{'; '.join(field_info) if field_info else 'Field selection applied'}. "
        f"Result has {len(result_gdf.columns)} columns."
    )

    obj = _save_gdf_as_geojson(
        result_gdf, title, keep_geometry=keep_geometry, detailed_description=detailed_desc
    )
    new_results = (state.get("geodata_results") or []) + [obj]

    return Command(
        update={
            "messages": [
                ToolMessage(
                    name="attribute_tool2",
                    content=f"Field selection applied. New layer: {obj.title}",
                    tool_call_id=tool_call_id,
                )
            ],
            "geodata_results": new_results,
        }
    )


def _handle_sort_by(
    gdf: gpd.GeoDataFrame,
    layer,
    sort_fields: Optional[List[Tuple[str, str]]],
    state: GeoDataAgentState,
    tool_call_id: str,
) -> Command:
    """Handle sort_by operation."""
    if not sort_fields:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        name="attribute_tool2",
                        content=(
                            "Error: 'sort_fields' parameter is required for sort_by operation. "
                            'Example: [("population", "desc"), ("name", "asc")]'
                        ),
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ]
            }
        )

    # Validate fields
    field_names = [f[0] for f in sort_fields]
    missing = [f for f in field_names if f not in gdf.columns]
    if missing:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        name="attribute_tool2",
                        content=(
                            f"Error: Unknown fields in sort_by: {missing}. "
                            f"Available: {sorted(gdf.columns.tolist())}"
                        ),
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ]
            }
        )

    # Perform sorting
    sorted_gdf = sort_by_gdf(gdf, sort_fields)

    # Save as new layer
    source_name = _clean_layer_name(layer.title or layer.name)

    # Generate smart layer name using LLM
    sort_desc_short = ", ".join([f"{fld} {order}" for fld, order in sort_fields[:2]])
    title = _generate_smart_layer_name(
        source_layer_name=source_name,
        operation="sorted",
        gdf=sorted_gdf,
        operation_details=sort_desc_short,
        state=state,
    )

    # Create detailed description
    sort_desc = ", ".join([f"{fld} {order}" for fld, order in sort_fields])
    detailed_desc = (
        f"Sorted '{layer.title or layer.name}' by: {sort_desc}. "
        f"Result contains {len(sorted_gdf)} features in sorted order."
    )

    obj = _save_gdf_as_geojson(
        sorted_gdf, title, keep_geometry=True, detailed_description=detailed_desc
    )
    new_results = (state.get("geodata_results") or []) + [obj]

    return Command(
        update={
            "messages": [
                ToolMessage(
                    name="attribute_tool2",
                    content=f"Sorting applied. New layer: {obj.title}",
                    tool_call_id=tool_call_id,
                )
            ],
            "geodata_results": new_results,
        }
    )


def _handle_describe_dataset(gdf: gpd.GeoDataFrame, layer, tool_call_id: str) -> Command:
    """Handle describe_dataset operation."""
    schema_ctx = build_schema_context(gdf)
    result = describe_dataset_gdf(gdf, schema_ctx)

    return Command(
        update={
            "messages": [
                ToolMessage(
                    name="attribute_tool2",
                    content=json.dumps(
                        {
                            "operation": "describe_dataset",
                            "layer": layer.name,
                            "result": result,
                        }
                    ),
                    tool_call_id=tool_call_id,
                )
            ]
        }
    )


def _handle_get_attribute_values(
    gdf: gpd.GeoDataFrame,
    layer,
    columns: Optional[List[str]],
    row_filter: Optional[str],
    tool_call_id: str,
) -> Command:
    """Handle get_attribute_values operation."""
    if not columns:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        name="attribute_tool2",
                        content=(
                            "Error: 'columns' parameter is required for "
                            "get_attribute_values operation. "
                            f"Available fields: {sorted(gdf.columns.tolist())}"
                        ),
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ]
            }
        )

    try:
        result = get_attribute_values_gdf(gdf, columns, row_filter)
    except Exception as e:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        name="attribute_tool2",
                        content=(
                            f"Error retrieving attribute values: {e}. "
                            f"Available fields: {sorted(gdf.columns.tolist())}"
                        ),
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ]
            }
        )

    # Check for errors in result
    if result.get("error"):
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        name="attribute_tool2",
                        content=f"Error: {result['error']}",
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ]
            }
        )

    return Command(
        update={
            "messages": [
                ToolMessage(
                    name="attribute_tool2",
                    content=json.dumps(
                        {
                            "operation": "get_attribute_values",
                            "layer": layer.name,
                            "result": result,
                        }
                    ),
                    tool_call_id=tool_call_id,
                )
            ]
        }
    )
