import json
from typing import Any, Dict, List, Set, Tuple, Union

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from typing_extensions import Annotated

from models.geodata import GeoDataObject
from models.states import GeoDataAgentState, get_medium_debug_state

"""
 Utility tools to manage the GeoData State
"""


@tool
def set_result_list(
    state: Annotated[GeoDataAgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    results_title: str,
    result_tuples: list[list[str, str]],
) -> Union[Dict[str, Any], Command]:
    """Set results_title and append geodata_results, given a string and list of id and data_source_id tuples like: [['id1234','dataset1'],['id1235','dataset1']]"""
    update_dict: Dict[str, Any] = dict()
    if results_title is not None and results_title != "":
        update_dict["results_title"] = results_title
    if "result_list" in state:
        result_list = state["result_list"]
    else:
        result_list = []

    data_to_look_up: Set[Tuple[str, str]] = {
        tuple(result_tuple) for result_tuple in result_tuples or []
    }

    for geoobject in state["global_geodata"]:
        identifier: Tuple[str, str] = (geoobject.id, geoobject.data_source_id)

        if identifier in data_to_look_up:
            result_list.append(geoobject)
            data_to_look_up.remove(identifier)

    message: str
    if len(data_to_look_up) == 0:
        message = "Successfully added {len(result_tuples)} to the result list!"
    else:
        message = f"Added {len(result_tuples)-len(data_to_look_up)} geoobjects to the result list, but the following were not found in global_geodata: {json.dumps(list(data_to_look_up))} "

    return Command(
        update={
            "messages": [
                *state["messages"],
                ToolMessage(
                    name="set_result_list",
                    content=message,
                    tool_call_id=tool_call_id,
                ),
            ],
            "geodata_results": result_list,
        }
    )


@tool
def list_global_geodata(
    state: Annotated[GeoDataAgentState, InjectedState],
) -> List[Dict[str, str]]:
    """
    Lists the datasets in the global state
    """
    return [
        {
            "id": geodata.id,
            "data_source_id": geodata.data_source_id,
            "title": geodata.title,
        }
        for geodata in state["global_geodata"]
    ]


@tool
def describe_geodata_object(
    state: Annotated[GeoDataAgentState, InjectedState],
    id: str,
    data_source_id: str,
) -> List[Dict[str, str]]:
    """
    Describes a GeoData Object with the given id and data_source_id returning its description and additional properties
    """
    found_object: List[GeoDataObject] = [
        geodata
        for geodata in state["global_geodata"]
        if geodata.id == id and geodata.data_source_id == data_source_id
    ]
    return found_object


@tool
def metadata_search(
    state: Annotated[GeoDataAgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    query: str,
    prioritize_layers: bool = True,
) -> Union[Dict[str, Any], Command]:
    """
    Search for a dataset by name/title in the geodata state and return its metadata.
    This tool is useful when a user asks for information about a specific dataset they've added to the map.

    Args:
        state: The agent state containing geodata_layers and geodata_last_results
        tool_call_id: ID for this tool call
        query: Search string to match against dataset titles or names
        prioritize_layers: If True, prioritize searching in geodata_layers (datasets added to map)

    Returns detailed metadata about matching datasets including description, source, type, etc.
    """
    # Get the datasets from state
    layers = state.get("geodata_layers") or []
    last_results = state.get("geodata_last_results") or []

    # Normalize query for better matching
    query_terms = query.lower().split()

    # Search function that assigns a relevance score to each dataset
    def get_relevance_score(dataset):
        score = 0
        title = (dataset.title or "").lower()
        name = (dataset.name or "").lower()

        # Exact match gets highest score
        if query.lower() in [title, name]:
            return 100

        # Partial matches
        for term in query_terms:
            if term in title:
                score += 10
            if term in name:
                score += 8
            if dataset.description and term in dataset.description.lower():
                score += 3
            if dataset.llm_description and term in dataset.llm_description.lower():
                score += 3
            if dataset.data_source and term in dataset.data_source.lower():
                score += 2

        return score

    # Search based on priority
    search_results = []

    if prioritize_layers:
        # First search in layers (datasets added to map)
        for dataset in layers:
            score = get_relevance_score(dataset)
            if score > 0:
                search_results.append((dataset, score, "layer"))

        # Then search in last results if needed
        if len(search_results) < 2:  # Only look in last_results if we don't have good matches yet
            for dataset in last_results:
                score = get_relevance_score(dataset)
                if score > 0:
                    search_results.append((dataset, score, "result"))
    else:
        # Search in both collections without prioritization
        for dataset in layers:
            score = get_relevance_score(dataset)
            if score > 0:
                search_results.append((dataset, score, "layer"))

        for dataset in last_results:
            score = get_relevance_score(dataset)
            if score > 0:
                search_results.append((dataset, score, "result"))

    # Sort by relevance
    search_results.sort(key=lambda x: x[1], reverse=True)

    # Format results for return
    if not search_results:
        return Command(
            update={
                "messages": [
                    *state["messages"],
                    ToolMessage(
                        name="metadata_search",
                        content=f"No datasets found matching '{query}'.",
                        tool_call_id=tool_call_id,
                    ),
                ]
            }
        )

    # Format the best match(es)
    best_matches = search_results[:2]  # Get top 2 matches
    response_parts = []

    for dataset, score, source in best_matches:
        # Build a structured response with all available metadata
        metadata = {
            "title": dataset.title or dataset.name,
            "name": dataset.name,
            "description": dataset.description or "No description available",
            "llm_description": dataset.llm_description,
            "data_source": dataset.data_source,
            "data_origin": dataset.data_origin,
            "layer_type": dataset.layer_type,
            "data_type": dataset.data_type,
            "bounding_box": dataset.bounding_box,
            "added_to_map": source == "layer",
        }

        # Filter out None values
        metadata = {k: v for k, v in metadata.items() if v is not None}
        response_parts.append(metadata)

    response_message = f"Found {len(best_matches)} dataset(s) matching '{query}':\n\n"
    response_message += json.dumps(response_parts, indent=2)

    return Command(
        update={
            "messages": [
                *state["messages"],
                ToolMessage(
                    name="metadata_search",
                    content=response_message,
                    tool_call_id=tool_call_id,
                ),
            ]
        }
    )


# TODO: More tools, e.g. show/hide/change color etc. tools to manipulate existing geodataobjects


if __name__ == "__main__":
    initial_geo_state: GeoDataAgentState = get_medium_debug_state(True)

    print(
        set_result_list.run(
            state=initial_geo_state,
            tool_input={
                "state": initial_geo_state,
                "tool_call_id": "testcallid1234",
                "results_title": "Results:",
                "result_tuples": [("1512", "db_name")],
            },
        )
    )

    # print(list_global_geodata.run(state=initial_geo_state, tool_input={"state": initial_geo_state}))

    # print(describe_geodata_object.run(state=initial_geo_state, tool_input={"state": initial_geo_state, "id":"1512", "data_source_id": "db_name"}))
