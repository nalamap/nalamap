# services/multi_agent_orch.py

import asyncio
from typing import Dict

from langgraph.graph import StateGraph, END
from langgraph.types import Command

from services.database.database import init_db
from services.agents.geo_weaver_ai import ai_executor as geo_helper_executor
from services.agents.langgraph_agent import executor as librarien_executor

DATASET_KEYWORDS = {
    "dataset", "datasets", "data", "download",
    "search database", "show me", "find", "search",
}

def choose_agent(state: Dict) -> str:
    text = next(
        (m["content"].lower() for m in state["messages"] if m["role"] == "user"),
        ""
    )
    return "librarien" if any(kw in text for kw in DATASET_KEYWORDS) else "geo_helper"

async def supervisor_node(state: Dict) -> Command:
    choice = choose_agent(state)
    print(f"[Orch] ▶ supervisor_node chose: {choice}")
    return Command()

def convert_to_geo_input(state: Dict) -> Dict:
    last = state["messages"][-1]["content"]
    return {"input": last, "messages": state["messages"], "status": "pending"}

async def geo_helper_node(state: Dict) -> Command:
    inp = convert_to_geo_input(state)
    print(f"[Orch] ▶ geo_helper_node, sending to LLM: {inp}")
    ai_state = await geo_helper_executor.ainvoke(inp)

    output = (
        getattr(ai_state, "response", None)
        or ai_state.get("response")
        or ai_state.get("output")
        or "⚠️ Geo Helper returned no response."
    )
    print(output)
    return Command(goto=END)

def convert_to_search_input(state: Dict) -> Dict:
    query = next((m["content"] for m in state["messages"] if m["role"] == "user"), "")
    return {"query": query, "results": []}

async def librarien_node(state: Dict) -> Command:
    print("[Orch] ▶ librarien_node: Initializing DB pool…")
    await init_db()

    inp = convert_to_search_input(state)
    print(f"[Orch] ▶ librarien_node, querying DB with: {inp}")
    search_state = await librarien_executor.ainvoke(inp)

    results = getattr(search_state, "results", None) or search_state.get("results", [])
    print("Search results:")
    for r in results:
        print(r)

    return Command(goto=END)


# --- Build the graph ---
graph = StateGraph(state_schema=dict)
graph.add_node("supervisor", supervisor_node)
graph.add_node("geo_helper", geo_helper_node)
graph.add_node("librarien", librarien_node)

graph.set_entry_point("supervisor")

graph.add_conditional_edges(
    "supervisor",
    choose_agent,
    {"geo_helper": "geo_helper", "librarien": "librarien"}
)

graph.add_edge("geo_helper", END)
graph.add_edge("librarien", END)

multi_agent_executor = graph.compile()


# --- Runner ---
async def main():
    user_input = input("Enter your message: ")
    initial = {"messages": [{"role": "user", "content": user_input}]}
    await multi_agent_executor.ainvoke(initial)

if __name__ == "__main__":
    asyncio.run(main())
