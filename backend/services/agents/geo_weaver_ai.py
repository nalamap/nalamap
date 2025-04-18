from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import json
from os import getenv

from langchain_openai import AzureChatOpenAI
from langchain.schema import HumanMessage, AIMessage, SystemMessage

class AIState(BaseModel):
    input: str
    messages: List[Dict[str, str]] = Field(default_factory=list)
    response: Optional[str] = None
    error: Optional[str] = None
    status: str = "pending"

def get_azure_llm(max_tokens: int = 5000):
    llm = AzureChatOpenAI(
        azure_deployment=getenv("AZURE_OPENAI_DEPLOYMENT"),
        api_version=getenv("AZURE_OPENAI_API_VERSION"),
        temperature=0,
        max_tokens=max_tokens,
        timeout=None,
        max_retries=3,
    )
    print("[geo_weaver_ai] Initialized AzureChatOpenAI")
    return llm

def prepare_messages(state: AIState) -> AIState:
    print("[geo_weaver_ai] ▶ prepare_messages (incoming state):", state)
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
    print("[geo_weaver_ai] ▶ query_ai, messages:", state.messages)
    llm = get_azure_llm()
    langchain_messages = []
    for msg in state.messages:
        if msg["role"] == "system":
            langchain_messages.append(SystemMessage(content=msg["content"]))
        elif msg["role"] == "user":
            langchain_messages.append(HumanMessage(content=msg["content"]))
        else:
            langchain_messages.append(AIMessage(content=msg["content"]))

    print("[geo_weaver_ai]    sending to Azure:", langchain_messages)
    response = await llm.ainvoke(langchain_messages)
    print("[geo_weaver_ai]    Azure returned:", response)

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
