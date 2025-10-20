import logging
from typing import Dict, List, Optional

from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from models.settings_model import ModelSettings, ToolConfig
from models.states import GeoDataAgentState, get_minimal_debug_state
from services.ai.llm_config import get_llm
from services.default_agent_settings import DEFAULT_AVAILABLE_TOOLS, DEFAULT_SYSTEM_PROMPT
from services.tools.attribute_tool2 import attribute_tool2
from services.tools.attribute_tools import attribute_tool
from services.tools.geocoding import (
    geocode_using_nominatim_to_geostate,
    geocode_using_overpass_to_geostate,
)
from services.tools.geoprocess_tools import geoprocess_tool
from services.tools.geostate_management import describe_geodata_object, metadata_search
from services.tools.styling_tools import (
    apply_intelligent_color_scheme,
    auto_style_new_layers,
    check_and_auto_style_layers,
    style_map_layers,
)
from utility.tool_configurator import create_configured_tools

logger = logging.getLogger(__name__)

tools: List[BaseTool] = [
    # set_result_list,
    # list_global_geodata,
    # describe_geodata_object,
    # geocode_using_geonames, # its very simple and does not create a geojson
    geocode_using_nominatim_to_geostate,
    geocode_using_overpass_to_geostate,
    # query_librarian_postgis,
    geoprocess_tool,
    metadata_search,
    style_map_layers,  # Manual styling tool
    auto_style_new_layers,  # Intelligent auto-styling tool
    check_and_auto_style_layers,  # Automatic layer style checker
    apply_intelligent_color_scheme,  # Intelligent color scheme application
    attribute_tool,
    attribute_tool2,  # Simplified attribute tool for better agent usability
]


def create_geo_agent(
    model_settings: Optional[ModelSettings] = None,
    selected_tools: Optional[List[ToolConfig]] = None,
    message_window_size: int = 20,
    enable_parallel_tools: bool = False,
) -> CompiledStateGraph:
    """Create a geo agent with specified model and tools.

    Args:
        model_settings: Model configuration (provider, name, max_tokens, system_prompt)
        selected_tools: Tool configurations to enable/disable
        message_window_size: Maximum number of recent messages to keep in context
            (default: 20)
        enable_parallel_tools: Whether to enable parallel tool execution
            (default: False, experimental)

    Returns:
        CompiledStateGraph configured with the specified model and tools

    Note:
        Parallel tool execution is currently EXPERIMENTAL. While it can speed up multi-tool queries,
        it may cause state corruption if multiple tools modify the same state fields concurrently.
        Use with caution and monitor for race conditions.
    """
    # Use model_settings if provided, otherwise use env defaults
    if model_settings is not None:
        from services.ai.llm_config import get_llm_for_provider

        llm, model_capabilities = get_llm_for_provider(
            provider_name=model_settings.model_provider,
            max_tokens=model_settings.max_tokens,
            model_name=model_settings.model_name,
        )
        system_prompt = (
            model_settings.system_prompt if model_settings.system_prompt else DEFAULT_SYSTEM_PROMPT
        )
    else:
        # Fall back to env-configured provider
        llm = get_llm()
        # No capabilities available for default LLM
        from services.ai.llm_config import ModelCapabilities

        model_capabilities = ModelCapabilities()
        system_prompt = DEFAULT_SYSTEM_PROMPT

    tools_dict: Dict[str, BaseTool] = create_configured_tools(
        DEFAULT_AVAILABLE_TOOLS, selected_tools or []
    )
    tools: List[BaseTool] = list(tools_dict.values())

    # Enable langgraph debug logging when global log level is DEBUG
    debug_enabled = logger.isEnabledFor(logging.DEBUG)

    # Determine if parallel tool calling should be enabled
    # Currently disabled by default due to potential state mutation conflicts
    parallel_tool_calls = False
    if enable_parallel_tools:
        # Check if model supports parallel tool calls
        if model_settings:
            parallel_tool_calls = model_capabilities.supports_parallel_tool_calls

            if parallel_tool_calls:
                logger.warning(
                    "Parallel tool execution ENABLED (experimental). "
                    "Monitor for potential state corruption issues."
                )
        else:
            logger.warning(
                "enable_parallel_tools=True but no model_settings provided, "
                "falling back to sequential execution"
            )

    return create_react_agent(
        name="GeoAgent",
        state_schema=GeoDataAgentState,
        tools=tools,
        model=llm.bind_tools(tools, parallel_tool_calls=parallel_tool_calls),
        prompt=system_prompt,
        debug=debug_enabled,
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
