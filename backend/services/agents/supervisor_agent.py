import json
from typing import Literal
from services.ai.llm_config import get_llm
from models.states import DataState
from langgraph.graph import END
from langgraph.types import Command
from langchain_core.messages import HumanMessage, SystemMessage

LLM_PROMPT = """
You are an orchestration agent that decides which downstream agent should handle a user query.
There are two agents:
- geo_helper: answers and explains general geospatial questions.
- librarien: searches a PostGIS database for datasets and returns metadata.

Given the user query, produce **only** a JSON object with two keys:
  1. "next"   – one of "geo_helper", "librarien" or "finish"
  2. "reason" – a brief justification (1–2 Sätze), warum genau dieser Agent gewählt wurde.

User query: {query}

Respond with JSON only.
"""

DATASET_KEYWORDS = {
    "dataset",
    "datasets",
    "data",
    "download",
    "search database",
}

llm = get_llm()


def choose_agent(messages) -> str:
    user_messages = [m for m in messages if isinstance(m, HumanMessage)]
    text = (
        user_messages[-1].content.lower()
        if isinstance(user_messages[-1], HumanMessage) or user_messages
        else ""
    )
    if any(kw in text for kw in DATASET_KEYWORDS):
        return "librarien"
    llm_prompt = LLM_PROMPT.format(query=text)
    response = llm.invoke([SystemMessage(llm_prompt)])
    agent = response.content.strip().lower()
    if "librarien" in agent:
        return "librarien"
    if "geo_helper" in agent:
        return "geo_helper"
    return "finish"


async def supervisor_node(
    state: DataState,
) -> Command[Literal["geo_helper", "librarien", "finish"]]:
    user_messages = [m for m in state["messages"] if isinstance(m, HumanMessage)]
    user_text = user_messages[-1].content.lower() if user_messages else ""
    messages = [SystemMessage(LLM_PROMPT.format(query=user_text))] + user_messages[-1:]
    response = await llm.ainvoke(messages)
    raw = response.content.strip()
    try:
        parsed = json.loads(raw)
        nxt = parsed.get("next", "finish")
        reason = parsed.get("reason", "")
    except json.JSONDecodeError:
        nxt = raw.lower()
        reason = ""
    goto = END if nxt == "finish" else nxt
    return Command(
        goto=goto, update={"messages": state["messages"], "geodata": state["geodata"]}
    )
