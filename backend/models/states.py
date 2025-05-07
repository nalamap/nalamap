from dataclasses import dataclass, field
from pydantic import BaseModel, Field
from typing import List, Optional
from .geodata import GeoDataObject  # relativer Import angepasst
from langgraph.graph import MessagesState  # Passe den Importpfad ggf. an
from langgraph.prebuilt.chat_agent_executor import AgentState

@dataclass
class DataState(MessagesState):
    geodata: List[GeoDataObject] = field(default_factory=list)


class GeoDataAgentState(AgentState):
    # TODO: maybe use references? 
    current_geodata: Optional[List[GeoDataObject]]

    # --- Internal-only fields (excluded from LLM prompt) ---
    global_geodata: Optional[List[GeoDataObject]] = Field(default_factory=dict, exclude=True, validate_default=False)
