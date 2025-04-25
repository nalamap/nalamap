from typing import List
from fastapi import APIRouter

from models.geodata import mock_geodata_objects
from models.states import DataState
from models.messages.chat_messages import GeoweaverRequest, GeoweaverResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from services.multi_agent_orch import multi_agent_executor

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

    response: GeoweaverResponse = GeoweaverResponse(messages=executor_result.messages, response=executor_result.messages[-1].content, geodata=executor_result.geodata)
    return response

