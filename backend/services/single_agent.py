from typing_extensions import Annotated
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from langchain_core.tools import tool
from langgraph.prebuilt.chat_agent_executor import AgentState
from langgraph.prebuilt import create_react_agent, InjectedState
from langgraph.graph.graph import CompiledGraph
from models.states import GeoDataAgentState
from services.ai.llm_config import get_llm
from langchain_core.messages import HumanMessage, SystemMessage

from langgraph.managed import RemainingSteps
from models.geodata import GeoDataObject, mock_geodata_objects

# Some State Menagement Tools
@tool
def list_global_geodata(state: Annotated[GeoDataAgentState, InjectedState]) -> List[Dict[str, str]]:
    """
    Lists the datasets in the global state
    """
    return [{"id": geodata.id, "data_source_id": geodata.data_source_id, "title": geodata.title} for geodata in state["global_geodata"]]

# Additional tools to show/hide/describe datasets?


tools = [
    list_global_geodata
]


def create_geo_agent() -> CompiledGraph:
    llm = get_llm()
    system_prompt = (
        "You are LaLaMap: a geospatial assistant with map capabilities. "
        "You only see the public state (current_geodata). "
        "The internal state contains 'global_geodata' which contains all geodata in the current user session."  
    )
    return create_react_agent(
        name="GeoAgent",
        state_schema=GeoDataAgentState,
        tools=tools,
        model=llm,
        #prompt=system_prompt,
        debug=True,
        # config_schema=GeoData,
        #response_format=GeoData
    )

if __name__ == "__main__":
    agent = create_geo_agent()
    # Initialize geodata state (e.g. Berlin) with both public and private data

    initial_geo_state: GeoDataAgentState = GeoDataAgentState()
    initial_geo_state["messages"] = [HumanMessage("Show layers for rivers in egypt")]
    initial_geo_state["global_geodata"] = mock_geodata_objects()
    initial_geo_state["current_geodata"] = [initial_geo_state["global_geodata"][0]]

    # Ask the agent; private fields are kept internally but not sent to the LLM
    response = agent.invoke(initial_geo_state)
    print("-"*64)
    print(response["messages"])
    for message in response["messages"]:
        print(message.type, ":", message.content)
    #print("-"*64)
    #print(response["messages"])
