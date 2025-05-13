
from typing import List
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent
from langgraph.graph.graph import CompiledGraph
from services.tools.librarian_tools import query_librarian_postgis
from services.tools.geocoding import geocode_using_nominatim_to_geostate
from services.tools.geostate_management import describe_geodata_object, list_global_geodata, set_result_list
from models.states import GeoDataAgentState, get_medium_debug_state, get_minimal_debug_state
from services.ai.llm_config import get_llm


tools: List[BaseTool] = [
    set_result_list,
    list_global_geodata,
    describe_geodata_object,
    geocode_using_nominatim_to_geostate,
    query_librarian_postgis
]


def create_geo_agent() -> CompiledGraph:
    llm = get_llm()
    system_prompt = (
        "You are LaLaMap: a geospatial assistant with map capabilities. "
        "The public state contains 'geodata_last_results' with the previous results, 'geodata_layers' for the geodata selected by the user. "
        "The internal state contains 'global_geodata' which contains all geodata in the current user session and retrieved by tools. Use id and data_source_id to reference its datasets." \
        "If you fetch/find/select/process geodata, please add it to the result list in addition to the response, set 'results_title' like 'Search results' and the list 'geodata_results' for Datasets presented to the user to select from using your tool set_result_list."  
    )
    return create_react_agent(
        name="GeoAgent",
        state_schema=GeoDataAgentState,
        tools=tools,
        model=llm,
        prompt=system_prompt,
        debug=True,
        # config_schema=GeoData,
        #response_format=GeoData
    )

single_agent = create_geo_agent()

if __name__ == "__main__":
    # Initialize geodata state (e.g. Berlin) with both public and private data

    debug_tool: bool = False
    initial_geo_state: GeoDataAgentState = get_minimal_debug_state(debug_tool)

    if not debug_tool:
        # Ask the agent; private fields are kept internally but not sent to the LLM
        response = single_agent.invoke(initial_geo_state)
        print(64*"-")
        print(response["messages"])
        for message in response["messages"]:
            print(message.type, ":", message.content)
        print(64*"-")
        print(response["global_geodata"])
        #print("-"*64)
        #print(response["messages"])
    else:
        # Tool debugging
        print(describe_geodata_object.run(state=initial_geo_state, tool_input={"state": initial_geo_state, "id":"1512", "data_source_id": "db_name"}))
