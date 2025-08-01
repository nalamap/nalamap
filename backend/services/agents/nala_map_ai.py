from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from models.states import DataState
from services.ai.llm_config import get_llm


def prepare_messages(state: DataState) -> DataState:
    first_message = state["messages"][-1].content
    # TODO: Remove?
    if state["messages"]:
        state["messages"].append(HumanMessage(first_message))
    else:
        state["messages"] = [
            SystemMessage("You are a helpful assistant for NaLaMap, a geospatial data platform."),
            HumanMessage(first_message),
        ]
    return state


async def query_ai(state: DataState) -> DataState:
    print(state["messages"])
    llm = get_llm()
    response = await llm.ainvoke(state["messages"])
    state["messages"].append(AIMessage(response.content))
    return state


# build the little graph
graph = StateGraph(state_schema=DataState)
graph.add_node("prepare_messages", prepare_messages)
graph.add_node("query_ai", query_ai)
graph.add_edge(START, "prepare_messages")
graph.add_edge("prepare_messages", "query_ai")
graph.add_edge("query_ai", END)

ai_executor = graph.compile()
