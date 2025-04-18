from fastapi import FastAPI, HTTPException, Query, Body
from typing import List, Optional, Literal
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from services.multi_agent_orch import multi_agent_executor
#from sqlalchemy.ext.asyncio import AsyncSession
from services.database.database import get_db, init_db, close_db
from services.agents.langgraph_agent import executor, SearchState

class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str

class OrchestratorRequest(BaseModel):
    messages: List[ChatMessage]

class OrchestratorResponse(BaseModel):
    messages: List[ChatMessage]

# Define a model to represent the incoming payload from useChat.
class ChatPayload(BaseModel):
    id: Optional[str] = None
    input: Optional[str] = None
    messages: Optional[List[ChatMessage]] = None
    query: Optional[str] = None

# Define the structure of the chat response.
class ChatResponse(BaseModel):
    id: str
    messages: List[ChatMessage]

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()  # Initialize DB pool when FastAPI starts
    yield
    await close_db() # close connection when app is finished
    
app = FastAPI(
    title="GeoWeaver API",
    description="API for making geospatial data accessible",
    version="0.1.0",
    lifespan=lifespan
)

# Enable CORS for all origins (adjust allow_origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or specify a list like ["https://example.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#@app.on_event("shutdown")
#async def shutdown():
#    await close_db()  # Clean up DB connections when FastAPI shuts down


@app.get("/api/search")
async def search(query: str = Query()):
    state = SearchState(query=query)  
    results = await executor.ainvoke(state)
    return results




class AIRequest(BaseModel):
    message: str
    # TODO: Add additional information, like map data and layers in json

class AIResponse(BaseModel):
    response: str

@app.post("/api/orchestrate", response_model=OrchestratorResponse)
async def orchestrate(req: OrchestratorRequest):
    state = {
        "messages": [m.dict() for m in req.messages],
        "next": ""
    }
    final_state = await multi_agent_executor.ainvoke(state)


    return OrchestratorResponse(messages=final_state["messages"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
