import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from models.settings_model import ModelSettings, ToolConfig
from models.states import GeoDataAgentState, get_minimal_debug_state
from services.ai.llm_config import get_llm
from services.conversation_manager import ConversationManager
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

# Module-level conversation managers (per session)
# Format: {session_id: {"manager": ConversationManager, "last_access": timestamp}}
conversation_managers: Dict[str, Dict[str, Any]] = {}

# Session TTL in seconds (default: 1 hour)
SESSION_TTL = 3600

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


def prune_messages(
    messages: List[BaseMessage], window_size: int, preserve_system: bool = True
) -> List[BaseMessage]:
    """Prune message history to keep only recent messages.

    Args:
        messages: List of messages to prune
        window_size: Maximum number of recent messages to keep (excluding system messages)
        preserve_system: If True, always keep the first system message (default: True)

    Returns:
        Pruned list of messages

    Examples:
        >>> messages = [SystemMessage("..."), HumanMessage("1"), AIMessage("2"), ...]
        >>> prune_messages(messages, window_size=5)  # Keeps system + last 5 messages
    """
    if not messages or window_size <= 0:
        return messages

    # Separate system messages from conversation messages
    system_messages = []
    conversation_messages = []

    for msg in messages:
        if preserve_system and isinstance(msg, SystemMessage):
            system_messages.append(msg)
        else:
            conversation_messages.append(msg)

    # Keep only the most recent window_size messages from conversation
    pruned_conversation = conversation_messages[-window_size:] if conversation_messages else []

    # Combine: system messages first, then recent conversation
    result = system_messages + pruned_conversation

    if len(conversation_messages) > window_size:
        logger.info(
            f"Pruned message history: {len(conversation_messages)} -> {len(pruned_conversation)} "
            f"messages (kept {len(system_messages)} system messages)"
        )

    return result


def _get_message_management_mode(settings_mode: Optional[str] = None) -> str:
    """Get the message management mode from settings or environment.

    Returns the configured message management strategy:
    - 'summarize' (default): Use LLM-based conversation summarization.
      Older messages are intelligently summarized to preserve context
      while reducing token usage.
    - 'prune': Use simple window-based truncation.
      Only the most recent messages are kept; older messages are discarded.

    Priority order:
    1. User/organization settings (settings_mode parameter)
    2. MESSAGE_MANAGEMENT_MODE environment variable
    3. Default: 'summarize'

    Args:
        settings_mode: Optional mode from user/organization settings

    Returns:
        One of 'summarize' or 'prune'
    """
    import os

    # Check user/organization settings first
    if settings_mode:
        mode = settings_mode.lower().strip()
        if mode in ("summarize", "prune"):
            return mode
        logger.warning(
            f"Invalid message_management_mode='{mode}' in settings, "
            f"checking environment variable. Valid values: 'summarize', 'prune'"
        )

    # Fallback to environment variable
    mode = os.getenv("MESSAGE_MANAGEMENT_MODE", "summarize").lower().strip()
    if mode not in ("summarize", "prune"):
        logger.warning(
            f"Unknown MESSAGE_MANAGEMENT_MODE='{mode}', falling back to 'summarize'. "
            f"Valid values: 'summarize', 'prune'"
        )
        return "summarize"
    return mode


async def prepare_messages(
    messages: List[BaseMessage],
    message_window_size: int,
    session_id: Optional[str] = None,
    llm: Optional[Any] = None,
    settings_mode: Optional[str] = None,
) -> List[BaseMessage]:
    """Prepare messages using the configured message management strategy.

    Applies either LLM-based summarization or simple window pruning based on:
    1. User/organization settings (settings_mode parameter)
    2. MESSAGE_MANAGEMENT_MODE environment variable
    3. Default: 'summarize'

    Args:
        messages: Full message history to process
        message_window_size: Window size for recent messages
        session_id: Session ID for conversation tracking (required for summarization)
        llm: Language model instance for summarization (optional, falls back to pruning)
        settings_mode: Optional mode from user/organization settings

    Returns:
        Processed message list, either summarized or pruned
    """
    mode = _get_message_management_mode(settings_mode)

    if mode == "summarize" and session_id:
        manager = get_conversation_manager(session_id, message_window_size)
        try:
            result = await manager.process_messages(messages, llm=llm)
            logger.info(
                f"Message summarization: {len(messages)} -> {len(result)} messages "
                f"(session: {session_id})"
            )
            return result
        except Exception as e:
            logger.error(f"Summarization failed, falling back to pruning: {e}")
            return prune_messages(messages, window_size=message_window_size)
    elif mode == "summarize" and not session_id:
        logger.warning("Summarization mode requires session_id, falling back to pruning")
        return prune_messages(messages, window_size=message_window_size)
    else:
        # mode == "prune"
        return prune_messages(messages, window_size=message_window_size)


def _cleanup_expired_sessions():
    """Clean up expired conversation manager sessions.

    Removes sessions that haven't been accessed within SESSION_TTL.
    Called periodically to prevent memory leaks.
    """
    current_time = time.time()
    expired_sessions = []

    for session_id, session_data in conversation_managers.items():
        last_access = session_data.get("last_access", 0)
        if current_time - last_access > SESSION_TTL:
            expired_sessions.append(session_id)

    for session_id in expired_sessions:
        del conversation_managers[session_id]
        logger.info(f"Cleaned up expired conversation session: {session_id}")

    if expired_sessions:
        logger.info(f"Cleaned up {len(expired_sessions)} expired conversation sessions")


def get_conversation_manager(session_id: str, message_window_size: int) -> ConversationManager:
    """Get or create conversation manager for a session.

    Args:
        session_id: Unique session identifier
        message_window_size: Window size for recent messages

    Returns:
        ConversationManager instance for this session
    """
    # Clean up expired sessions periodically
    _cleanup_expired_sessions()

    current_time = time.time()

    if session_id not in conversation_managers:
        # Create new conversation manager
        manager = ConversationManager(
            max_messages=message_window_size * 2,
            summarize_threshold=message_window_size + 5,
            summary_window=message_window_size,
        )
        conversation_managers[session_id] = {"manager": manager, "last_access": current_time}
        logger.info(f"Created new conversation manager for session: {session_id}")
    else:
        # Update last access time
        conversation_managers[session_id]["last_access"] = current_time

    return conversation_managers[session_id]["manager"]


async def create_geo_agent(
    model_settings: Optional[ModelSettings] = None,
    selected_tools: Optional[List[ToolConfig]] = None,
    enable_parallel_tools: bool = False,
    query: Optional[str] = None,
    session_id: Optional[str] = None,
    mcp_servers: Optional[List] = None,  # List of MCPServer objects
    system_prompt_addendum: Optional[str] = None,
) -> Tuple[CompiledStateGraph, Any]:
    """Create a geo agent with specified model and tools.

    Args:
        model_settings: Model configuration (provider, name, max_tokens, system_prompt)
        selected_tools: Tool configurations to enable/disable
        enable_parallel_tools: Whether to enable parallel tool execution
            (default: False, experimental)
        query: Current user query for dynamic tool selection (optional)
        session_id: Unique session identifier for conversation tracking
            (used for conversation summarization)
        mcp_servers: List of MCPServer objects to load external tools from
            (optional, supports authentication via api_key and headers fields)
        system_prompt_addendum: Optional text to append to the system prompt
            (used by the planner to inject execution plan instructions)

    Returns:
        Tuple of (CompiledStateGraph, llm) - the agent graph and the LLM instance.
        The LLM is returned so callers can pass it to prepare_messages() for
        conversation summarization.

    Note:
        Parallel tool execution is currently EXPERIMENTAL. While it can speed up multi-tool queries,
        it may cause state corruption if multiple tools modify the same state fields concurrently.
        Use with caution and monitor for race conditions.

        Dynamic tool selection uses semantic similarity to select relevant tools based on
        the query, supporting all languages. This reduces context size and improves performance.

        Message management is controlled by the MESSAGE_MANAGEMENT_MODE environment variable.
        Use prepare_messages() before invoking the agent to handle message history.

        MCP server integration allows loading external tools from Model Context Protocol
        servers, enabling NaLaMap to use third-party tools seamlessly.
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

    # Apply dynamic tool selection if enabled
    enable_dynamic_tools = (
        model_settings.enable_dynamic_tools
        if model_settings and hasattr(model_settings, "enable_dynamic_tools")
        else False
    )

    if enable_dynamic_tools and query:
        from services.tool_selector import create_tool_selector

        # Get embeddings from LLM if available
        embeddings = None
        if hasattr(llm, "embeddings"):
            embeddings = llm.embeddings
        else:
            # Try to create embeddings from same provider
            try:
                from services.ai.llm_config import get_embeddings

                embeddings = get_embeddings()
            except Exception as e:
                logger.warning(f"Could not load embeddings for dynamic tool selection: {e}")

        # Create tool selector with settings
        selector = create_tool_selector(
            embeddings=embeddings,
            strategy=(
                model_settings.tool_selection_strategy
                if hasattr(model_settings, "tool_selection_strategy")
                else "conservative"
            ),
            similarity_threshold=(
                model_settings.tool_similarity_threshold
                if hasattr(model_settings, "tool_similarity_threshold")
                else 0.3
            ),
            max_tools=(
                model_settings.max_tools_per_query
                if hasattr(model_settings, "max_tools_per_query")
                else None
            ),
        )

        # Select relevant tools
        tools: List[BaseTool] = await selector.select_tools(query, tools_dict)
        logger.info(f"Dynamic tool selection: {len(tools)}/{len(tools_dict)} tools selected")
    else:
        tools: List[BaseTool] = list(tools_dict.values())

    # Load external MCP tools if configured
    if mcp_servers:
        try:
            from services.mcp.integration import load_mcp_tools

            for mcp_server in mcp_servers:
                try:
                    server_url = mcp_server.url
                    api_key = getattr(mcp_server, "api_key", None)
                    headers = getattr(mcp_server, "headers", None)

                    logger.info(f"Loading tools from MCP server: {server_url}")
                    mcp_tools = await load_mcp_tools(server_url, api_key=api_key, headers=headers)
                    tools.extend(mcp_tools)
                    logger.info(f"Loaded {len(mcp_tools)} tools from MCP server: {server_url}")
                except Exception as e:
                    logger.error(f"Failed to load tools from MCP server {mcp_server.url}: {e}")
                    # Continue with other servers even if one fails
        except Exception as e:
            logger.error(f"Failed to import MCP integration: {e}")

    # Enable langgraph debug logging when global log level is DEBUG
    debug_enabled = logger.isEnabledFor(logging.DEBUG)

    # Determine if parallel tool calling should be enabled
    # State reducers now handle concurrent updates safely
    parallel_tool_calls = False
    if enable_parallel_tools:
        # Check if model supports parallel tool calls
        if model_settings:
            parallel_tool_calls = model_capabilities.supports_parallel_tool_calls

            if parallel_tool_calls:
                logger.info(
                    "Parallel tool execution ENABLED. "
                    "State reducers will handle concurrent updates."
                )
        else:
            logger.warning(
                "enable_parallel_tools=True but no model_settings provided, "
                "falling back to sequential execution"
            )

    # Append planning addendum to system prompt if provided
    if system_prompt_addendum:
        system_prompt = system_prompt + system_prompt_addendum
        logger.info("Appended execution plan to system prompt")

    agent = create_react_agent(
        name="GeoAgent",
        state_schema=GeoDataAgentState,
        tools=tools,
        model=llm.bind_tools(tools, parallel_tool_calls=parallel_tool_calls),
        prompt=system_prompt,
        debug=debug_enabled,
        # config_schema=GeoData,
        # response_format=GeoData
    )
    return agent, llm


if __name__ == "__main__":
    import asyncio

    # Initialize geodata state (e.g. Berlin) with both public and private data

    debug_tool: bool = False
    initial_geo_state: GeoDataAgentState = get_minimal_debug_state(debug_tool)
    single_agent, _llm = asyncio.run(create_geo_agent())

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
