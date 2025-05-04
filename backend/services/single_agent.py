from typing_extensions import Annotated
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
from langchain_core.tools import tool
from langgraph.prebuilt.chat_agent_executor import AgentState
from langgraph.prebuilt import create_react_agent, InjectedState
from langgraph.graph.graph import CompiledGraph
from services.ai.llm_config import get_llm
from langchain_core.messages import HumanMessage, SystemMessage

from langgraph.managed import RemainingSteps

class GeoData(AgentState):
    # --- Public state fields (exposed to the agent/LLM) ---
    latitude: float
    longitude: float


    # --- Internal-only fields (excluded from LLM prompt) ---
    dataset_cache: Optional[Dict[str, Any]] = Field(default_factory=dict, exclude=True, validate_default=False)
    user_preferences: Optional[Dict[str, Any]] = Field(default_factory=dict, exclude=True, validate_default=False)

# 2. Minimal dummy example tool
# TODO: Check tool state handling https://github.com/langchain-ai/langgraph/discussions/1616 -> Command
@tool
def get_elevation(state: Annotated[GeoData, InjectedState]) -> Dict[str, Any]:
    """
    Get elevation (in meters) at the current geodata state
    """
    return {"elevation_m": 123.0}


@tool
def get_weather(state: Annotated[GeoData, InjectedState]) -> Dict[str, Any]:
    """
    Get current weather at the current geodata state
    """
    return {"condition": "Sunny", "temp_c": 18.5}


@tool
def calculate_distance(state: Annotated[GeoData, InjectedState], target_lat: float, target_lon: float) -> Dict[str, Any]:
    """
    Calculate distance (in km) from the current geodata state 
    to a target latitude and longitude: args = (target_lat, target_lon)
    """
    from math import radians, sin, cos, sqrt, atan2

    R = 6371.0  # Earth radius in kilometers
    lat1, lon1, lat2, lon2 = map(radians, [state.latitude, state.longitude, target_lat, target_lon])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return {"distance_km": R * c}


@tool
def list_datasets(state: Annotated[GeoData, InjectedState]) -> Dict[str, Any]:
    """
    List all available datasets: no args needed
    """
    # e.g., query your database or storage
    return {"datasets": [{"id": "sample_ds", "name": "Sample Dataset"}]}


@tool
def process_dataset(state: Annotated[GeoData, InjectedState], dataset_id: str) -> Dict[str, Any]:
    """
    Process a dataset given its id: args = (dataset_id,)
    """
    # Simulate processing and cache result in internal state
    result = {"dataset_id": dataset_id, "status": "processed"}
    state["dataset_cache"][dataset_id] = result
    return result


tools = [
    get_elevation,
    get_weather,
    calculate_distance,
    list_datasets,
    process_dataset
]


def create_geo_agent() -> CompiledGraph:
    llm = get_llm()
    system_prompt = (
        "You are GeoAgent: a geospatial assistant. "
        "You only see the public state (latitude, longitude, messages). "
        "Internal state fields like dataset_cache or user_preferences are NOT exposed to you."  
    )
    return create_react_agent(
        name="GeoAgent",
        state_schema=GeoData,
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

    initial_state = GeoData(latitude=52.52, longitude=13.405, user_preferences={"units": "metric"})
    initial_state["messages"] = [HumanMessage("Fetch elevation, display weather, then list datasets and process 'sample_ds'.")]
    initial_state["dataset_cache"] = {}
    initial_state["latitude"] = 52.52
    initial_state["longitude"] = 13.405
    initial_state["user_preferences"] = {"units": "metric"}

    # Ask the agent; private fields are kept internally but not sent to the LLM
    response = agent.invoke(initial_state)
    print("-"*64)
    print(response)
