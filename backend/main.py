from fastapi import FastAPI, HTTPException, Query, Body
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from services.ai_service import generate_ai_response
#from sqlalchemy.ext.asyncio import AsyncSession
from services.database.database import get_db, init_db, close_db
from services.agents.langgraph_agent import executor, SearchState

class ChatMessage(BaseModel):
    role: str
    content: str
    parts: Optional[List[dict]] = None

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

# Example in your FastAPI endpoint
@app.post("/api/search", response_model=ChatResponse)
async def search_endpoint(payload: dict = Body(...)):
    """
    FastAPI endpoint for search.
    Extracts the query from the incoming payload (using 'query', 'input', or the last message's content),
    passes it to the LangGraph executor, and wraps the search results in a chat response.
    """
    query = payload.get("query") or payload.get("input")
    if not query and "messages" in payload and payload["messages"]:
        query = payload["messages"][-1].get("content")
    if not query:
        raise HTTPException(status_code=400, detail="Query field is missing")
    
    # ... (query extraction and executor call)
    state = SearchState(query=query)
    result_state = await executor.ainvoke(state)
    results = result_state.get("results")
    print(results)
    # Return an assistant message with friendly content (or empty) and attach results.
    response = ChatResponse(
        id=payload.get("id", "map-chat"),
        messages=[
            ChatMessage(
                id="assistant-response",
                role="assistant",
                content="Search completed.",  # You can set this to empty if preferred.
                parts=results  # Attach the search results.
            )
        ]
    )
    return response



class AIRequest(BaseModel):
    message: str
    # TODO: Add additional information, like map data and layers in json

class AIResponse(BaseModel):
    response: str

@app.post("/api/geoweaver/generate", 
        response_model=AIResponse,
    summary="Generate GeoWeaver Response",
    description="Receives a message and returns an AI-generated response using GeoWeaverAI.",
    tags=["GeoWeaver"])
async def get_ai_response(request: AIRequest):
    try:
        result = generate_ai_response(request.message)
        return AIResponse(response=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
