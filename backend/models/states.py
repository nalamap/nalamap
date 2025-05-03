from dataclasses import dataclass, field
from typing import List
from .geodata import GeoDataObject  # relativer Import angepasst
from langgraph.graph import MessagesState  # Passe den Importpfad ggf. an

@dataclass
class DataState(MessagesState):
    geodata: List[GeoDataObject] = field(default_factory=list)
