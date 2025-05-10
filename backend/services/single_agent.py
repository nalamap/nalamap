
from typing import List
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent
from langgraph.graph.graph import CompiledGraph
from services.tools.geocoding import geocode_using_nominatim_to_geostate
from services.tools.geostate_management import describe_geodata_object, list_global_geodata
from models.states import GeoDataAgentState, get_medium_debug_state, get_minimal_debug_state
from services.ai.llm_config import get_llm


tools: List[BaseTool] = [
    list_global_geodata,
    describe_geodata_object,
    geocode_using_nominatim_to_geostate
]


def create_geo_agent() -> CompiledGraph:
    llm = get_llm()
    system_prompt = (
        "You are LaLaMap: a geospatial assistant with map capabilities. "
        "You only see the public state (current_geodata). "
        "The internal state contains 'global_geodata' which contains all geodata in the current user session."  
    )
    return create_react_agent(
        name="GeoAgent",
        state_schema=GeoDataAgentState,
        tools=tools,
        model=llm,
        #prompt=system_prompt,
        debug=True,
        # config_schema=GeoData,
        #response_format=GeoData
    )

if __name__ == "__main__":
    agent = create_geo_agent()
    # Initialize geodata state (e.g. Berlin) with both public and private data

    debug_tool: bool = False
    initial_geo_state: GeoDataAgentState = get_minimal_debug_state(debug_tool)

    if not debug_tool:
        # Ask the agent; private fields are kept internally but not sent to the LLM
        response = agent.invoke(initial_geo_state)
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
