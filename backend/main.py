from fastapi import FastAPI, HTTPException, Query, Body, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import List, Optional, Any, Dict, Literal
from pydantic import BaseModel
from contextlib import asynccontextmanager
from services.multi_agent_orch import multi_agent_executor
from services.database.database import get_db, init_db, close_db
from services.agents.langgraph_agent import executor, SearchState
from services.tools.geocoding import geocode_using_nominatim
import os
import uuid
import json

# Optional Azure Blob storage
USE_AZURE = os.getenv("USE_AZURE_STORAGE", "false").lower() == "true"
AZ_CONN = os.getenv("AZURE_CONN_STRING", "")
AZ_CONTAINER = os.getenv("AZURE_CONTAINER", "")
# Local upload directory and base URL
LOCAL_UPLOAD_DIR = os.getenv("LOCAL_UPLOAD_DIR", "./uploads")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()

app = FastAPI(
    title="GeoWeaver API",
    description="API for making geospatial data accessible",
    version="0.1.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve local uploads
os.makedirs(LOCAL_UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=LOCAL_UPLOAD_DIR), name="uploads")

# Upload endpoint
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)) -> Dict[str, str]:
    """
    Uploads a file either to Azure Blob Storage or local disk and returns its public URL and unique ID.
    """
    # Generate unique file name
    unique_name = f"{uuid.uuid4().hex}_{file.filename}"
    content = await file.read()

    if USE_AZURE:
        from azure.storage.blob import BlobServiceClient
        blob_svc = BlobServiceClient.from_connection_string(AZ_CONN)
        container = blob_svc.get_container_client(AZ_CONTAINER)
        container.upload_blob(name=unique_name, data=content)
        url = f"{container.url}/{unique_name}"
    else:
        dest_path = os.path.join(LOCAL_UPLOAD_DIR, unique_name)
        with open(dest_path, "wb") as f:
            f.write(content)
        url = f"{BASE_URL}/uploads/{unique_name}"

    return {"url": url, "id": unique_name}

@app.get("/api/search")
async def search(query: str = Query()):
    state = SearchState(query=query)
    results = await executor.ainvoke(state)
    return results

@app.get("/api/geocode")
async def geocode(query: str = Query(...)) -> Dict[str, Any]:
    raw = geocode_using_nominatim.invoke({"query": query, "geojson": True})
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        fixed = raw.replace("'", '"')
        data = json.loads(fixed)

    results: List[Dict[str, Any]] = []
    for props in data:
        place_id     = props.get("place_id")
        osm_type     = props.get("osm_type")
        display_name = props.get("display_name")
        name_prop    = props.get("name")
        typ          = props.get("type")
        importance   = props.get("importance")
        bbox         = props.get("boundingbox")
        raw_geo      = props.get("geokml")

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

    return {"query": query, "results": results}

@app.post("/api/orchestrate", response_model=OrchestratorResponse)
async def orchestrate(req: OrchestratorRequest):
    state = {"messages": [m.dict() for m in req.messages], "next": ""}
    final_state = await multi_agent_executor.ainvoke(state)
    return OrchestratorResponse(messages=final_state["messages"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
