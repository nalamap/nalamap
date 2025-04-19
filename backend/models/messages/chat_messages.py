from typing import List, Optional, Literal
from pydantic import BaseModel
from models.geodata import GeoDataObject

class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str

class OrchestratorRequest(BaseModel):
    messages: List[ChatMessage]

class OrchestratorResponse(BaseModel):
    messages: List[ChatMessage]

class ChatPayload(BaseModel):
    id: Optional[str] = None
    input: Optional[str] = None
    messages: Optional[List[ChatMessage]] = None
    query: Optional[str] = None

class ChatResponse(BaseModel):
    id: str
    messages: List[ChatMessage]

# Geoweaver Messages
class GeoweaverRequest(BaseModel):
    """
    Request of the Frontend to the Geoweaver, which contains the message history, a request and geodata related to the query
    """
    messages: Optional[List[ChatMessage]] = None
    query: Optional[str] = None
    geodata: Optional[List[GeoDataObject]] = None

class GeoweaverResponse(BaseModel):
    """
    Reponse of the Geoweaver, which contains the message history, a response and geodata related to the query
    """
    messages: Optional[List[ChatMessage]] = None
    response: Optional[str] = None
    geodata: Optional[List[GeoDataObject]] = None