from typing import Any, Dict, List, Literal, Optional, Set, Union
from pydantic import BaseModel
from models.geodata import GeoDataObject
from langchain_core.messages import BaseMessage

# class ChatMessage(BaseModel):
#    role: Literal["user", "assistant", "system"]
#    content: str


class OrchestratorRequest(BaseModel):
    messages: List[BaseMessage]


class OrchestratorResponse(BaseModel):
    messages: List[BaseMessage]


class ChatPayload(BaseModel):
    id: Optional[str] = None
    input: Optional[str] = None
    messages: Optional[List[BaseMessage]] = None
    query: Optional[str] = None


class ChatResponse(BaseModel):
    id: str
    messages: List[BaseMessage]


# Geoweaver Messages
class GeoweaverRequest(BaseModel):
    """
    Request of the Frontend to the Geoweaver, which contains the message history, a request and geodata related to the query
    """

    messages: Optional[List[BaseMessage]] = None
    query: Optional[str] = None
    geodata_last_results: Optional[List[GeoDataObject]] = None
    geodata_layers: Optional[List[GeoDataObject]] = None
    #global_geodata: Optional[List[GeoDataObject]] = None
    options: Optional[Dict[str, Any]] = None


class GeoweaverResponse(BaseModel):
    """
    Reponse of the Geoweaver, which contains the message history, a response and geodata related to the query
    """

    messages: Optional[List[BaseMessage]] = None
    results_title: Optional[str] = None
    geodata_results: Optional[List[GeoDataObject]] = None
    #geodata_layers: Optional[List[GeoDataObject]] = None
    global_geodata: Optional[List[GeoDataObject]] = None
    options: Optional[Dict[str, Any]] = None
