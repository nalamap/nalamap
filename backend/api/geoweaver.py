from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException

from services.single_agent import single_agent
from models.geodata import GeoDataObject, mock_geodata_objects
from models.states import DataState, GeoDataAgentState
from models.messages.chat_messages import GeoweaverRequest, GeoweaverResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage, FunctionMessage
from services.multi_agent_orch import multi_agent_executor
import json

def normalize_messages(raw: List[BaseMessage]) -> List[BaseMessage]:
    normalized: List[BaseMessage] = []
    for idx, m in enumerate(raw):
        # 1) Already a subclass?
        if isinstance(m, (HumanMessage, AIMessage, SystemMessage, ToolMessage, FunctionMessage)):
            normalized.append(m)
            continue

        t = getattr(m, "type", "").lower()
        content = getattr(m, "content", None)
        if content is None:
            raise HTTPException(400, detail=f"message[{idx}].content is missing")

        # Grab raw additional_kwargs so we can pull out tool_calls/refusal
        raw_additional = getattr(m, "additional_kwargs", {}) or {}
        raw_tool_calls = raw_additional.get("tool_calls")
        raw_refusal    = raw_additional.get("refusal")

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
                    normalized_tool_calls.append({
                        "id":   tc.get("id"),
                        "name": func.get("name"),
                        "args": args,
                        "type": "tool_call",
                    })
                # ai_kwargs["tool_calls"] = normalized_tool_calls #TODO: Add back once fixed https://langchain-ai.github.io/langgraph/troubleshooting/errors/INVALID_CHAT_HISTORY/

            # Finally merge in the other metadata (token_usage, model_name, etc)
            ai_kwargs.update(extra)

            normalized.append(AIMessage(**ai_kwargs))

        elif t == "system":
            normalized.append(SystemMessage(content=content, **extra))

        elif t == "tool":
            continue # TODO: Fix required tool call missing
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
            raise HTTPException(400, detail=f"message[{idx}].type '{t}' not recognized")

    return normalized


router = APIRouter()
@router.post("/api/chatmock", tags=["geoweaver"], response_model=GeoweaverResponse)
async def ask_geoweaver(request: GeoweaverRequest):
    """
    Ask a question to the GeoWeaver, which 
    """
    print(request)
    # TODO: Pass information to agent

    # TODO: Receive response and map to result

    # Fake response for now
    messages: List[BaseMessage] = [HumanMessage("Find rivers in Africa!"), AIMessage("I found some rivers!")]
    
    response: GeoweaverResponse = GeoweaverResponse(messages=messages, response="I found some rivers!", geodata=mock_geodata_objects())
    return response


@router.post("/api/chat2", tags=["geoweaver"], response_model=GeoweaverResponse)
async def ask_geoweaver(request: GeoweaverRequest):
    """
    Ask a question to the GeoWeaver Orchestrator, which uses tools to respond and analyse geospatial information.
    """
    messages: List[BaseMessage] = normalize_messages(request.messages)
    messages.append(HumanMessage(request.query))

    state = DataState(messages=messages, geodata=request.geodata)

    executor_result: DataState = await multi_agent_executor.ainvoke(state)

    #print(executor_result)
    #print(executor_result['geodata'])
    #print(getattr(executor_result, "geodata", state["geodata"]))
    result_messages: List[BaseMessage] = executor_result['messages']
    result_response: str = result_messages[-1].content
    result_geodata: List[GeoDataObject] = executor_result['geodata']
    response: GeoweaverResponse = GeoweaverResponse(messages=result_messages, response=result_response, geodata=result_geodata)
    return response


@router.post("/api/chat", tags=["geoweaver"], response_model=GeoweaverResponse)
async def ask_geoweaver(request: GeoweaverRequest):
    """
    Ask a question to the GeoWeaver Single Agent, which uses tools to respond and analyse geospatial information.
    """
    print("befor normalize:", request.messages)
    messages: List[BaseMessage] = normalize_messages(request.messages)
    messages.append(HumanMessage(request.query)) # TODO: maybe remove query once message is correctly added in frontend
    print("debug messages:", messages)

    state: GeoDataAgentState = GeoDataAgentState(messages=messages, geodata_last_results=request.geodata_last_results, geodata_layers=request.geodata_layers, global_geodata=request.global_geodata, results_title="", geodata_results=[])

    executor_result: GeoDataAgentState = single_agent.invoke(state, debug=True)
    #executor_result=state
    #print(executor_result)
    #print(executor_result['geodata'])
    #print(getattr(executor_result, "geodata", state["geodata"]))
    result_messages: List[BaseMessage] = executor_result['messages']
    result_response: str = result_messages[-1].content
    results_title: Optional[str] = getattr(executor_result, "results_title", "")
    if "results_title" in executor_result:
        results_title = executor_result["results_title"]
    else:
        results_title = ""
    geodata_results: List[GeoDataObject] = executor_result['geodata_results']
    geodata_layers: List[GeoDataObject] = executor_result['geodata_layers']
    global_geodata: List[GeoDataObject] = executor_result['global_geodata']
    if (results_title is None or results_title == "") and geodata_results and isinstance(geodata_results, List) and len(geodata_results) != 0:
        results_title = "Agent results:"
    response: GeoweaverResponse = GeoweaverResponse(messages=result_messages, results_title=results_title, geodata_results=geodata_results, geodata_layers=geodata_layers, global_geodata=global_geodata)
    return response