# services/multi_agent_orch.py

import os
import sys
import asyncio
from typing import Literal

from langgraph.graph import StateGraph, END
from langgraph.types import Command

from services.agents.geo_weaver_ai import ai_executor as geo_helper_executor
from services.agents.langgraph_agent import executor as librarien_executor

def convert_to_geo_input(state: dict) -> dict:
    msgs = state["messages"]
    last = msgs[-1]["content"] if msgs else ""
    return {"input": last, "messages": msgs, "status": "pending"}

def convert_to_search_input(state: dict) -> dict:
    query = ""
    for m in state["messages"]:
        if m.get("role") == "user":
            query = m["content"]
            break
    return {"query": query, "results": []}


async def supervisor_node(state: dict) -> Command[Literal["geo_helper","librarien"]]:
    user_text = ""
    for m in state["messages"]:
        if m.get("role") == "user":
            user_text = m["content"].lower()
            break

    dataset_keywords = ["dataset", "datasets", "data", "download", "search database"]
    choice = "librarien" if any(kw in user_text for kw in dataset_keywords) else "geo_helper"
    print(f"[Orch] ▶ supervisor_node chose: {choice}")
    return Command(goto=choice, update={"next": choice})


async def geo_helper_node(state: dict) -> Command:
    inp = convert_to_geo_input(state)
    print(f"[Orch] ▶ geo_helper_node, sending to LLM: {inp}")
    ai_state = await geo_helper_executor.ainvoke(inp)

    output = getattr(ai_state, "response", None) \
             or ai_state.get("response") \
             or ai_state.get("output") \
             or "⚠️ Geo Helper returned no response."
    print(output)

    return Command(update={}, goto=END)


async def librarien_node(state: dict) -> Command:
    inp = convert_to_search_input(state)
    print(f"[Orch] ▶ librarien_node, querying DB with: {inp}")
    try:
        search_state = await librarien_executor.ainvoke(inp)
    except RuntimeError as e:
        if "not initialized" in str(e).lower():
            print("⚠️ Database pool is not initialized. Please initialize it and retry.")
            return Command(update={}, goto=END)
        raise

    results = getattr(search_state, "results", None) or search_state.get("results", [])
    print("Search results:")
    for r in results:
        print(r)

    return Command(update={}, goto=END)


# --- Build the orchestration graph ---
graph = StateGraph(state_schema=dict)
graph.add_node("supervisor", supervisor_node)
graph.add_node("geo_helper", geo_helper_node)
graph.add_node("librarien", librarien_node)
graph.set_entry_point("supervisor")

graph.add_edge("supervisor", "geo_helper")
graph.add_edge("supervisor", "librarien")
graph.add_edge("geo_helper", END)
graph.add_edge("librarien", END)

multi_agent_executor = graph.compile()

# Optional: export a Mermaid diagram
png_path = os.path.join(os.path.dirname(__file__), "multi_agent_graph.png")
with open(png_path, "wb") as f:
    f.write(multi_agent_executor.get_graph().draw_mermaid_png())
print("[Orch] Graph visualization saved to:", png_path)


# --- Runner ---
async def main():
    user_input = input("Enter your message: ")
    initial = {
        "messages": [{"role": "user", "content": user_input}],
        "next": ""
    }
    # invoke; one of the agent nodes will print and return END
    await multi_agent_executor.ainvoke(initial)

if __name__ == "__main__":
    asyncio.run(main())
