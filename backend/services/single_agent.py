from typing import Dict, List, Optional

from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from models.settings_model import ModelSettings, ToolConfig
from models.states import GeoDataAgentState, get_minimal_debug_state
from services.ai.llm_config import get_llm
from services.default_agent_settings import DEFAULT_AVAILABLE_TOOLS, DEFAULT_SYSTEM_PROMPT
from services.tools.geocoding import (
    geocode_using_nominatim_to_geostate,
    geocode_using_overpass_to_geostate,
)
from services.tools.geoprocess_tools import geoprocess_tool
from services.tools.geostate_management import describe_geodata_object, metadata_search
from services.tools.librarian_tools import query_librarian_postgis
from services.tools.styling_tools import (
    apply_intelligent_color_scheme,
    auto_style_new_layers,
    check_and_auto_style_layers,
    style_map_layers,
)
from utility.tool_configurator import create_configured_tools


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
    style_map_layers,  # Manual styling tool
    auto_style_new_layers,  # Intelligent auto-styling tool
    check_and_auto_style_layers,  # Automatic layer style checker
    apply_intelligent_color_scheme,  # Intelligent color scheme application
]


def create_geo_agent(
    model_settings: Optional[ModelSettings] = None,
    selected_tools: Optional[List[ToolConfig]] = None,
) -> CompiledStateGraph:
    # TODO: Create get_specific_llm to act on model_settings
    llm = get_llm()

    if (
        model_settings is None
        or model_settings.system_prompt is None
        or model_settings.system_prompt == ""
    ):
        system_prompt = DEFAULT_SYSTEM_PROMPT
    else:
        system_prompt = model_settings.system_prompt

    tools_dict: Dict[str, BaseTool] = create_configured_tools(
        DEFAULT_AVAILABLE_TOOLS, selected_tools
    )
    tools: List[BaseTool] = tools_dict.values()

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


if __name__ == "__main__":
    # Initialize geodata state (e.g. Berlin) with both public and private data

    debug_tool: bool = False
    initial_geo_state: GeoDataAgentState = get_minimal_debug_state(debug_tool)
    single_agent: CompiledStateGraph = create_geo_agent()

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
