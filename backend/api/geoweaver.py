from typing import List
from fastapi import APIRouter

from models.geodata import GeoDataObject, mock_geodata_objects
from models.states import DataState
from models.messages.chat_messages import GeoweaverRequest, GeoweaverResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from services.multi_agent_orch import multi_agent_executor
import json

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



@router.post("/api/chat", tags=["geoweaver"], response_model=GeoweaverResponse)
async def ask_geoweaver(request: GeoweaverRequest):
    """
    Ask a question to the GeoWeaver, which uses tools to respond and analyse geospatial information.
    """
    messages: List[BaseMessage] = request.messages
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

