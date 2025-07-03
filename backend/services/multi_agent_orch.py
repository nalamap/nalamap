# services/multi_agent_orch.py

import asyncio
import json
from typing import Dict, List

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, StateGraph
from langgraph.types import Command

from models.geodata import GeoDataObject, mock_geodata_objects
from models.states import DataState
from services.agents.geo_weaver_ai import ai_executor as geo_helper_executor
from services.agents.langgraph_agent import SearchState
from services.agents.langgraph_agent import executor as librarien_executor
from services.agents.supervisor_agent import choose_agent
from services.agents.supervisor_agent import (
    supervisor_node as llm_supervisor_node,
)


async def supervisor_node(state: DataState) -> Command:
    user_messages = [m for m in state["messages"] if isinstance(m, HumanMessage)]
    choice = choose_agent(user_messages)
    print(f"[Orch] ▶ supervisor_node chose: {choice}")
    return Command(
        goto=choice,
        update={"messages": state["messages"], "geodata": state["geodata"]},
    )


def convert_to_geo_input(state: DataState) -> Dict:
    return state  # {"input": last, "messages": state["messages"], "geodata": state["geodata"]}


async def geo_helper_node(state: DataState) -> Command:
    geo_input = convert_to_geo_input(state)
    ai_state = await geo_helper_executor.ainvoke(geo_input)
    # output = getattr(ai_state, "response", None) or "⚠️ Geo Helper returned no response."
    # new_msgs = state["messages"] + [{"role": "assistant", "content": output}]
    return Command(
        update={
            "messages": ai_state["messages"],
            "geodata": ai_state["geodata"],
        }
    )  # getattr(ai_state, "geodata", state["geodata"])})


def convert_to_search_input(state: DataState) -> Dict:
    query = next(
        (m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
        "",
    )
    # return state # {"query": query, "messages": state["messages"], "geodata": state["geodata"]}
    return SearchState(raw_query=query)


async def librarien_node(state: DataState) -> Command:
    search_input = convert_to_search_input(state)
    search_state: SearchState = await librarien_executor.ainvoke(search_input)
    results = getattr(search_state, "results", None) or search_state.get("results", [])
    output = "####BEGIN_DB_RESULTS####"
    for r in results:
        output += json.dumps(r.model_dump()) + "####"
    output += "END_DB_RESULTS####"
    # print(output)
    new_msgs = state["messages"] + [
        AIMessage(content="I found some layers and added them to the state ")
    ]  # [{"role": "assistant", "content": output}]
    return Command(update={"messages": new_msgs, "geodata": results})


# --- Build the graph ---
graph = StateGraph(state_schema=DataState)
graph.add_node("supervisor", supervisor_node)
graph.add_node("geo_helper", geo_helper_node)
graph.add_node("librarien", librarien_node)

graph.set_entry_point("supervisor")


def agent_selector(state: DataState):
    user_messages = [m for m in state["messages"] if isinstance(m, HumanMessage)]
    return choose_agent(user_messages[-1:])


graph.add_conditional_edges(
    "supervisor",
    agent_selector,
    {"geo_helper": "geo_helper", "librarien": "librarien"},
)

graph.add_edge("geo_helper", END)
graph.add_edge("librarien", END)

multi_agent_executor = graph.compile()


# --- Runner ---
async def main():
    from services.database.database import close_db, init_db

    try:
        await init_db()
        messages = []
        print("Type 'exit' or 'quit' to end the conversation.")
        while True:
            user_input = input("Enter your message: ")
            if user_input.strip().lower() in {"exit", "quit"}:
                print("Goodbye!")
                break
            messages.append(HumanMessage(user_input))

            geo_data: List[GeoDataObject] = mock_geodata_objects() or []
            state = DataState(messages=messages, geodata=geo_data)

            supervisor_result = await llm_supervisor_node(state)
            print(supervisor_result)
            reason = supervisor_result.update.get("reason", "")
            if reason:
                print(f"[Orch] ▶ Supervisor explanation: {reason}")

            await multi_agent_executor.ainvoke(state)
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
