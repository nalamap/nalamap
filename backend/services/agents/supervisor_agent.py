import json
from typing import Literal
from os import getenv

from langchain_openai import AzureChatOpenAI
from langgraph.graph import MessagesState, START, END
from langgraph.types import Command

# Use a single, clear system prompt for all LLM decisions
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
    "dataset", "datasets", "data", "download",
    "search database",
}

def choose_agent(messages) -> str:
    text = next(
        (m["content"].lower() for m in messages if m["role"] == "user"),
        ""
    )
    if any(kw in text for kw in DATASET_KEYWORDS):
        return "librarien"
    # If no keywords, ask the LLM to decide
    llm_prompt = LLM_PROMPT.format(query=text)
    response = llm.invoke([{"role": "system", "content": llm_prompt}])
    agent = response.content.strip().lower()
    if "librarien" in agent:
        return "librarien"
    return "geo_helper"

def get_azure_llm(max_tokens: int = 5000):
    return AzureChatOpenAI(
        azure_deployment=getenv("AZURE_OPENAI_DEPLOYMENT"),
        api_version=getenv("AZURE_OPENAI_API_VERSION"),
        temperature=0,
        max_tokens=max_tokens,
        timeout=None,
        max_retries=3
    )

llm = get_azure_llm()

class State(MessagesState):
    next: str = ""
    reason: str = ""

async def supervisor_node(state: State) -> Command[Literal["geo_helper","librarien","finish"]]:
    user_text = next(
        (m["content"].lower() for m in state["messages"] if m["role"] == "user"),
        ""
    )
    messages = [{"role": "system", "content": LLM_PROMPT.format(query=user_text)}] + state["messages"]
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
    return Command(goto=goto, update={"next": nxt, "reason": reason})
