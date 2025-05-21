import json
from typing_extensions import Annotated
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langchain_core.tools.base import InjectedToolCallId
from models.states import GeoDataAgentState, get_medium_debug_state
from models.geodata import GeoDataIdentifier, GeoDataObject
from langchain_core.messages import ToolMessage
from pydantic import BaseModel, Field
"""
 Utility tools to manage the GeoData State
"""


@tool
def set_result_list(state: Annotated[GeoDataAgentState, InjectedState], tool_call_id: Annotated[str, InjectedToolCallId],  results_title: str, result_tuples: list[list[str, str]]) -> Union[Dict[str, Any], Command]:
    """Set results_title and append geodata_results, given a string and list of id and data_source_id tuples like: [['id1234','dataset1'],['id1235','dataset1']]"""
    update_dict: Dict[str, Any] = dict()
    if results_title is not None and results_title != "":
        update_dict["results_title"] = results_title
    if 'result_list' in state:
        result_list = state['result_list']
    else:
        result_list = []

    data_to_look_up: Set[Tuple[str, str]] = { tuple(result_tuple) for result_tuple in result_tuples or [] }

    for geoobject in state['global_geodata']:
        identifier: Tuple[str, str] = (geoobject.id, geoobject.data_source_id)

        if identifier in data_to_look_up:
            result_list.append(geoobject)
            data_to_look_up.remove(identifier)
    
    message: str
    if len(data_to_look_up) == 0:
        message = f"Successfully added {len(result_tuples)} to the result list!"
    else:
        message = f"Added {len(result_tuples)-len(data_to_look_up)} geoobjects to the result list, but the following were not found in global_geodata: {json.dumps(list(data_to_look_up))} "

    return Command(update={
                    "messages": [
                        *state["messages"], 
                        ToolMessage(name="set_result_list", content=message, tool_call_id=tool_call_id )
                        ],
                    "geodata_results": result_list
                })

@tool
def list_global_geodata(state: Annotated[GeoDataAgentState, InjectedState]) -> List[Dict[str, str]]:
    """
    Lists the datasets in the global state
    """
    return [{"id": geodata.id, "data_source_id": geodata.data_source_id, "title": geodata.title} for geodata in state["global_geodata"]]


@tool
def describe_geodata_object(state: Annotated[GeoDataAgentState, InjectedState], id: str, data_source_id: str) -> List[Dict[str, str]]:
    """
    Describes a GeoData Object with the given id and data_source_id returning its description and additional properties
    """
    found_object: List[GeoDataObject] = [geodata for geodata in state["global_geodata"] if geodata.id == id and geodata.data_source_id == data_source_id]
    return found_object


# TODO: More tools, e.g. show/hide/change color etc. tools to manipulate existing geodataobjects


if __name__ == "__main__":
    initial_geo_state: GeoDataAgentState = get_medium_debug_state(True)

    print(set_result_list.run(state=initial_geo_state, tool_input={"state": initial_geo_state, 'tool_call_id': 'testcallid1234', 'results_title': 'Results:', 'result_tuples': [('1512', 'db_name')]}))

    # print(list_global_geodata.run(state=initial_geo_state, tool_input={"state": initial_geo_state}))

    # print(describe_geodata_object.run(state=initial_geo_state, tool_input={"state": initial_geo_state, "id":"1512", "data_source_id": "db_name"}))
