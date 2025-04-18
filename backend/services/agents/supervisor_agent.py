import json
from typing import Literal
from os import getenv

from langchain_openai import AzureChatOpenAI
from langgraph.graph import MessagesState, START, END
from langgraph.types import Command

system_prompt = (
    "You are a supervisor managing a conversation between two workers: geo_helper and librarien. "
    "Analyze the conversation and decide which worker is best suited to answer the query. "
    "The Geo_Helper Agent is a LLM for general geospatial questions. "
    "The Librarien Agent searches a PostGIS database for datasets. "
    "Return a JSON object with: 'next' (one of 'geo_helper','librarien','finish') "
    "and 'reason' (short explanation)."
)

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
    messages = [{"role":"system","content":system_prompt}] + state["messages"]
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
