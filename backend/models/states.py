from dataclasses import dataclass, field
from pydantic import BaseModel, Field
from typing import List, Optional
from .geodata import GeoDataObject, mock_geodata_objects  # relativer Import angepasst
from langgraph.graph import MessagesState  # Passe den Importpfad ggf. an
from langgraph.prebuilt.chat_agent_executor import AgentState
from langchain_core.messages import HumanMessage

@dataclass
class DataState(MessagesState):
    geodata: List[GeoDataObject] = field(default_factory=list)


class GeoDataAgentState(AgentState):
    # TODO: maybe use references? 
    current_geodata: Optional[List[GeoDataObject]]

    # --- Internal-only fields (excluded from LLM prompt) ---
    global_geodata: Optional[List[GeoDataObject]] = Field(default_factory=dict, exclude=True, validate_default=False)


def get_minimal_debug_state(tool_call: bool = False) -> GeoDataAgentState:
    initial_geo_state: GeoDataAgentState = GeoDataAgentState()
    initial_geo_state["messages"] = [HumanMessage("Please show Frankfurt")]
    initial_geo_state["global_geodata"] = []
    initial_geo_state["current_geodata"] = []
    if tool_call:
        initial_geo_state["is_last_step"] = False
        initial_geo_state["remaining_steps"] = 5
    return initial_geo_state

def get_medium_debug_state(tool_call: bool = False) -> GeoDataAgentState:
    initial_geo_state: GeoDataAgentState = GeoDataAgentState()
    initial_geo_state["messages"] = [HumanMessage("Show layers for rivers in egypt")]
    initial_geo_state["global_geodata"] = mock_geodata_objects()[0:2]
    initial_geo_state["current_geodata"] = [initial_geo_state["global_geodata"][0]]
    if tool_call:
        initial_geo_state["is_last_step"] = False
        initial_geo_state["remaining_steps"] = 5
    return initial_geo_state