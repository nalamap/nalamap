# services/multi_agent_orch.py

import asyncio
from typing import Dict, List

from langgraph.graph import StateGraph, END
from langgraph.types import Command
import json
from api.geoweaver import mock_geodata_objects
from models.geodata import GeoDataObject
from services.agents.geo_weaver_ai import ai_executor as geo_helper_executor
from services.agents.langgraph_agent import executor as librarien_executor
from services.agents.supervisor_agent import choose_agent, supervisor_node as llm_supervisor_node


async def supervisor_node(state: Dict) -> Command:
    latest_user_message = [m for m in state["messages"] if m["role"] == "user"][-1:]
    choice = choose_agent(latest_user_message)
    print(f"[Orch] ▶ supervisor_node chose: {choice}")
    return Command()

def convert_to_geo_input(state: Dict) -> Dict:
    last = state["messages"][-1]["content"]
    return {"input": last, "messages": state["messages"], "status": "pending"}

async def geo_helper_node(state: Dict) -> Command:
    inp = convert_to_geo_input(state)
    ai_state = await geo_helper_executor.ainvoke(inp)

    output = (
        getattr(ai_state, "response", None)
        or ai_state.get("response")
        or ai_state.get("output")
        or "⚠️ Geo Helper returned no response."
    )
    new_msgs = state["messages"] + [{"role": "assistant", "content": output}]
    return {"messages": new_msgs}

def convert_to_search_input(state: Dict) -> Dict:
    query = next((m["content"] for m in reversed(state["messages"]) if m["role"] == "user"), "")
    return {"query": query, "results": []}

async def librarien_node(state: Dict) -> Command:
    inp = convert_to_search_input(state)
    search_state = await librarien_executor.ainvoke(inp)

    results = getattr(search_state, "results", None) or search_state.get("results", [])
    print("Search results:")
    output="####BEGIN_DB_RESULTS####"
    for r in results:
        print(r)
        output+=json.dumps(r)+"####"
    output+="END_DB_RESULTS####"
    print(output)
    new_msgs = state["messages"] + [{"role": "assistant", "content": output}]
    return {"messages": new_msgs}


# --- Build the graph ---
graph = StateGraph(state_schema=dict)
graph.add_node("supervisor", supervisor_node)
graph.add_node("geo_helper", geo_helper_node)
graph.add_node("librarien", librarien_node)

graph.set_entry_point("supervisor")

graph.add_conditional_edges(
    "supervisor",
    lambda state: choose_agent([m for m in state["messages"] if m["role"] == "user"][-1:]),
    {"geo_helper": "geo_helper", "librarien": "librarien"}
)

graph.add_edge("geo_helper", END)
graph.add_edge("librarien", END)

multi_agent_executor = graph.compile()


# --- Runner ---
async def main():
    from services.database.database import init_db, close_db
    try:
        await init_db()
        messages = []
        print("Type 'exit' or 'quit' to end the conversation.")
        while True:
            user_input = input("Enter your message: ")
            if user_input.strip().lower() in {"exit", "quit"}:
                print("Goodbye!")
                break
            messages.append({"role": "user", "content": user_input})

            # initial state
            geo_data: List[GeoDataObject] = mock_geodata_objects()
            initial = {"messages": messages, "geo_data": geo_data}

            supervisor_result = await llm_supervisor_node(initial)
            print(supervisor_result)
            reason = supervisor_result.update.get("reason", "")
            next_agent = supervisor_result.goto
            if reason:
                print(f"[Orch] ▶ Supervisor explanation: {reason}")

            executor_result = await multi_agent_executor.ainvoke(initial)
            print(executor_result)
    finally:
        await close_db()

if __name__ == "__main__":
    asyncio.run(main())
