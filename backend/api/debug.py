import io
import json
import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from kml2geojson.main import convert as kml2geojson_convert
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel

from core.config import BASE_URL, LOCAL_UPLOAD_DIR
from models.geodata import DataOrigin, DataType, GeoDataObject
from models.messages.chat_messages import (
    NaLaMapRequest,
    NaLaMapResponse,
    OrchestratorRequest,
    OrchestratorResponse,
)
from services.agents.langgraph_agent import SearchState, executor
from services.multi_agent_orch import multi_agent_executor
from services.tools.geocoding import geocode_using_nominatim
from utility.string_methods import clean_allow

# Geo conversion


router = APIRouter()


@router.post("/api/search", tags=["debug"], response_model=NaLaMapResponse)
async def search(req: NaLaMapRequest):
    state = SearchState(raw_query=req.query)
    result_state = await executor.ainvoke(state)
    numresults = result_state["num_results"]
    results: List[GeoDataObject] = result_state["results"]
    # Decide which message to send based on whether we got anything back
    if numresults == 0:
        human_msg = HumanMessage("Search layers for “{req.query}”")
        ai_msg = AIMessage("I'm sorry, I couldn't find any datasets matching your criteria.")
    else:
        human_msg = HumanMessage(f"{req.query}")
        ai_msg = AIMessage("Here are relevant layers:")

    # global_geodata=req.global_geodata
    # global_geodata.extend(results)

    return NaLaMapResponse(
        messages=[*req.messages, human_msg, ai_msg],
        results_title="Search Results",
        geodata_results=results,
        geodata_layers=req.geodata_layers,
        options=req.options,
    )  # , global_geodata=global_geodata)


@router.post("/api/geocode", tags=["debug"], response_model=NaLaMapResponse)
async def geocode(req: NaLaMapRequest) -> Dict[str, Any]:
    """Geocode the given request using the OpenStreetMap API.
    Returns and geokml some additional information."""
    # futue input: request: NaLaMapRequest
    response: str = "Geocoding results:"
    messages: List[BaseMessage] = [
        *(req.messages or []),
        HumanMessage(f"Geocode {req.query}!"),
        AIMessage(response),
    ]
    # 1) Invoke the tool (returns a JSON string)
    raw = geocode_using_nominatim.invoke({"query": req.query, "geojson": True})
    # 2) Parse into a Python dict, handling single-quoted JSON safely
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: convert single quotes to double quotes for JSON parsing
        fixed = raw.replace("'", '"')
        data = json.loads(fixed)

    # TODO: Adapt tool to add GeoDataObject to calling state and summary or so

    geocodeResponse: NaLaMapResponse = NaLaMapResponse(
        results_title="Geocoding Results:",
        geodata_layers=req.geodata_layers,
        options=req.options,
    )
    geocodeResponse.messages = messages

    # 3) Build our own result list
    geodata: List[GeoDataObject] = []
    # Nominatim returns a list of places
    for props in data:
        place_id = str(props.get("place_id"))
        display_name = props.get("display_name")
        name_prop = props.get("name")
        importance = props.get("importance")
        bbox = props.get("boundingbox")  # [lat_min, lat_max, lon_min, lon_max]

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

        # Convert GeoKML to GeoJSON
        geo_kml_string: str = """<?xml version="1.0" encoding="UTF-8"?>
            <kml xmlns="http://www.opengis.net/kml/2.2">
              <Document>
                <Placemark>
                  ${raw_geo}
                </Placemark>
              </Document>
            </kml>
            """

        geojson_dict = kml2geojson_convert(io.StringIO(geo_kml_string))
        # print(json.dump(geojson_dict))

        out_filename = f"{clean_allow(name_prop)}_geocode_{uuid.uuid4().hex}.geojson"
        out_path = os.path.join(LOCAL_UPLOAD_DIR, out_filename)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(geojson_dict, f)
        out_url = f"{BASE_URL}/uploads/{out_filename}"

        # Copy selected properties
        properties: Dict[str, Any] = dict()
        for property in [
            "place_id",
            "licence",
            "osm_type",
            "osm_id",
            "lat",
            "lon",
            "class",
            "type",
            "place_rank",
            "addresstype",
            "address",
        ]:
            if property in props:
                properties[property] = props.get(property)

        geodata.append(
            GeoDataObject(
                id=place_id,
                data_source_id="geocode",
                data_type=DataType.GEOJSON,
                data_origin=DataOrigin.TOOL,
                data_source=props.get("licence"),
                data_link=out_url,
                name=name_prop,
                title=name_prop,
                description=display_name,
                llm_description=display_name,
                score=importance,
                bounding_box=bounding_box,
                layer_type="GeoJSON",
                properties=properties,
            )
        )
    geocodeResponse.geodata_results = geodata

    # global_geodata=req.global_geodata
    # global_geodata.extend(geodata)
    # geocodeResponse.global_geodata=global_geodata

    return geocodeResponse


@router.post("/api/orchestrate", tags=["debug"], response_model=OrchestratorResponse)
async def orchestrate(req: OrchestratorRequest):
    state = {"messages": [m.dict() for m in req.messages], "next": ""}
    final_state = await multi_agent_executor.ainvoke(state)

    return OrchestratorResponse(messages=final_state["messages"])


# --- New Geoprocessing Endpoint ---
class GeoProcessRequest(BaseModel):
    query: str
    layer_urls: List[str]  # URLs to existing GeoJSON files in the uploads folder


class GeoProcessResponse(BaseModel):
    layer_urls: List[str]  # URL to the new GeoJSON file # TODO: Move API Endpoint to GeoData Model
    tools_used: Optional[List[str]] = None


@router.post("/api/geoprocess", response_model=NaLaMapResponse)
async def geoprocess(req: NaLaMapRequest):
    """
    Accepts a natural language query and a list of GeoJSON URLs.
    Loads the GeoJSON from local storage, delegates processing to the geoprocess executor,
    then saves the resulting FeatureCollection and returns its URL.
    """
    # Get layer urls from request:
    layer_urls = [
        gd.data_link
        for gd in req.geodata
        if gd.data_type == DataType.GEOJSON or gd.data_type == DataType.UPLOADED
    ]
    result_name = "and".join(
        gd.name
        for gd in req.geodata
        if gd.data_type == DataType.GEOJSON or gd.data_type == DataType.UPLOADED
    )
    # 0) Load GeoJSON features from provided URLs
    input_layers: List[Dict[str, Any]] = []
    for url in layer_urls:
        filename = os.path.basename(url)
        path = os.path.join(LOCAL_UPLOAD_DIR, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                gj = json.load(f)
        except Exception:
            raise HTTPException(status_code=400, detail=f"Could not load {url}")
        if isinstance(gj, List):  # GeoJSON list? TODO: Verify GeoCoding
            gj = gj[0]
        if gj.get("type") == "FeatureCollection":
            # input_layers.extend(gj.get("features", []))
            input_layers.append(gj)
        elif gj.get("type") == "Feature":
            fc = {"type": "FeatureCollection", "features": [gj]}
            input_layers.append(fc)

    state = {
        "query": req.query,
        "input_layers": input_layers,
        "available_operations_and_params": [
            # backend-supported operations
            "operation: buffer params: radius=1000, buffer_crs=EPSG:3857",
            "operation: intersection params:",
            "operation: union params:",
            "operation: clip params:",
            "operation: difference params:",
            "operation: simplify params: tolerance=0.01",
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
    if tools_used:
        tools_name = "and".join(tool for tool in tools_used)
        result_name = result_name + tools_name
    new_geodata: List[GeoDataObject] = []
    # 4) Write output as a new GeoJSON file in uploads
    out_urls = []
    for result_layer in result_layers:
        out_uuid: str = uuid.uuid4().hex
        out_filename = f"{out_uuid}_geoprocess.geojson"
        out_path = os.path.join(LOCAL_UPLOAD_DIR, out_filename)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result_layer, f)
        out_url = f"{BASE_URL}/uploads/{out_filename}"
        out_urls.append(out_url)
        new_geodata.append(
            GeoDataObject(
                id=out_uuid,
                data_source_id="geoprocess",
                data_type=DataType.GEOJSON,
                data_origin=DataOrigin.TOOL,
                data_source="NaLaMapGeoprocess",
                data_link=out_url,
                name=result_name,
                title=result_name,
                description=result_name,
                llm_description=result_name,
                score=0.2,
                bounding_box=None,
                layer_type="GeoJSON",
                properties=None,
            )
        )
    # output_fc = {"type": "FeatureCollection", "features": result_layers}
    # out_filename = "{uuid.uuid4().hex}_geoprocess.geojson"
    # out_path = os.path.join(LOCAL_UPLOAD_DIR, out_filename)
    # with open(out_path, "w", encoding="utf-8") as f:
    #    json.dump(output_fc, f)
    # out_url = "{BASE_URL}/uploads/{out_filename}"

    # 5) Return the URL of the new file
    # return GeoProcessResponse(
    #    layer_urls=out_urls,
    #    tools_used=tools_used
    # )

    # global_geodata=req.global_geodata
    # global_geodata.extend(new_geodata)

    # Convert to common Geodatamodel
    response_str: str = "Here are the processing results, used Tools: {', '.join(tools_used)}:"
    geodataResponse: NaLaMapResponse = NaLaMapResponse(
        geodata_layers=req.geodata_layers, options=req.options
    )
    geodataResponse.geodata_results = new_geodata
    # geodataResponse.global_geodata=global_geodata
    geodataResponse.messages = [*req.messages, AIMessage(response_str)]
    return geodataResponse
