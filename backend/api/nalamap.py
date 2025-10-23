import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    FunctionMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from models.geodata import GeoDataObject, mock_geodata_objects
from models.messages.chat_messages import NaLaMapRequest, NaLaMapResponse
from models.settings_model import SettingsSnapshot
from models.states import DataState, GeoDataAgentState

# Lazy imports for heavy modules (loaded only when chat endpoint is called)
# from services.multi_agent_orch import multi_agent_executor
# from services.single_agent import create_geo_agent
# import openai

logger = logging.getLogger(__name__)


def make_json_serializable(obj: Any) -> Any:
    """
    Recursively convert non-JSON-serializable objects to JSON-serializable format.
    Handles LangChain message objects, lists, dicts, and other common types.
    """
    if obj is None:
        return None

    # Handle LangChain message objects
    if isinstance(obj, HumanMessage):
        return {"type": "human", "content": obj.content}
    elif isinstance(obj, AIMessage):
        return {"type": "ai", "content": obj.content}
    elif isinstance(obj, SystemMessage):
        return {"type": "system", "content": obj.content}
    elif isinstance(obj, (ToolMessage, FunctionMessage)):
        return {"type": "tool", "content": obj.content}
    elif isinstance(obj, BaseMessage):
        return {"type": "message", "content": str(obj.content)}

    # Handle lists
    elif isinstance(obj, list):
        return [make_json_serializable(item) for item in obj]

    # Handle dicts
    elif isinstance(obj, dict):
        return {key: make_json_serializable(value) for key, value in obj.items()}

    # Handle primitive types and other JSON-serializable objects
    elif isinstance(obj, (str, int, float, bool)):
        return obj

    # For everything else, convert to string
    else:
        try:
            # Try to serialize it first
            json.dumps(obj)
            return obj
        except (TypeError, ValueError):
            # If it fails, convert to string
            return str(obj)


def normalize_messages(raw: Optional[List[BaseMessage]]) -> List[BaseMessage]:
    if raw is None:
        return []
    normalized: List[BaseMessage] = []
    for idx, m in enumerate(raw):
        # 1) Already a subclass?
        if isinstance(
            m,
            (
                HumanMessage,
                AIMessage,
                SystemMessage,
                ToolMessage,
                FunctionMessage,
            ),
        ):
            normalized.append(m)
            continue

        t = getattr(m, "type", "").lower()
        content = getattr(m, "content", None)
        if content is None:
            raise HTTPException(400, detail="message[{idx}].content is missing")

        # Grab raw additional_kwargs so we can pull out tool_calls/refusal
        raw_additional = getattr(m, "additional_kwargs", {}) or {}
        raw_tool_calls = raw_additional.get("tool_calls")
        raw_refusal = raw_additional.get("refusal")

        # Everything else (e.g. token_usage, model_name, id, etc) lives in response_metadata
        extra = getattr(m, "response_metadata", {}) or {}

        if t in ("human", "user"):
            normalized.append(HumanMessage(content=content, **extra))

        elif t in ("ai", "assistant"):
            # Build your kwargs explicitly
            ai_kwargs: Dict[str, Any] = {"content": content}

            # Re-inject refusal if present
            if raw_refusal is not None:
                ai_kwargs["refusal"] = raw_refusal

            # Turn each legacy entry into a proper tool_call dict
            if raw_tool_calls:
                normalized_tool_calls = []
                for tc in raw_tool_calls:
                    func = tc.get("function", {})
                    # parse arguments JSON if needed:
                    raw_args = func.get("arguments", "{}")
                    try:
                        args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        args = raw_args
                    normalized_tool_calls.append(
                        {
                            "id": tc.get("id"),
                            "name": func.get("name"),
                            "args": args,
                            "type": "tool_call",
                        }
                    )
                # Finally merge in the other metadata (token_usage, model_name, etc)
            ai_kwargs.update(extra)

            normalized.append(AIMessage(**ai_kwargs))

        elif t == "system":
            normalized.append(SystemMessage(content=content, **extra))

        elif t == "tool":
            continue  # TODO: Fix required tool call missing
            # Your existing ToolMessage logic
            kwargs = {"content": content}
            if getattr(m, "name", None):
                kwargs["tool"] = m.name
            if getattr(m, "id", None):
                kwargs["tool_call_id"] = m.id
            # plus any other metadata you want to keep
            kwargs.update(extra)
            normalized.append(ToolMessage(**kwargs))

        elif t == "function":
            continue
            normalized.append(
                FunctionMessage(
                    name=getattr(m, "name", "unknown_function"),
                    content=content,
                    **extra,
                )
            )

        else:
            raise HTTPException(400, detail="message[{idx}].type '{t}' not recognized")

    return normalized


router = APIRouter()


@router.post("/chatmock", tags=["nalamap"], response_model=NaLaMapResponse)
async def ask_nalamap(request: NaLaMapRequest):
    """
    Ask a question to the NaLaMap, which
    """
    # TODO: Pass information to agent

    # TODO: Receive response and map to result

    # Fake response for now
    messages: List[BaseMessage] = [
        HumanMessage("Find rivers in Africa!"),
        AIMessage("I found some rivers!"),
    ]

    response: NaLaMapResponse = NaLaMapResponse(
        messages=messages,
        response="I found some rivers!",
        geodata=mock_geodata_objects(),
        options=request.options,
    )
    return response


@router.post("/chat2", tags=["nalamap"], response_model=NaLaMapResponse)
async def ask_nalamap_orchestrator(request: NaLaMapRequest):
    """Ask a question to the NaLaMap Orchestrator, which uses tools to respond
    and analyse geospatial information."""
    # Lazy import: only load heavy modules when chat endpoint is actually called
    from services.multi_agent_orch import multi_agent_executor

    messages: List[BaseMessage] = normalize_messages(request.messages)
    messages.append(HumanMessage(request.query))

    state = DataState(messages=messages, geodata=request.geodata)

    executor_result: DataState = await multi_agent_executor.ainvoke(state)

    # print(executor_result)
    # print(executor_result['geodata'])
    # print(getattr(executor_result, "geodata", state["geodata"]))
    result_messages: List[BaseMessage] = executor_result["messages"]
    result_response: str = result_messages[-1].content
    result_geodata: List[GeoDataObject] = executor_result["geodata"]
    response: NaLaMapResponse = NaLaMapResponse(
        messages=result_messages,
        response=result_response,
        geodata=result_geodata,
        options=request.options,
    )
    return response


@router.post("/chat", tags=["nalamap"], response_model=NaLaMapResponse)
async def ask_nalamap_agent(request: NaLaMapRequest):
    """Ask a question to the NaLaMap Single Agent, which uses tools to respond
    and analyse geospatial information."""
    # Lazy import: only load heavy modules when chat endpoint is actually called
    from services.single_agent import create_geo_agent, prune_messages
    from utility.performance_metrics import (
        PerformanceMetrics,
        PerformanceCallbackHandler,
        extract_token_usage_from_messages,
    )
    from utility.metrics_storage import get_metrics_storage
    import openai

    # Initialize performance tracking
    metrics = PerformanceMetrics()

    # print("befor normalize:", request.messages)
    # Normalize incoming messages and append user query
    messages: List[BaseMessage] = normalize_messages(request.messages)
    messages.append(
        HumanMessage(request.query)
    )  # TODO: maybe remove query once message is correctly added in frontend

    # Track message count before pruning
    metrics.record("message_count_before", len(messages))

    # Append as a single human message
    options_orig: dict = request.options

    options: SettingsSnapshot = SettingsSnapshot.model_validate(options_orig, strict=False)

    # Get message window size from model settings or use environment default
    message_window_size = getattr(options.model_settings, "message_window_size", None)
    if message_window_size is None:
        import os

        message_window_size = int(os.getenv("MESSAGE_WINDOW_SIZE", "20"))

    # Prune message history to prevent unbounded growth
    messages = prune_messages(messages, window_size=message_window_size)

    # Track message count after pruning
    metrics.record("message_count_after", len(messages))
    metrics.record("message_reduction", metrics.metrics["message_count_before"] - len(messages))

    state: GeoDataAgentState = GeoDataAgentState(
        messages=messages,
        geodata_last_results=request.geodata_last_results,
        geodata_layers=request.geodata_layers,
        results_title="",
        geodata_results=[],
        options=options,
        remaining_steps=10,  # Explicitly set remaining_steps
    )
    # state.global_geodata=request.global_geodata,

    try:
        # Get enable_parallel_tools from model settings
        enable_parallel_tools = getattr(options.model_settings, "enable_parallel_tools", False)

        single_agent = create_geo_agent(
            model_settings=options.model_settings,
            selected_tools=options.tools,
            enable_parallel_tools=enable_parallel_tools,
        )

        # Create performance callback handler
        perf_callback = PerformanceCallbackHandler()

        # Enable langgraph debug logging when global log level is DEBUG
        debug_enabled = logger.isEnabledFor(logging.DEBUG)

        # Start timing agent execution
        metrics.start_timer("agent_execution")

        executor_result: GeoDataAgentState = single_agent.invoke(
            state, debug=debug_enabled, config={"callbacks": [perf_callback]}
        )

        # End timing agent execution
        metrics.end_timer("agent_execution")

        result_messages: List[BaseMessage] = executor_result.get("messages", [])
        results_title: Optional[str] = executor_result.get("results_title", "")
        geodata_results: List[GeoDataObject] = executor_result.get("geodata_results", [])
        geodata_layers: List[GeoDataObject] = executor_result.get("geodata_layers", [])
        # global_geodata: List[GeoDataObject] = executor_result.get('global_geodata', [])

        result_options: Dict[str, Any] = executor_result.get("options", {})

        # Track final message count
        metrics.record("message_count_final", len(result_messages))

        # Collect metrics from callback handler
        callback_metrics = perf_callback.get_metrics()
        metrics.metrics.update(callback_metrics)

        # Extract token usage from messages if not captured by callback
        if callback_metrics["token_usage"]["total"] == 0:
            token_usage = extract_token_usage_from_messages(result_messages)
            metrics.metrics["token_usage"] = token_usage

        # Track state metrics
        metrics.record("geodata_layers_count", len(geodata_layers))
        metrics.record("geodata_results_count", len(geodata_results))

        # Log performance metrics
        final_metrics = metrics.finalize()

        # Store metrics in global storage if enabled
        session_id = getattr(options, "session_id", None) or "unknown"
        enable_performance_metrics = getattr(
            options.model_settings, "enable_performance_metrics", False
        )
        if enable_performance_metrics:
            storage = get_metrics_storage()
            storage.store(session_id=session_id, metrics=final_metrics)

        logger.info(
            "Agent execution completed",
            extra={
                "performance_metrics": final_metrics,
                "session_id": session_id,
            },
        )

        if not result_messages:  # Should always have messages, but safeguard
            result_messages = [
                AIMessage(content="Agent processed the request but returned no explicit messages.")
            ]

    except openai.InternalServerError as e:
        logger.error(f"OpenAI Internal Server Error: {e}")
        error_message = (
            "I encountered an issue with the AI model while processing your request. "
            "This might be a temporary problem. Please try again in a few moments. "
            "If the problem persists, simplifying your query might help."
        )
        result_messages = [
            *messages,
            AIMessage(content=error_message),
        ]  # Include history
        results_title = "Model Error"
        geodata_results = []
        geodata_layers = state.get("geodata_layers", [])  # Preserve existing layers
        # global_geodata = state.get('global_geodata', [])
        result_options = options

    except openai.APIError as e:
        logger.error(f"OpenAI API Error: {e}")
        error_message = (
            "I encountered an API error while trying to process your request. "
            "Please check your query or try again later."
        )
        result_messages = [*messages, AIMessage(content=error_message)]
        results_title = "API Error"
        geodata_results = []
        geodata_layers = state.get("geodata_layers", [])
        # global_geodata = state.get('global_geodata', [])
        result_options = options

    except Exception as e:  # Catch any other unexpected errors during agent execution
        logger.exception(f"Unexpected error during agent execution: {e}")
        error_message = (
            "An unexpected error occurred while processing your request. " "Please try again."
        )
        result_messages = [*messages, AIMessage(content=error_message)]
        results_title = "Unexpected Error"
        geodata_results = []
        geodata_layers = state.get("geodata_layers", [])
        # global_geodata = state.get('global_geodata', [])
        result_options = options

    # Ensure results_title is set if geodata_results exist but title is empty
    if (
        (results_title is None or results_title == "")
        and geodata_results
        and isinstance(geodata_results, List)
        and len(geodata_results) != 0
    ):
        results_title = "Agent results:"

    # Ensure result_messages always has at least one message for response
    # construction
    if not result_messages:
        # This case should ideally be handled by the agent or error blocks,
        # but as a final fallback:
        result_messages = [AIMessage(content="No response content generated.")]

    response: NaLaMapResponse = NaLaMapResponse(
        messages=result_messages,
        results_title=results_title,
        geodata_results=geodata_results,
        geodata_layers=geodata_layers,
        # global_geodata=global_geodata,
        options=result_options,
    )
    return response


@router.post("/chat/stream", tags=["nalamap"])
async def ask_nalamap_agent_stream(request: NaLaMapRequest):
    """
    Streaming version of the NaLaMap agent that emits real-time events
    using Server-Sent Events (SSE).

    Event types:
    - tool_start: Tool execution begins
    - tool_end: Tool execution completes
    - llm_token: LLM token streamed
    - state_update: Agent state changed
    - result: Final result ready
    - error: Error occurred
    - done: Stream complete
    """
    from fastapi.responses import StreamingResponse
    from services.single_agent import create_geo_agent, prune_messages
    from utility.performance_metrics import (
        PerformanceMetrics,
        PerformanceCallbackHandler,
        extract_token_usage_from_messages,
    )
    from utility.metrics_storage import get_metrics_storage
    import json
    import openai

    async def event_generator():
        """Generate SSE events from agent execution."""
        try:
            # Initialize performance tracking
            metrics = PerformanceMetrics()

            # Normalize incoming messages and append user query
            messages: List[BaseMessage] = normalize_messages(request.messages)
            messages.append(HumanMessage(request.query))

            # Track message count before pruning
            metrics.record("message_count_before", len(messages))

            # Parse options
            options_orig: dict = request.options
            options: SettingsSnapshot = SettingsSnapshot.model_validate(options_orig, strict=False)

            # Get message window size
            message_window_size = getattr(options.model_settings, "message_window_size", None)
            if message_window_size is None:
                import os

                message_window_size = int(os.getenv("MESSAGE_WINDOW_SIZE", "20"))

            # Prune messages
            messages = prune_messages(messages, window_size=message_window_size)

            # Track message counts
            metrics.record("message_count_after", len(messages))
            metrics.record(
                "message_reduction", metrics.metrics["message_count_before"] - len(messages)
            )

            # Create initial state
            state: GeoDataAgentState = GeoDataAgentState(
                messages=messages,
                geodata_last_results=request.geodata_last_results,
                geodata_layers=request.geodata_layers,
                results_title="",
                geodata_results=[],
                options=options,
                remaining_steps=10,
            )

            # Create agent
            enable_parallel_tools = getattr(options.model_settings, "enable_parallel_tools", False)
            single_agent = create_geo_agent(
                model_settings=options.model_settings,
                selected_tools=options.tools,
                enable_parallel_tools=enable_parallel_tools,
            )

            # Create performance callback handler
            perf_callback = PerformanceCallbackHandler()

            # Start timing
            metrics.start_timer("agent_execution")

            # Stream events using astream_events v2
            async for event in single_agent.astream_events(
                state, version="v2", config={"callbacks": [perf_callback]}
            ):
                event_type = event.get("event")
                event_name = event.get("name", "")
                event_data = event.get("data", {})

                # Debug logging for all events
                if event_type in ["on_chain_start", "on_chain_end"]:
                    logger.info(f"Chain event: type={event_type}, name={event_name}")

                # Handle tool events
                if event_type == "on_tool_start":
                    tool_name = event_name
                    tool_input = event_data.get("input", {})
                    # Make tool_input JSON serializable (may contain LangChain messages)
                    serializable_input = make_json_serializable(tool_input)
                    yield "event: tool_start\n"
                    data = json.dumps({"tool": tool_name, "input": serializable_input})
                    yield f"data: {data}\n\n"

                elif event_type == "on_tool_end":
                    tool_name = event_name
                    tool_output = event_data.get("output", {})
                    # Make tool_output JSON serializable
                    serializable_output = make_json_serializable(tool_output)

                    # Check if output is a state update (dict with messages, etc.)
                    # vs actual tool result (string, dict with data, etc.)
                    is_state_update = isinstance(serializable_output, dict) and (
                        "messages" in serializable_output
                        or "geodata_results" in serializable_output
                        or "geodata_layers" in serializable_output
                    )

                    # For state updates, only send summary
                    # For actual results, send full output
                    if is_state_update:
                        msg_count = len(serializable_output.get("messages", []))
                        output_preview = f"State update with {msg_count} messages"
                        output_data = {
                            "tool": tool_name,
                            "output_preview": output_preview,
                            "is_state_update": True,
                            "output_type": "state",
                        }
                    else:
                        # Send full result but also include a preview
                        output_str = str(serializable_output)
                        ellipsis = "..." if len(output_str) > 200 else ""
                        output_data = {
                            "tool": tool_name,
                            "output": serializable_output,
                            "output_preview": output_str[:200] + ellipsis,
                            "is_state_update": False,
                            "output_type": type(serializable_output).__name__,
                        }

                    yield "event: tool_end\n"
                    data = json.dumps(output_data)
                    yield f"data: {data}\n\n"

                # Handle LLM streaming tokens
                elif event_type == "on_chat_model_stream":
                    chunk = event_data.get("chunk", {})
                    if hasattr(chunk, "content") and chunk.content:
                        yield "event: llm_token\n"
                        yield f"data: {json.dumps({'token': chunk.content})}\n\n"

                # Handle chain/agent state updates
                elif event_type == "on_chain_end":
                    # Check for both "LangGraph" (older) and "GeoAgent" (current name)
                    if event_name in ["LangGraph", "GeoAgent"]:
                        # Agent execution complete - get final state
                        output = event_data.get("output", {})
                        result_messages = output.get("messages", [])
                        results_title = output.get("results_title", "")
                        geodata_results = output.get("geodata_results", [])
                        geodata_layers = output.get("geodata_layers", [])

                        # End timing
                        metrics.end_timer("agent_execution")

                        # Collect metrics
                        callback_metrics = perf_callback.get_metrics()
                        metrics.metrics.update(callback_metrics)

                        # Extract token usage if needed
                        if callback_metrics["token_usage"]["total"] == 0:
                            token_usage = extract_token_usage_from_messages(result_messages)
                            metrics.metrics["token_usage"] = token_usage

                        # Track state metrics
                        metrics.record("geodata_layers_count", len(geodata_layers))
                        metrics.record("geodata_results_count", len(geodata_results))
                        metrics.record("message_count_final", len(result_messages))

                        # Finalize and store metrics
                        final_metrics = metrics.finalize()
                        session_id = getattr(options, "session_id", None) or "unknown"
                        enable_performance_metrics = getattr(
                            options.model_settings, "enable_performance_metrics", False
                        )
                        if enable_performance_metrics:
                            storage = get_metrics_storage()
                            storage.store(session_id=session_id, metrics=final_metrics)

                        logger.info(
                            "Agent execution completed (streaming)",
                            extra={
                                "performance_metrics": final_metrics,
                                "session_id": session_id,
                            },
                        )

                        # Send final result
                        # Convert messages to serializable format
                        serializable_messages = []
                        for msg in result_messages:
                            if isinstance(msg, HumanMessage):
                                serializable_messages.append(
                                    {"type": "human", "content": msg.content}
                                )
                            elif isinstance(msg, AIMessage):
                                serializable_messages.append({"type": "ai", "content": msg.content})
                            elif isinstance(msg, SystemMessage):
                                serializable_messages.append(
                                    {"type": "system", "content": msg.content}
                                )

                        # Serialize geodata objects
                        serialized_results = [
                            r.model_dump() if hasattr(r, "model_dump") else r
                            for r in geodata_results
                        ]
                        serialized_layers = [
                            layer.model_dump() if hasattr(layer, "model_dump") else layer
                            for layer in geodata_layers
                        ]

                        yield "event: result\n"
                        result_data = {
                            "messages": serializable_messages,
                            "results_title": results_title,
                            "geodata_results": serialized_results,
                            "geodata_layers": serialized_layers,
                            "metrics": final_metrics,
                        }
                        yield f"data: {json.dumps(result_data)}\n\n"

            # Send done event
            yield "event: done\n"
            yield f"data: {json.dumps({'status': 'complete'})}\n\n"

        except openai.InternalServerError as e:
            logger.error(f"OpenAI Internal Server Error during streaming: {e}")
            yield "event: error\n"
            yield f"data: {json.dumps({'error': 'model_error', 'message': str(e)})}\n\n"
            yield "event: done\n"
            yield f"data: {json.dumps({'status': 'error'})}\n\n"

        except openai.APIError as e:
            logger.error(f"OpenAI API Error during streaming: {e}")
            yield "event: error\n"
            yield f"data: {json.dumps({'error': 'api_error', 'message': str(e)})}\n\n"
            yield "event: done\n"
            yield f"data: {json.dumps({'status': 'error'})}\n\n"

        except Exception as e:
            logger.exception(f"Unexpected error during streaming: {e}")
            yield "event: error\n"
            yield f"data: {json.dumps({'error': 'unexpected_error', 'message': str(e)})}\n\n"
            yield "event: done\n"
            yield f"data: {json.dumps({'status': 'error'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/metrics", tags=["nalamap"])
async def get_metrics(
    hours: int = Query(default=1, ge=1, le=168, description="Hours to look back (1-168)"),
    session_id: Optional[str] = Query(default=None, description="Filter by session ID"),
):
    """Get performance metrics for recent requests.

    Args:
        hours: Number of hours to look back (1-168, default: 1)
        session_id: Optional session ID filter

    Returns:
        Dictionary with recent metrics or aggregated statistics
    """
    from utility.metrics_storage import get_metrics_storage

    storage = get_metrics_storage()

    # Return aggregated statistics
    stats = storage.get_statistics(hours=hours, session_id=session_id)

    return {
        "status": "success",
        "data": stats,
        "storage_info": {"total_entries": storage.get_count()},
    }


@router.get("/metrics/recent", tags=["nalamap"])
async def get_recent_metrics(
    hours: int = Query(default=1, ge=1, le=24, description="Hours to look back (1-24)"),
    session_id: Optional[str] = Query(default=None, description="Filter by session ID"),
    limit: int = Query(default=100, ge=1, le=1000, description="Max results (1-1000)"),
):
    """Get recent raw metrics entries.

    Args:
        hours: Number of hours to look back (1-24, default: 1)
        session_id: Optional session ID filter
        limit: Maximum number of entries to return

    Returns:
        List of recent metrics entries
    """
    from utility.metrics_storage import get_metrics_storage

    storage = get_metrics_storage()
    recent = storage.get_recent(hours=hours, session_id=session_id)

    # Limit results
    recent = recent[-limit:]

    return {"status": "success", "data": recent, "count": len(recent)}
