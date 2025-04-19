from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field
from typing import List, Dict, Optional

from services.ai.llm_config import get_llm
from core.config import *  
from langchain.schema import HumanMessage, AIMessage, SystemMessage
from models.states import DataState


def prepare_messages(state: DataState) -> DataState:
    first_message = state["messages"][-1].content
    # TODO: Remove?
    if state["messages"]:
        state["messages"].append(HumanMessage(first_message))
    else:
        state["messages"] = [
            SystemMessage("You are a helpful assistant for GeoWeaver, a geospatial data platform."),
            HumanMessage(first_message)
        ]
    return state

async def query_ai(state: DataState) -> DataState:
    llm = get_llm() 
    """
    langchain_messages = []
    for msg in state["messages"]:
        if msg.role == "system":
            langchain_messages.append(SystemMessage(content=msg.content))
        elif msg.role == "user":
            langchain_messages.append(HumanMessage(content=msg.content))
        else:
            langchain_messages.append(AIMessage(content=msg.content))"""
    response = await llm.ainvoke(state["messages"]) # langchain_messages)
    print(response.content)
    # state.response = response.content if hasattr(response, "content") else str(response)
    state["messages"].append(AIMessage(response))
    return state

# build the little graph
graph = StateGraph(state_schema=DataState)
graph.add_node("prepare_messages", prepare_messages)
graph.add_node("query_ai", query_ai)
graph.add_edge(START, "prepare_messages")
graph.add_edge("prepare_messages", "query_ai")
graph.add_edge("query_ai", END)

ai_executor = graph.compile()
