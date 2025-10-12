import json
import logging
from typing import Any, Dict, List, Optional

import openai  # Import openai for error handling
from fastapi import APIRouter, HTTPException
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
from services.multi_agent_orch import multi_agent_executor
from services.single_agent import create_geo_agent

logger = logging.getLogger(__name__)


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
    # print("befor normalize:", request.messages)
    # Normalize incoming messages and append user query
    messages: List[BaseMessage] = normalize_messages(request.messages)
    messages.append(
        HumanMessage(request.query)
    )  # TODO: maybe remove query once message is correctly added in frontend

    # Append as a single human message
    options_orig: dict = request.options

    options: SettingsSnapshot = SettingsSnapshot.model_validate(options_orig, strict=False)

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
        single_agent = create_geo_agent(
            model_settings=options.model_settings, selected_tools=options.tools
        )

        # Enable langgraph debug logging when global log level is DEBUG
        debug_enabled = logger.isEnabledFor(logging.DEBUG)
        executor_result: GeoDataAgentState = single_agent.invoke(state, debug=debug_enabled)

        result_messages: List[BaseMessage] = executor_result.get("messages", [])
        results_title: Optional[str] = executor_result.get("results_title", "")
        geodata_results: List[GeoDataObject] = executor_result.get("geodata_results", [])
        geodata_layers: List[GeoDataObject] = executor_result.get("geodata_layers", [])
        # global_geodata: List[GeoDataObject] = executor_result.get('global_geodata', [])

        result_options: Dict[str, Any] = executor_result.get("options", {})

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
