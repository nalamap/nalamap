from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from services.ai_service import generate_ai_response
#from sqlalchemy.ext.asyncio import AsyncSession
from services.database.database import get_db, init_db, close_db
from services.agents.langgraph_agent import executor, SearchState




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
    state = SearchState(query=query)  # Initialize state with input query
    results = await executor.ainvoke(state)
    return results

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
