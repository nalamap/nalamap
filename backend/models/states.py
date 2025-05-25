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
    results_title: Optional[str] = Field(default="", description="Title for the geodata response in 'geodata_results'" )
    geodata_last_results: Optional[List[GeoDataObject]] = Field(default_factory=list, exclude=False, validate_default=False)
    geodata_results: Optional[List[GeoDataObject]] = Field(default_factory=list, exclude=True, validate_default=False)
    geodata_layers: Optional[List[GeoDataObject]] = Field(default_factory=list, exclude=False, validate_default=False)
    
    # --- Internal-only fields (excluded from LLM prompt) ---
    #global_geodata: Optional[List[GeoDataObject]] = Field(default_factory=list, exclude=True, validate_default=False)


def get_minimal_debug_state(tool_call: bool = False) -> GeoDataAgentState:
    initial_geo_state: GeoDataAgentState = GeoDataAgentState()
    initial_geo_state["messages"] = [HumanMessage("Please show Frankfurt")]
    #initial_geo_state["global_geodata"] = []
    initial_geo_state["geodata_last_results"] = []
    initial_geo_state["geodata_results"] = []
    initial_geo_state["geodata_layers"] = []
    initial_geo_state["results_title"] = ""
    if tool_call:
        initial_geo_state["is_last_step"] = False
        initial_geo_state["remaining_steps"] = 5
    return initial_geo_state

def get_medium_debug_state(tool_call: bool = False) -> GeoDataAgentState:
    initial_geo_state: GeoDataAgentState = GeoDataAgentState()
    initial_geo_state["messages"] = [HumanMessage("Show layers for rivers in egypt")]
    #initial_geo_state["global_geodata"] = mock_geodata_objects()[0:2]
    initial_geo_state["geodata_last_results"] =  mock_geodata_objects()[0:2]
    initial_geo_state["geodata_results"] = []
    initial_geo_state["geodata_layers"] = []
    initial_geo_state["results_title"] = ""
    if tool_call:
        initial_geo_state["is_last_step"] = False
        initial_geo_state["remaining_steps"] = 5
    return initial_geo_state