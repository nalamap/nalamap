from typing import Dict, List, Optional

from langchain_core.tools import BaseTool
from langraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent
from langgraph.graph import START, END, StateGraph
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage

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


def should_continue(state):
    """Determine whether to continue or finish the agent execution."""
    messages = state.get("messages", [])
    if not messages:
        return END
    
    last_message = messages[-1]
    
    # If the last message is an AIMessage with tool calls, continue to tools
    if isinstance(last_message, AIMessage) and hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"
    
    # Otherwise, we're done
    return END


def create_call_model_function(model_settings: Optional[ModelSettings], selected_tools: Optional[List[ToolConfig]]):
    """Create a call_model function with the specified settings."""
    
    def call_model(state):
        """Call the model with the current state."""
        llm = get_llm()
        
        # Get the system prompt
        if (
            model_settings is None
            or model_settings.system_prompt is None
            or model_settings.system_prompt == ""
        ):
            system_prompt = DEFAULT_SYSTEM_PROMPT
        else:
            system_prompt = model_settings.system_prompt
        
        # Get tools configuration
        tools_dict: Dict[str, BaseTool] = create_configured_tools(
            DEFAULT_AVAILABLE_TOOLS, selected_tools
        )
        tools_list: List[BaseTool] = list(tools_dict.values())
        
        # Bind tools to the model
        model_with_tools = llm.bind_tools(tools_list, parallel_tool_calls=False)
        
        # Prepare messages with system prompt
        messages = state.get("messages", [])
        if not messages or not any(getattr(msg, 'type', None) == "system" for msg in messages):
            from langchain_core.messages import SystemMessage
            messages = [SystemMessage(content=system_prompt)] + messages
        
        # Call the model
        response = model_with_tools.invoke(messages)
        
        # Return the new message to add to state
        return {"messages": [response]}
    
    return call_model


def create_geo_agent(
    model_settings: Optional[ModelSettings] = None,
    selected_tools: Optional[List[ToolConfig]] = None,
) -> CompiledStateGraph:
    """
    Create a geography agent that properly handles Anthropic tool calling.
    
    This function replaces the previous create_react_agent approach with a manual
    LangGraph construction to ensure proper message flow for Anthropic's API.
    
    Anthropic requires strict message sequencing:
    1. AIMessage with tool_use content
    2. ToolMessage with tool_result (this was missing in create_react_agent)
    3. Next AIMessage response
    
    This manual construction ensures ToolNode properly handles the tool execution
    and inserts ToolMessage objects between tool_use and response messages.
    """
    
    # Get tools configuration
    tools_dict: Dict[str, BaseTool] = create_configured_tools(
        DEFAULT_AVAILABLE_TOOLS, selected_tools
    )
    tools_list: List[BaseTool] = list(tools_dict.values())
    
    # Create tool node
    tool_node = ToolNode(tools_list)
    
    # Create call_model function with settings
    call_model = create_call_model_function(model_settings, selected_tools)
    
    # Build the graph
    workflow = StateGraph(GeoDataAgentState)
    
    # Add nodes
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", tool_node)
    
    # Add edges
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", should_continue)
    workflow.add_edge("tools", "agent")
    
    # Compile and return
    return workflow.compile()


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
