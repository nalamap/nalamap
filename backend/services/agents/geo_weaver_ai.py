from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field
from typing import List, Dict, Optional

from services.ai.llm_config import get_llm
from core.config import *  
from langchain.schema import HumanMessage, AIMessage, SystemMessage

class AIState(BaseModel):
    input: str
    messages: List[Dict[str, str]] = Field(default_factory=list)
    response: Optional[str] = None
    error: Optional[str] = None
    status: str = "pending"

def prepare_messages(state: AIState) -> AIState:
    if state.messages:
        state.messages.append({"role": "user", "content": state.input})
    else:
        state.messages = [
            {"role": "system", "content": "You are a helpful assistant for GeoWeaver, a geospatial data platform."},
            {"role": "user",   "content": state.input}
        ]
    state.status = "messages_prepared"
    return state

async def query_ai(state: AIState) -> AIState:
    llm = get_llm()  
    langchain_messages = []
    for msg in state.messages:
        if msg["role"] == "system":
            langchain_messages.append(SystemMessage(content=msg["content"]))
        elif msg["role"] == "user":
            langchain_messages.append(HumanMessage(content=msg["content"]))
        else:
            langchain_messages.append(AIMessage(content=msg["content"]))
    response = await llm.ainvoke(langchain_messages)
    print(response.content)
    state.response = response.content if hasattr(response, "content") else str(response)
    state.messages.append({"role": "assistant", "content": state.response})
    state.status = "completed"
    return state

# build the little graph
graph = StateGraph(state_schema=AIState)
graph.add_node("prepare_messages", prepare_messages)
graph.add_node("query_ai", query_ai)
graph.add_edge(START, "prepare_messages")
graph.add_edge("prepare_messages", "query_ai")
graph.add_edge("query_ai", END)

ai_executor = graph.compile()
