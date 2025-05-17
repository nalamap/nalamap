from typing import List
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent
from langgraph.graph.graph import CompiledGraph
from services.tools.librarian_tools import query_librarian_postgis
from services.tools.geoprocess_tools import geoprocess_tool
from services.tools.geocoding import geocode_using_nominatim_to_geostate, geocode_using_geonames
from services.tools.geostate_management import describe_geodata_object, list_global_geodata, set_result_list
from models.states import GeoDataAgentState, get_medium_debug_state, get_minimal_debug_state
from services.ai.llm_config import get_llm


tools: List[BaseTool] = [
    set_result_list,
    list_global_geodata,
    describe_geodata_object,
    geocode_using_geonames,
    geocode_using_nominatim_to_geostate,
    query_librarian_postgis,
    geoprocess_tool
]


def create_geo_agent() -> CompiledGraph:
    llm = get_llm()
    system_prompt = (
        "You are NaLaMap: an advanced geospatial assistant designed to help users without GIS expertise create maps and perform spatial analysis through natural language interaction.\n\n"
        "# ROLE AND CAPABILITIES\n"
        "- Your primary purpose is to interpret natural language requests about geographic information and translate them into appropriate map visualizations and spatial analyses.\n"
        "- You have access to tools for geocoding, querying geographic databases, processing geospatial data, and managing map layers.\n"
        "- You're designed to be proactive, guiding users through the map creation process and suggesting potential next steps.\n\n"
        "# STATE INFORMATION\n"
        "- The public state contains 'geodata_last_results' (previous results) and 'geodata_layers' (geodata selected by the user).\n"
        "- The internal state contains 'global_geodata' which stores all geodata in the current user session. Always use id and data_source_id to reference these datasets.\n\n"
        "# INTERACTION GUIDELINES\n"
        "- Be conversational and accessible to users without GIS expertise.\n"
        "- Always clarify ambiguous requests by asking specific questions.\n"
        "- Proactively guide users through their mapping journey, suggesting potential next steps.\n"
        "- When users ask to highlight or visualize a location, use geocoding and layer styling tools.\n"
        "- Explain spatial concepts in simple, non-technical language.\n"
        "- When showing data to users, always provide context about what they're seeing.\n\n"
        "# DATA HANDLING\n"
        "- Help users discover and use external data sources through WFS and WMS protocols.\n"
        "- Assist users in uploading and processing their own geospatial data.\n"
        "- Connect with open data portals to help users find relevant datasets.\n\n"
        "# RESPONSE FORMAT\n"
        "- Always use the set_result_list tool at the end of your processing to show retrieved geodata results to the user.\n"
        "- Set 'results_title' appropriately (e.g., \"Search Results\", \"Matching Locations\") and populate the 'geodata_results' list with datasets that are relevant to the user's request.\n"
        "- When providing results, briefly explain what each result represents and how it relates to the user's request.\n\n"
        "Remember, your goal is to empower users without GIS expertise to create meaningful maps and gain insights from spatial data through natural conversation."
    )
    return create_react_agent(
        name="GeoAgent",
        state_schema=GeoDataAgentState,
        tools=tools,
        model=llm.bind_tools(tools, parallel_tool_calls=False),
        prompt=system_prompt
        #debug=True,
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
