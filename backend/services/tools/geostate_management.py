from typing_extensions import Annotated
from typing import Dict, List
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from models.states import GeoDataAgentState, get_medium_debug_state
from models.geodata import GeoDataObject
"""
 Utility tools to manage the GeoData State
"""

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

    print(list_global_geodata.run(state=initial_geo_state, tool_input={"state": initial_geo_state}))

    print(describe_geodata_object.run(state=initial_geo_state, tool_input={"state": initial_geo_state, "id":"1512", "data_source_id": "db_name"}))
