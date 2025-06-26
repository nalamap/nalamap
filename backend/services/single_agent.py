from typing import List
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent
from langgraph.graph.graph import CompiledGraph
from services.tools.librarian_tools import query_librarian_postgis
from services.tools.geoprocess_tools import geoprocess_tool
from services.tools.geocoding import (
    geocode_using_nominatim_to_geostate,
    geocode_using_geonames,
    geocode_using_overpass_to_geostate,
)
from services.tools.geostate_management import (
    describe_geodata_object,
    list_global_geodata,
    set_result_list,
    metadata_search,
)
from models.states import (
    GeoDataAgentState,
    get_medium_debug_state,
    get_minimal_debug_state,
)
from services.ai.llm_config import get_llm


tools: List[BaseTool] = [
    # set_result_list,
    # list_global_geodata,
    # describe_geodata_object,
    # geocode_using_geonames, # its very simple and does not create a geojson
    geocode_using_nominatim_to_geostate,
    geocode_using_overpass_to_geostate,
    query_librarian_postgis,
    geoprocess_tool,
    metadata_search,
]


def create_geo_agent() -> CompiledGraph:
    llm = get_llm()
    system_prompt = (
        "You are NaLaMap: an advanced geospatial assistant designed to help users without GIS expertise create maps and perform spatial analysis through natural language interaction.\n\n"
        "# ROLE AND CAPABILITIES\n"
        "- Your primary purpose is to interpret natural language requests about geographic information and translate them into appropriate map visualizations and spatial analyses.\n"
        "- You have access to tools for geocoding, querying geographic databases, processing geospatial data, and managing map layers.\n"
        "- You can search for specific amenities (e.g., restaurants, parks, hospitals) near a location using the Overpass API.\n"
        "- You're designed to be proactive, guiding users through the map creation process and suggesting potential next steps.\n\n"
        "# STATE INFORMATION\n"
        "- The public state contains 'geodata_last_results' (previous results) and 'geodata_layers' (geodata selected by the user).\n"
        "- The list 'geodata_results' in the state collects tool results, which are presented to the user in a result list\n"
        "- IMPORTANT: When a user asks about a specific dataset, ALWAYS check if that dataset exists in 'geodata_last_results' or 'geodata_layers'.\n"
        "- When responding to questions about a dataset, first check if it's available in the state, and use its 'title', 'description', 'llm_description', 'data_source', 'layer_type', 'bounding_box' and other properties to provide specific, detailed information.\n"
        "# INTERACTION GUIDELINES\n"
        "- Be conversational and accessible to users without GIS expertise.\n"
        "- Always clarify ambiguous requests by asking specific questions.\n"
        "- Proactively guide users through their mapping journey, suggesting potential next steps.\n"
        "- When users ask to highlight or visualize a location, use geocoding and layer styling tools.\n"
        "- When a user asks to find amenities (e.g., 'restaurants in Paris', 'hospitals near the Colosseum'), use the 'geocode_using_overpass_to_geostate' tool. \n"
        "  - For this tool, you must extract the amenity type (e.g., 'restaurant', 'hospital') and the location name (e.g., 'Paris', 'Colosseum').\n"
        "  - Pass the original user query as the 'query' parameter.\n"
        "  - Pass the extracted amenity type as the 'amenity_key' parameter (e.g., 'restaurant', 'park', 'hospital'). Refer to the tool's internal mapping for supported keys.\n"
        "  - Pass the extracted location name as the 'location_name' parameter (e.g., 'Paris', 'Colosseum', 'Brandenburg Gate').\n"
        "  - You can optionally specify 'radius_meters' (default 10000m), 'max_results' (default 20), and 'timeout' (default 30s) for the search.\n"
        "- Explain spatial concepts in simple, non-technical language.\n"
        "- When showing data to users, always provide context about what they're seeing.\n"
        "- When users ask about specific datasets like 'Tell me more about the Rivers of Africa dataset' or 'What does this dataset contain?', use the 'metadata_search' tool with the name of the dataset as the query parameter.\n\n"
        "# DATA HANDLING\n"
        "- Help users discover and use external data sources through WFS and WMS protocols.\n"
        "- Assist users in uploading and processing their own geospatial data.\n"
        "- Connect with open data portals to help users find relevant datasets.\n\n"
        # "# RESPONSE FORMAT\n"
        # "- Always use the set_result_list tool at the end of your processing to show retrieved geodata results to the user.\n"
        # "- Set 'results_title' appropriately (e.g., \"Search Results\", \"Matching Locations\") and populate the 'geodata_results' list with datasets that are relevant to the user's request.\n"
        # "- When providing results, briefly explain what each result represents and how it relates to the user's request.\n\n"
        "Remember, your goal is to empower users without GIS expertise to create meaningful maps and gain insights from spatial data through natural conversation."
    )
    return create_react_agent(
        name="GeoAgent",
        state_schema=GeoDataAgentState,
        tools=tools,
        model=llm.bind_tools(tools, parallel_tool_calls=False),
        prompt=system_prompt,
        # debug=True,
        # config_schema=GeoData,
        # response_format=GeoData
    )


single_agent = create_geo_agent()

if __name__ == "__main__":
    # Initialize geodata state (e.g. Berlin) with both public and private data

    debug_tool: bool = False
    initial_geo_state: GeoDataAgentState = get_minimal_debug_state(debug_tool)

    if not debug_tool:
        # Ask the agent; private fields are kept internally but not sent to the LLM
        response = single_agent.invoke(initial_geo_state)
        print(64 * "-")
        print(response["messages"])
        for message in response["messages"]:
            print(message.type, ":", message.content)
        print(64 * "-")
        print(response["geodata_results"])
        # print("-"*64)
        # print(response["messages"])
    else:
        # Tool debugging
        print(
            describe_geodata_object.run(
                state=initial_geo_state,
                tool_input={
                    "state": initial_geo_state,
                    "id": "1512",
                    "data_source_id": "db_name",
                },
            )
        )
