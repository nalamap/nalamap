import asyncio
import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
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

# Global dict to track cancellation requests by session_id
_cancellation_flags: Dict[str, bool] = {}
_cancellation_lock = asyncio.Lock()


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


async def _prepare_chat_context(
    request: NaLaMapRequest,
    raw_request: Request,
    metrics,
) -> tuple:
    """Prepare shared context for both chat and streaming endpoints.

    Normalizes messages, resolves session_id, manages message history
    (via pruning or summarization), creates an execution plan for complex
    queries, and creates the agent + initial state.

    Args:
        request: The NaLaMap chat request
        raw_request: The raw FastAPI request (for cookies)
        metrics: Performance metrics tracker

    Returns:
        Tuple of (state, single_agent, options, perf_callback, session_id, stream_id, plan)
    """
    from services.single_agent import create_geo_agent, prepare_messages
    from services.planner import create_execution_plan, build_plan_system_addendum
    from utility.performance_metrics import PerformanceCallbackHandler

    logger.info(f"[CHAT] query={request.query[:120]!r}")

    # Normalize incoming messages and append user query
    messages: List[BaseMessage] = normalize_messages(request.messages)
    messages.append(HumanMessage(request.query))

    # Track message count before processing
    metrics.record("message_count_before", len(messages))

    # Parse options
    options_orig: dict = request.options
    options: SettingsSnapshot = SettingsSnapshot.model_validate(options_orig, strict=False)

    # Resolve session_id: options > cookie
    if not options.session_id:
        cookie_session_id = raw_request.cookies.get("session_id")
        if cookie_session_id:
            logger.info(f"Using session_id from cookie: {cookie_session_id}")
            options.session_id = cookie_session_id
        else:
            logger.warning("No session_id provided in options or cookies")

    session_id = getattr(options, "session_id", None)
    if not session_id:
        session_id = str(uuid.uuid4())
        logger.warning(f"Generated fallback session_id: {session_id}")

    # Get message window size from model settings or environment
    message_window_size = getattr(options.model_settings, "message_window_size", None)
    if message_window_size is None:
        import os

        message_window_size = int(os.getenv("MESSAGE_WINDOW_SIZE", "20"))

    # Create agent (returns agent + llm for summarization)
    enable_parallel_tools = getattr(options.model_settings, "enable_parallel_tools", False)

    # Get enabled MCP servers from options (pass full objects for auth)
    mcp_servers = [server for server in getattr(options, "mcp_servers", []) if server.enabled]

    single_agent, llm = await create_geo_agent(
        model_settings=options.model_settings,
        selected_tools=options.tools,
        enable_parallel_tools=enable_parallel_tools,
        query=request.query,
        session_id=options.session_id,
        mcp_servers=mcp_servers if mcp_servers else None,
    )

    # Get message management mode from settings (or fall back to env var)
    message_management_mode = getattr(options.model_settings, "message_management_mode", None)

    # Prepare messages (summarization or pruning based on settings/env)
    messages = await prepare_messages(
        messages=messages,
        message_window_size=message_window_size,
        session_id=options.session_id,
        llm=llm,
        settings_mode=message_management_mode,
    )

    # Track message count after processing
    metrics.record("message_count_after", len(messages))
    metrics.record("message_reduction", metrics.metrics["message_count_before"] - len(messages))

    # --- Multi-step Planning ---
    # Analyze the query to determine if it requires a multi-step plan.
    # If so, the plan is injected into the agent's prompt so it follows
    # the structured steps, and streamed to the frontend for visibility.
    enable_planning = getattr(options.model_settings, "enable_planning", False)
    execution_plan = None

    if enable_planning:
        try:
            # Build layer context for the planner
            existing_layers = None
            if request.geodata_layers:
                existing_layers = [
                    {
                        "title": getattr(layer, "title", None) or getattr(layer, "name", ""),
                        "name": getattr(layer, "name", ""),
                    }
                    for layer in request.geodata_layers
                ]

            metrics.start_timer("planning")
            execution_plan = await create_execution_plan(
                query=request.query,
                llm=llm,
                messages=messages,
                existing_layers=existing_layers,
            )
            metrics.end_timer("planning")

            if execution_plan:
                logger.info(
                    f"Execution plan created with {len(execution_plan.steps)} steps "
                    f"for query: {request.query[:80]}"
                )
                metrics.record("plan_steps", len(execution_plan.steps))

                # Inject plan into agent by rebuilding with augmented prompt
                plan_addendum = build_plan_system_addendum(execution_plan)
                single_agent, llm = await create_geo_agent(
                    model_settings=options.model_settings,
                    selected_tools=options.tools,
                    enable_parallel_tools=enable_parallel_tools,
                    query=request.query,
                    session_id=options.session_id,
                    mcp_servers=mcp_servers if mcp_servers else None,
                    system_prompt_addendum=plan_addendum,
                )
        except Exception as e:
            logger.warning(f"Planning failed, proceeding without plan: {e}")
            execution_plan = None

    # Create initial state
    state: GeoDataAgentState = GeoDataAgentState(
        messages=messages,
        geodata_last_results=request.geodata_last_results,
        geodata_layers=request.geodata_layers,
        results_title="",
        geodata_results=[],
        options=options,
        remaining_steps=10,
        execution_plan=execution_plan,
    )

    # Create performance callback handler
    perf_callback = PerformanceCallbackHandler()

    # Also extract stream_id for cancellation tracking (streaming only)
    stream_id = options_orig.get("stream_id") or session_id

    return state, single_agent, options, perf_callback, session_id, stream_id, execution_plan


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
async def ask_nalamap_agent(request: NaLaMapRequest, raw_request: Request):
    """Ask a question to the NaLaMap Single Agent, which uses tools to respond
    and analyse geospatial information."""
    # Lazy import: only load heavy modules when chat endpoint is actually called
    from utility.performance_metrics import (
        PerformanceMetrics,
        extract_token_usage_from_messages,
    )
    from utility.metrics_storage import get_metrics_storage
    import openai

    # Initialize performance tracking
    metrics = PerformanceMetrics()

    # Prepare shared context (messages, agent, state)
    state, single_agent, options, perf_callback, session_id, _, _plan = await _prepare_chat_context(
        request, raw_request, metrics
    )

    try:
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

        result_options: Dict[str, Any] = executor_result.get("options", {})

        # Track final message count
        metrics.record("message_count_final", len(result_messages))

        # Collect metrics from callback handler
        callback_metrics = perf_callback.get_metrics()
        metrics.metrics.update(callback_metrics)

        # Collect tool selector metrics (Week 3 - Performance Monitoring)
        from services.tool_selector import get_last_selector_metrics

        tool_selector_metrics = get_last_selector_metrics()
        if tool_selector_metrics:
            metrics.metrics["tool_selector"] = tool_selector_metrics

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
        metrics_session_id = getattr(options, "session_id", None) or session_id
        enable_performance_metrics = getattr(
            options.model_settings, "enable_performance_metrics", False
        )
        if enable_performance_metrics:
            storage = get_metrics_storage()
            storage.store(session_id=metrics_session_id, metrics=final_metrics)

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
            *state.get("messages", []),
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
        result_messages = [*state.get("messages", []), AIMessage(content=error_message)]
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
        result_messages = [*state.get("messages", []), AIMessage(content=error_message)]
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
async def ask_nalamap_agent_stream(request: NaLaMapRequest, raw_request: Request):
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
    from utility.performance_metrics import (
        PerformanceMetrics,
        extract_token_usage_from_messages,
    )
    from utility.metrics_storage import get_metrics_storage
    from services.planner import match_tool_to_plan_step, update_plan_step_status
    import asyncio
    import json
    import openai

    # Keepalive interval for SSE (seconds) - prevents proxy idle timeouts
    SSE_KEEPALIVE_INTERVAL = 30

    async def event_generator():
        """Generate SSE events from agent execution."""
        stream_id = "unknown"  # Initialize at function scope
        try:
            # Initialize performance tracking
            metrics = PerformanceMetrics()

            # Prepare shared context (messages, agent, state)
            (
                state,
                single_agent,
                options,
                perf_callback,
                session_id,
                stream_id,
                execution_plan,
            ) = await _prepare_chat_context(request, raw_request, metrics)

            # If we have an execution plan, stream it to the frontend
            if execution_plan:
                plan_data = execution_plan.model_dump()
                yield "event: plan\n"
                yield f"data: {json.dumps(plan_data)}\n\n"

            # Start timing
            metrics.start_timer("agent_execution")

            # Track which plan step is currently active
            current_active_step = None  # step_number of the in-progress step
            # Map tool invocation run_id → step_number (to reuse on tool_end)
            tool_step_map = {}

            # Plan continuation: if the agent ends with pending steps, re-invoke
            MAX_PLAN_CONTINUATIONS = 3
            continuation_count = 0
            current_state = state
            final_agent_output = None

            while True:  # Outer loop: plan continuation
                aiter = single_agent.astream_events(
                    current_state, version="v2", config={"callbacks": [perf_callback]}
                ).__aiter__()

                while True:  # Inner loop: event processing
                    try:
                        event = await asyncio.wait_for(
                            aiter.__anext__(), timeout=SSE_KEEPALIVE_INTERVAL
                        )
                    except StopAsyncIteration:
                        break
                    except asyncio.TimeoutError:
                        # Emit SSE comment as keepalive to prevent proxy idle timeout
                        yield ": keepalive\n\n"
                        continue

                    # Check for cancellation before processing each event
                    if await is_cancelled(stream_id):
                        logger.warning(
                            f"🛑 Cancellation detected for stream: {stream_id} at event loop"
                        )
                        yield "event: cancelled\n"
                        yield (f"data: {json.dumps({'message': 'Request cancelled by user'})}\n\n")
                        yield "event: done\n"
                        yield f"data: {json.dumps({'status': 'cancelled'})}\n\n"
                        return

                    event_type = event.get("event")
                    event_name = event.get("name", "")
                    event_data = event.get("data", {})

                    # Debug logging for cancellation checking
                    if event_type in ["on_tool_start", "on_tool_end", "on_chain_start"]:
                        logger.info(
                            f"Event: {event_type} | name: {event_name} | "
                            f"stream: {stream_id} | "
                            f"cancelled: {await is_cancelled(stream_id)}"
                        )

                    # Debug logging for all events
                    if event_type in ["on_chain_start", "on_chain_end"]:
                        logger.info(f"Chain event: type={event_type}, name={event_name}")

                    # Handle tool events
                    if event_type == "on_tool_start":
                        tool_name = event_name
                        tool_input = event_data.get("input", {})
                        run_id = event.get("run_id")
                        serializable_input = make_json_serializable(tool_input)

                        # Track plan step progress
                        matched_step = None
                        if execution_plan:
                            matched_step = match_tool_to_plan_step(
                                tool_name, execution_plan, current_active_step
                            )
                            if matched_step:
                                if run_id:
                                    tool_step_map[run_id] = matched_step

                                if (
                                    current_active_step is not None
                                    and matched_step != current_active_step
                                ):
                                    update_plan_step_status(
                                        execution_plan, current_active_step, "complete"
                                    )
                                    yield "event: plan_step_update\n"
                                    step_data = {
                                        "step_number": current_active_step,
                                        "status": "complete",
                                    }
                                    yield f"data: {json.dumps(step_data)}\n\n"

                                current_active_step = matched_step
                                update_plan_step_status(execution_plan, matched_step, "in-progress")
                                yield "event: plan_step_update\n"
                                step_update = {
                                    "step_number": matched_step,
                                    "status": "in-progress",
                                    "tool": tool_name,
                                }
                                yield f"data: {json.dumps(step_update)}\n\n"

                        yield "event: tool_start\n"
                        data = json.dumps(
                            {
                                "tool": tool_name,
                                "input": serializable_input,
                                "plan_step": matched_step,
                            }
                        )
                        yield f"data: {data}\n\n"

                    elif event_type == "on_tool_end":
                        tool_name = event_name
                        run_id = event.get("run_id")
                        tool_output = event_data.get("output", {})
                        serializable_output = make_json_serializable(tool_output)

                        is_state_update = isinstance(serializable_output, dict) and (
                            "messages" in serializable_output
                            or "geodata_results" in serializable_output
                            or "geodata_layers" in serializable_output
                        )

                        matched_step = None
                        if execution_plan and run_id:
                            matched_step = tool_step_map.pop(run_id, None)

                        if is_state_update:
                            msg_count = len(serializable_output.get("messages", []))
                            output_preview = f"State update with {msg_count} messages"
                            output_data = {
                                "tool": tool_name,
                                "output_preview": output_preview,
                                "is_state_update": True,
                                "output_type": "state",
                                "plan_step": matched_step,
                            }
                        else:
                            output_str = str(serializable_output)
                            ellipsis = "..." if len(output_str) > 200 else ""
                            output_data = {
                                "tool": tool_name,
                                "output": serializable_output,
                                "output_preview": output_str[:200] + ellipsis,
                                "is_state_update": False,
                                "output_type": type(serializable_output).__name__,
                                "plan_step": matched_step,
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

                    # Handle chain/agent completion — capture output
                    elif event_type == "on_chain_end":
                        if event_name in ["LangGraph", "GeoAgent"]:
                            final_agent_output = event_data.get("output", {})

                # Inner loop ended. Check for plan continuation.
                if execution_plan and final_agent_output:
                    pending_steps = [s for s in execution_plan.steps if s.status == "pending"]
                    if pending_steps and continuation_count < MAX_PLAN_CONTINUATIONS:
                        continuation_count += 1

                        # Mark current in-progress step as complete
                        if current_active_step is not None:
                            update_plan_step_status(execution_plan, current_active_step, "complete")
                            yield "event: plan_step_update\n"
                            step_data = {
                                "step_number": current_active_step,
                                "status": "complete",
                            }
                            yield f"data: {json.dumps(step_data)}\n\n"
                            current_active_step = None

                        next_step = pending_steps[0]
                        logger.info(
                            f"Plan continuation {continuation_count}/"
                            f"{MAX_PLAN_CONTINUATIONS}: "
                            f"step {next_step.step_number} ({next_step.title})"
                        )

                        # Build continuation state from agent output
                        cont_messages = list(final_agent_output.get("messages", []))
                        cont_messages.append(
                            HumanMessage(
                                content=(
                                    f"Continue with the next step of the plan. "
                                    f"Step {next_step.step_number}: "
                                    f"{next_step.title} — {next_step.description}"
                                )
                            )
                        )
                        current_state = GeoDataAgentState(
                            messages=cont_messages,
                            geodata_layers=final_agent_output.get("geodata_layers", []),
                            geodata_results=final_agent_output.get("geodata_results", []),
                            geodata_last_results=final_agent_output.get("geodata_last_results", []),
                            results_title=final_agent_output.get("results_title", ""),
                            options=options,
                            remaining_steps=10,
                            execution_plan=execution_plan,
                        )
                        final_agent_output = None
                        continue  # Re-invoke agent for next step
                # No continuation needed — break outer loop
                break

            # All agent invocations done — emit final result
            metrics.end_timer("agent_execution")

            if final_agent_output:
                result_messages = final_agent_output.get("messages", [])
                results_title = final_agent_output.get("results_title", "")
                geodata_results = final_agent_output.get("geodata_results", [])
                geodata_layers = final_agent_output.get("geodata_layers", [])

                # Collect metrics
                callback_metrics = perf_callback.get_metrics()
                metrics.metrics.update(callback_metrics)

                if callback_metrics["token_usage"]["total"] == 0:
                    token_usage = extract_token_usage_from_messages(result_messages)
                    metrics.metrics["token_usage"] = token_usage

                metrics.record("geodata_layers_count", len(geodata_layers))
                metrics.record("geodata_results_count", len(geodata_results))
                metrics.record("message_count_final", len(result_messages))
                if continuation_count > 0:
                    metrics.record("plan_continuations", continuation_count)

                final_metrics = metrics.finalize()
                metrics_session_id = getattr(options, "session_id", None) or session_id
                enable_performance_metrics = getattr(
                    options.model_settings, "enable_performance_metrics", False
                )
                if enable_performance_metrics:
                    storage = get_metrics_storage()
                    storage.store(session_id=metrics_session_id, metrics=final_metrics)

                logger.info(
                    "Agent execution completed (streaming)",
                    extra={
                        "performance_metrics": final_metrics,
                        "session_id": session_id,
                    },
                )

                # Convert messages to serializable format
                serializable_messages = []
                for msg in result_messages:
                    if isinstance(msg, HumanMessage):
                        serializable_messages.append({"type": "human", "content": msg.content})
                    elif isinstance(msg, AIMessage):
                        serializable_messages.append({"type": "ai", "content": msg.content})
                    elif isinstance(msg, SystemMessage):
                        serializable_messages.append({"type": "system", "content": msg.content})

                serialized_results = [
                    r.model_dump() if hasattr(r, "model_dump") else r for r in geodata_results
                ]
                serialized_layers = [
                    layer.model_dump() if hasattr(layer, "model_dump") else layer
                    for layer in geodata_layers
                ]

                # Mark any remaining plan steps as complete
                if execution_plan:
                    for step in execution_plan.steps:
                        if step.status in ("pending", "in-progress"):
                            update_plan_step_status(execution_plan, step.step_number, "complete")
                            yield "event: plan_step_update\n"
                            step_data = {
                                "step_number": step.step_number,
                                "status": "complete",
                            }
                            yield f"data: {json.dumps(step_data)}\n\n"

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

        finally:
            # Always clear cancellation flag when stream ends (use stream_id)
            await clear_cancellation(stream_id)

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


@router.post("/chat/cancel", tags=["nalamap"])
async def cancel_chat_request(session_id: str):
    """
    Cancel an ongoing chat/streaming request for a specific stream.

    Args:
        session_id: The stream ID of the request to cancel (can be user session_id
                   for backward compatibility or stream_id for new requests)

    Returns:
        Status message indicating cancellation was requested
    """
    async with _cancellation_lock:
        _cancellation_flags[session_id] = True
        logger.info(f"Cancellation requested for stream: {session_id}")

    return {"status": "cancellation_requested", "session_id": session_id}


async def is_cancelled(session_id: str) -> bool:
    """Check if cancellation has been requested for a session."""
    async with _cancellation_lock:
        return _cancellation_flags.get(session_id, False)


async def clear_cancellation(session_id: str):
    """Clear cancellation flag for a session after completion."""
    async with _cancellation_lock:
        _cancellation_flags.pop(session_id, None)


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
