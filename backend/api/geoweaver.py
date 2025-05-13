from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException

from services.single_agent import single_agent
from models.geodata import GeoDataObject, mock_geodata_objects
from models.states import DataState, GeoDataAgentState
from models.messages.chat_messages import GeoweaverRequest, GeoweaverResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from services.multi_agent_orch import multi_agent_executor
import json

def normalize_messages(raw: List[BaseMessage]) -> List[BaseMessage]:
    normalized: List[BaseMessage] = []
    for idx, m in enumerate(raw):
        # If it's already the right subclass, leave it alone:
        if isinstance(m, (HumanMessage, AIMessage, SystemMessage)):
            normalized.append(m)
            continue

        # Otherwise we have a "generic" BaseMessage: inspect .type
        t = getattr(m, "type", "").lower()
        content = getattr(m, "content", None)
        if content is None:
            raise HTTPException(400, detail=f"message[{idx}].content is missing")

        # Pull through any other kwargs (like metadata) if you want
        extra = {
            **getattr(m, "additional_kwargs", {}),
            **getattr(m, "response_metadata", {}),
        }

        if t in ("human", "user"):
            normalized.append(HumanMessage(content=content, **extra))
        elif t in ("ai", "assistant"):
            normalized.append(AIMessage(content=content, **extra))
        elif t == "system":
            normalized.append(SystemMessage(content=content, **extra))
        elif t == "tool":
            continue
            # Tool Messages seem to fail with some tool_call_id missing errors -> skipping for now
            #normalized.append(ToolMessage(content=content, tool_call_id=getattr(m, "id", "noid"),**extra))
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
    messages: List[BaseMessage] = normalize_messages(request.messages)
    messages.append(HumanMessage(request.query)) # TODO: maybe remove query

    state: GeoDataAgentState = GeoDataAgentState(messages=messages, geodata_last_results=request.geodata_last_results, geodata_layers=request.geodata_layers, global_geodata=request.global_geodata, results_title="", geodata_results=[])

    executor_result: GeoDataAgentState = single_agent.invoke(state)

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