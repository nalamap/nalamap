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
import io
# Geo conversion
from shapely.geometry import mapping
from kml2geojson.main import convert as kml2geojson_convert


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
        raw_geo      = props.get("geokml")  # inner KML snippet

        # 1) Reconstruct full KML document
        full_kml = ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
                    "<kml xmlns=\"http://www.opengis.net/kml/2.2\">"
                    "<Document><Placemark>" + raw_geo + "</Placemark></Document></kml>")

            # Convert KML to GeoJSON FeatureCollection
        buffer = io.BytesIO(full_kml.encode('utf-8'))
        collection = kml2geojson_convert(buffer)
        # kml2geojson_convert can return:
        # - a list of FeatureCollections
        # - a tuple (style_dict, list_of_FeatureCollections)
        if isinstance(collection, tuple):
            # expect the last element as list of FeatureCollections
            raw_list = collection[-1]
        elif isinstance(collection, list):
            raw_list = collection
        else:
            raw_list = [collection]
        # take the first FeatureCollection
        fc = raw_list[0]
        features = fc.get("features", []) if isinstance(fc, dict) else []
        geometry = features[0].get("geometry") if features else None

        # 3) Build GeoJSON Feature
        feature_geojson = {
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "resource_id": place_id,
                "name":         display_name,
                "description":  typ,
                "score":        importance,
            },
            "bbox": bbox
        }

        # 4) Serialize and save as .geojson
        geojson_bytes = json.dumps(feature_geojson).encode('utf-8')
        filename = f"{uuid.uuid4().hex}_{place_id}.geojson"

        # Persist raw_geo_data to storage and generate access_url
        access_url: Optional[str] = None
        if raw_geo:
            # decide filename
            # filename = f"{uuid.uuid4().hex}_{place_id}.kml"
            #content_bytes = raw_geo.encode("utf-8") 
            if USE_AZURE:
                from azure.storage.blob import BlobServiceClient
                blob_svc = BlobServiceClient.from_connection_string(AZ_CONN)
                container = blob_svc.get_container_client(AZ_CONTAINER)
                container.upload_blob(name=filename, data=geojson_bytes)
                access_url = f"{container.url}/{filename}"
            else:
                file_path = os.path.join(LOCAL_UPLOAD_DIR, filename)
                with open(file_path, "wb") as f:
                    f.write(geojson_bytes)
                access_url = f"{BASE_URL}/uploads/{filename}"

        # build bounding box WKT if available
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
            "access_url":      access_url,
            "format":          None,
            "llm_description": display_name,
            "bounding_box":    bounding_box,
            "score":           importance,
        })

    return {"query": query, "results": results}

# --- New Geoprocessing Endpoint ---
from typing import Any
class GeoProcessRequest(BaseModel):
    query: str
    layer_urls: List[str]  # URLs to existing GeoJSON files in the uploads folder

class GeoProcessResponse(BaseModel):
    layer_urls: List[str]            # URL to the new GeoJSON file
    tools_used: Optional[List[str]] = None
    
@app.post("/api/geoprocess", response_model=GeoProcessResponse)
async def geoprocess(req: GeoProcessRequest):
    """
    Accepts a natural language query and a list of GeoJSON URLs.
    Loads the GeoJSON from local storage, delegates processing to the geoprocess executor,
    then saves the resulting FeatureCollection and returns its URL.
    """
    # 0) Load GeoJSON features from provided URLs
    input_layers: List[Dict[str, Any]] = []
    for url in req.layer_urls:
        filename = os.path.basename(url)
        path = os.path.join(LOCAL_UPLOAD_DIR, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                gj = json.load(f)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Could not load {url}: {exc}")
        if gj.get("type") == "FeatureCollection":
            input_layers.extend(gj.get("features", []))
        elif gj.get("type") == "Feature":
            input_layers.append(gj)

    state = {
        "query": req.query,
        "input_layers": input_layers,
        "available_operations": [
            # backend-supported operations
            "buffer", "intersection", "union", "clip", "difference", "simplify"
        ],
        "tool_sequence": [],  # to be filled by the agent
    }
    # 2) Invoke geoprocess agent (stubbed service)
    from services.agents.geoprocessing_agent import geoprocess_executor
    
    final_state = await geoprocess_executor(state)


    # 3) Execute each step in the tool sequence
    result_layers = final_state.get("result_layers", [])
    tools_used = final_state.get("tool_sequence", [])

    # Note: actual tool implementations should be invoked here, e.g.:
    # for step in tools_used:
    #     tool = TOOL_REGISTRY[step["operation"]]
    #     result = tool(step["layers"], **step.get("params", {}))
    #     result_layers = [result]

    # 4) Write output as a new GeoJSON file in uploads
    out_urls=[]
    for result_layer in result_layers:
        out_filename = f"{uuid.uuid4().hex}_geoprocess.geojson"
        out_path = os.path.join(LOCAL_UPLOAD_DIR, out_filename)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result_layer, f)
        out_url = f"{BASE_URL}/uploads/{out_filename}"
        out_urls.append(out_url)
    #output_fc = {"type": "FeatureCollection", "features": result_layers}
    #out_filename = f"{uuid.uuid4().hex}_geoprocess.geojson"
    #out_path = os.path.join(LOCAL_UPLOAD_DIR, out_filename)
    #with open(out_path, "w", encoding="utf-8") as f:
    #    json.dump(output_fc, f)
    #out_url = f"{BASE_URL}/uploads/{out_filename}"

    # 5) Return the URL of the new file
    return GeoProcessResponse(
        layer_urls=out_urls,
        tools_used=tools_used
    )
    
    
@app.post("/api/orchestrate", response_model=OrchestratorResponse)
async def orchestrate(req: OrchestratorRequest):
    state = {"messages": [m.dict() for m in req.messages], "next": ""}
    final_state = await multi_agent_executor.ainvoke(state)
    return OrchestratorResponse(messages=final_state["messages"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
