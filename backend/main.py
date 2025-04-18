from fastapi import FastAPI, HTTPException, Query, Body
from typing import List, Optional, Any, Dict, Literal
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from services.multi_agent_orch import multi_agent_executor
#from sqlalchemy.ext.asyncio import AsyncSession
from services.database.database import get_db, init_db, close_db
from services.agents.langgraph_agent import executor, SearchState
from services.tools.geocoding import geocode_using_nominatim
import json

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


@app.get("/api/geocode")
async def geocode(query: str = Query(...)) -> Dict[str, Any]:
    # 1) Invoke the tool (returns a JSON string)
    raw = geocode_using_nominatim.invoke(
        {"query": query, "geojson": True}
    )
    # 2) Parse into a Python dict, handling single-quoted JSON safely
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: convert single quotes to double quotes for JSON parsing
        fixed = raw.replace("'", '"')
        data = json.loads(fixed)
    
    # 3) Build our own result list
    results: List[Dict[str, Any]] = []
    print(str(data)[:500])
    # Nominatim returns a list of places
    for props in data:
        place_id     = props.get("place_id")
        osm_type     = props.get("osm_type")
        display_name = props.get("display_name")
        name_prop    = props.get("name")
        typ          = props.get("type")
        importance   = props.get("importance")
        bbox         = props.get("boundingbox")  # [lat_min, lat_max, lon_min, lon_max]
        raw_geo      = props.get("geokml")
        
        # turn bbox into WKT POLYGON string
        bounding_box: Optional[str]
        if bbox and len(bbox) == 4:
            lat_min, lat_max, lon_min, lon_max = map(float, bbox)
            bounding_box = (
                f"POLYGON(({lon_max} {lat_min},"
                         f"{lon_max} {lat_max},"
                         f"{lon_min} {lat_max},"
                         f"{lon_min} {lat_min},"
                         f"{lon_max} {lat_min}))"
            )
        else:
            bounding_box = None
        
        results.append({
            "resource_id":     place_id,
            "source_type":     osm_type,
            "name":            display_name,
            "title":           name_prop,
            "description":     typ,
            "access_url":      None,
            "format":          None,
            "llm_description": display_name,
            "bounding_box":    bounding_box,
            "raw_geo_data":    raw_geo,
            "score":           importance,
        })
    
    # 4) Return wrapped payload
    return {
        "query":   query,
        "results": results
    }

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
