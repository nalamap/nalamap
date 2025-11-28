from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from langchain_core.messages import HumanMessage
from langgraph.graph import MessagesState
from pydantic import Field
from typing_extensions import Annotated

from models.settings_model import SettingsSnapshot

from .geodata import GeoDataObject, mock_geodata_objects


# =============================================================================
# REDUCER FUNCTIONS FOR CONCURRENT TOOL EXECUTION
# =============================================================================
# These reducers allow multiple tools running in parallel to update the same
# state fields without conflicts. They merge results intelligently and handle
# deduplication based on (id, data_source_id) tuples.


def reduce_geodata_last_results(
    current: Optional[List[GeoDataObject]], new: Optional[List[GeoDataObject]]
) -> List[GeoDataObject]:
    """
    Reducer for geodata_last_results that merges results from concurrent tools.
    Combines results into a single list, deduplicating by (id, data_source_id).
    """
    if new is None:
        return current if current is not None else []
    if current is None:
        return new if new is not None else []

    existing_ids = {(g.id, g.data_source_id) for g in current}
    merged = list(current)
    for item in new:
        if (item.id, item.data_source_id) not in existing_ids:
            merged.append(item)
            existing_ids.add((item.id, item.data_source_id))
    return merged


def reduce_geodata_results(
    current: Optional[List[GeoDataObject]], new: Optional[List[GeoDataObject]]
) -> List[GeoDataObject]:
    """
    Reducer for geodata_results - same logic as reduce_geodata_last_results.
    Combines results into a single list, deduplicating by (id, data_source_id).
    """
    if new is None:
        return current if current is not None else []
    if current is None:
        return new if new is not None else []

    existing_ids = {(g.id, g.data_source_id) for g in current}
    merged = list(current)
    for item in new:
        if (item.id, item.data_source_id) not in existing_ids:
            merged.append(item)
            existing_ids.add((item.id, item.data_source_id))
    return merged


def reduce_geodata_layers(
    current: Optional[List[GeoDataObject]], new: Optional[List[GeoDataObject]]
) -> List[GeoDataObject]:
    """
    Reducer for geodata_layers that handles concurrent layer updates.
    Updates existing layers by ID and appends new ones.
    """
    if new is None:
        return current if current is not None else []
    if current is None:
        return new if new is not None else []

    new_layers_by_id = {(g.id, g.data_source_id): g for g in new}
    result = []
    seen_ids = set()

    for layer in current:
        layer_id = (layer.id, layer.data_source_id)
        if layer_id in new_layers_by_id:
            result.append(new_layers_by_id[layer_id])
        else:
            result.append(layer)
        seen_ids.add(layer_id)

    for layer in new:
        layer_id = (layer.id, layer.data_source_id)
        if layer_id not in seen_ids:
            result.append(layer)

    return result


def reduce_results_title(current: Optional[str], new: Optional[str]) -> str:
    """Reducer for results_title - takes first non-empty value."""
    if new is not None and new.strip():
        return new
    if current is not None and current.strip():
        return current
    return ""


@dataclass
class DataState(MessagesState):
    geodata: List[GeoDataObject] = field(default_factory=list)


class GeoDataAgentState(MessagesState):
    """State with parallel execution support via reducer functions.

    The reducer functions (reduce_geodata_*) allow multiple tools running in parallel
    to update the same state fields without conflicts by intelligently merging results.
    """

    # TODO: maybe use references?
    results_title: Annotated[str, reduce_results_title] = Field(
        default="",
        description="Title for the geodata response in 'geodata_results'",
    )
    geodata_last_results: Annotated[List[GeoDataObject], reduce_geodata_last_results] = Field(
        default_factory=list, exclude=False, validate_default=False
    )
    geodata_results: Annotated[List[GeoDataObject], reduce_geodata_results] = Field(
        default_factory=list, exclude=True, validate_default=False
    )
    geodata_layers: Annotated[List[GeoDataObject], reduce_geodata_layers] = Field(
        default_factory=list, exclude=False, validate_default=False
    )
    options: Optional[Union[Dict[str, Any], SettingsSnapshot]] = Field(
        default_factory=dict, exclude=True, validate_default=False
    )

    # Required by create_react_agent
    remaining_steps: Optional[int] = Field(
        default=10, description="Number of remaining steps for the agent"
    )

    # --- Internal-only fields (excluded from LLM prompt) ---
    # global_geodata: Optional[List[GeoDataObject]] = Field(
    #     default_factory=list, exclude=True, validate_default=False
    # )


def get_minimal_debug_state(tool_call: bool = False) -> GeoDataAgentState:
    initial_geo_state: GeoDataAgentState = GeoDataAgentState()
    initial_geo_state["messages"] = [HumanMessage("Please show Frankfurt")]
    # initial_geo_state["global_geodata"] = []
    initial_geo_state["geodata_last_results"] = []
    initial_geo_state["geodata_results"] = []
    initial_geo_state["geodata_layers"] = []
    initial_geo_state["results_title"] = ""
    initial_geo_state["options"] = {}
    if tool_call:
        initial_geo_state["is_last_step"] = False
        initial_geo_state["remaining_steps"] = 5
    return initial_geo_state


def get_medium_debug_state(tool_call: bool = False) -> GeoDataAgentState:
    initial_geo_state: GeoDataAgentState = GeoDataAgentState()
    initial_geo_state["messages"] = [HumanMessage("Show layers for rivers in egypt")]
    # initial_geo_state["global_geodata"] = mock_geodata_objects()[0:2]
    initial_geo_state["geodata_last_results"] = mock_geodata_objects()[0:2]
    initial_geo_state["geodata_results"] = []
    initial_geo_state["geodata_layers"] = []
    initial_geo_state["results_title"] = ""
    initial_geo_state["options"] = {}
    if tool_call:
        initial_geo_state["is_last_step"] = False
        initial_geo_state["remaining_steps"] = 5
    return initial_geo_state
