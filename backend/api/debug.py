from fastapi import APIRouter, Query
from typing import List, Optional, Any, Dict
import json

from models.messages.chat_messages import OrchestratorRequest, OrchestratorResponse
from services.multi_agent_orch import multi_agent_executor
from services.agents.langgraph_agent import executor, SearchState
from services.tools.geocoding import geocode_using_nominatim


router = APIRouter()

@router.get("/api/search", tags=["debug"])
async def search(query: str = Query()):
    """
    Searches the annotated datasets provided by the librarian 
    """
    state = SearchState(query=query)  
    results = await executor.ainvoke(state)
    return results


@router.get("/api/geocode", tags=["debug"])
async def geocode(query: str = Query(...)) -> Dict[str, Any]:
    """
    Geocode the given request using the OpenStreetMap API. Returns and geokml some additional information.
    """
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

@router.post("/api/orchestrate", tags=["debug"], response_model=OrchestratorResponse)
async def orchestrate(req: OrchestratorRequest):
    state = {
        "messages": [m.dict() for m in req.messages],
        "next": ""
    }
    final_state = await multi_agent_executor.ainvoke(state)


    return OrchestratorResponse(messages=final_state["messages"])
