# services/agents/geoprocessing_agent.py
import geopandas as gpd
from models.geodata import DataOrigin, DataType, GeoDataObject
from typing_extensions import Annotated
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langchain_core.tools.base import InjectedToolCallId
from models.states import GeoDataAgentState, get_medium_debug_state
from models.geodata import GeoDataIdentifier, GeoDataObject
from langchain_core.messages import ToolMessage
from pydantic import BaseModel, Field
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
import os
import uuid
from core.config import BASE_URL, LOCAL_UPLOAD_DIR
import json
# LLM import
from langchain_core.messages import HumanMessage
from services.ai.llm_config import get_llm

def get_last_human_content(messages):
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content
    raise ValueError("No human message found in context")

def _flatten_features(layers):
    """
    Given a list of Feature or FeatureCollection dicts, return a flat list of Feature dicts.
    """
    feats = []
    for layer in layers:
        if layer.get("type") == "FeatureCollection":
            feats.extend(layer.get("features", []))
        elif layer.get("type") == "Feature":
            feats.append(layer)
        else:
            # skip invalid entries
            continue
    return feats


def _get_layer_geoms(layers):
    """
    Given a list of Feature or FeatureCollection dicts, return a list of shapely geometries,
    each being the unary_union of one layer's features.
    """
    geoms = []
    for layer in layers:
        feats = layer.get("features") if layer.get("type") == "FeatureCollection" else ([layer] if layer.get("type") == "Feature" else [])
        if not feats:
            continue
        gdf = gpd.GeoDataFrame.from_features(feats)
        geoms.append(gdf.unary_union)
    return geoms


def op_buffer(layers, radius=10000, buffer_crs="EPSG:3857", radius_unit="meters"):
    """
    Buffers features of a single input layer item individually.
    If multiple layers are provided, this function will raise a ValueError.
    Input geometries are assumed in EPSG:4326. This function:
      1) Expects `layers` to be a list containing a single layer item (FeatureCollection or Feature).
      2) Converts radius to meters based on radius_unit (default is "meters").
      3) Extracts features from the single layer item.
      4) Creates a GeoDataFrame from these features.
      5) Reprojects the GeoDataFrame to buffer_crs (default EPSG:3857, which uses meters).
      6) Applies buffer to each feature geometry with the meter-based radius.
      7) Reprojects the GeoDataFrame (with buffered features) back to EPSG:4326.
      8) Returns a list containing one FeatureCollection with the individually buffered features.
    Supported radius_unit: "meters", "kilometers", "miles".
    """
    if not layers:
        return [] # No input layer, return empty list
    
    if len(layers) > 1:
        raise ValueError("Buffer operation error: Only one layer can be buffered at a time. Please specify a single target layer.")
    
    layer_item = layers[0] # Process the single layer provided

    actual_radius_meters = float(radius)
    if radius_unit.lower() == "kilometers":
        actual_radius_meters *= 1000
    elif radius_unit.lower() == "miles":
        actual_radius_meters *= 1609.34
    elif radius_unit.lower() != "meters":
        print(f"Warning: Unknown radius_unit '{radius_unit}'. Assuming meters.")

    current_features = []
    if isinstance(layer_item, dict):
        if layer_item.get("type") == "FeatureCollection":
            current_features = layer_item.get("features", [])
        elif layer_item.get("type") == "Feature":
            current_features = [layer_item]
    
    if not current_features:
        # This case might occur if the single layer_item was an empty FeatureCollection or invalid
        print(f"Warning: The provided layer item is empty or not a recognizable Feature/FeatureCollection: {type(layer_item)}")
        return []

    gdf = gpd.GeoDataFrame.from_features(current_features)
    if gdf.empty:
        return [] # GeoDataFrame is empty, nothing to buffer
    
    gdf.set_crs("EPSG:4326", inplace=True)
    
    gdf_reprojected = gdf.to_crs(buffer_crs)
    gdf_reprojected['geometry'] = gdf_reprojected.geometry.buffer(actual_radius_meters)
    gdf_buffered_individual = gdf_reprojected.to_crs("EPSG:4326")
    
    if gdf_buffered_individual.empty:
        return [] # Resulting GeoDataFrame is empty
        
    fc = json.loads(gdf_buffered_individual.to_json())
    return [fc] # Return a list containing the single FeatureCollection



def op_intersection(layers, **kwargs):
    """Intersects one FeatureCollection with another (works for N layers)."""
    geoms = _get_layer_geoms(layers)
    if not geoms:
        return []
    inter = geoms[0]
    for geom in geoms[1:]:
        inter = inter.intersection(geom)
    series = gpd.GeoSeries([inter])
    fc = json.loads(series.to_json())
    return [fc]


def op_union(layers, **kwargs):
    """Unions all input FeatureCollections into one or more geometries."""
    geoms = _get_layer_geoms(layers)
    if not geoms:
        return []
    union_geom = unary_union(geoms)
    series = gpd.GeoSeries([union_geom])
    fc = json.loads(series.to_json())
    return [fc]


def op_difference(layers, **kwargs):
    """Subtracts the second FeatureCollection from the first."""
    geoms = _get_layer_geoms(layers)
    if not geoms:
        return []
    base = geoms[0]
    sub = geoms[1] if len(geoms) > 1 else None
    diff = base.difference(sub) if sub else base
    series = gpd.GeoSeries([diff])
    fc = json.loads(series.to_json())
    return [fc]


def op_clip(layers, **kwargs):
    """Clips the first FeatureCollection by the second."""
    if len(layers) < 2:
        return _flatten_features(layers)
    subj_feats = layers[0].get("features", []) if layers[0].get("type") == "FeatureCollection" else [layers[0]]
    mask_feats = layers[1].get("features", []) if layers[1].get("type") == "FeatureCollection" else [layers[1]]
    subj_gdf = gpd.GeoDataFrame.from_features(subj_feats)
    mask_geom = unary_union(gpd.GeoDataFrame.from_features(mask_feats).geometry)
    subj_gdf['geometry'] = subj_gdf.geometry.intersection(mask_geom)
    fc = json.loads(subj_gdf.to_json())
    return [fc]


def op_simplify(layers, tolerance=0.01):
    """Simplifies each feature geometry with the given tolerance."""
    feats = _flatten_features(layers)
    if not feats:
        return []
    gdf = gpd.GeoDataFrame.from_features(feats)
    gdf['geometry'] = gdf.geometry.simplify(tolerance)
    fc = json.loads(gdf.to_json())
    return [fc]


# Registry of available tools
TOOL_REGISTRY = {
    "buffer": op_buffer,
    "intersection": op_intersection,
    "union": op_union,
    "difference": op_difference,
    "clip": op_clip,
    "simplify": op_simplify
}

# ========== Geoprocess Executor ==========
def geoprocess_executor(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Uses an LLM to plan a sequence of geoprocessing operations based on a natural-language query
    and executes them in order against the input GeoJSON layers.

    Returns:
      - tool_sequence: List of operation names executed
      - result_layers: List of GeoJSON Feature dicts
    """
    query = state.get("query", "")
    layers: List[Dict[str, Any]] = state.get("input_layers", [])
    available_ops: List[str] = state.get("available_operations_and_params", [])

    # 0) Summarize layers to metadata to reduce context size
    layer_meta = []
    for feat in layers:
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        # get geometry type and bbox if present
        gtype = geom.get("type")
        coords = geom.get("coordinates")
        # simplistic bbox extraction: assume Feature has 'bbox' prop
        bbox = feat.get("bbox") or props.get("bbox")
        layer_meta.append({
            "resource_id": props.get("resource_id"),
            "name": props.get("name"),
            "geometry_type": gtype,
            "bbox": bbox
        })

        # 1) Invoke LLM planner with metadata only
    llm = get_llm()
    system_msg = (
        "You are a geospatial processing assistant. "
        "You have the following input layers with metadata (id, name, geometry_type, bbox). "
        "Based on the user request and available operations, choose the best sequence of operations. "
        "Return a JSON object with a top-level key steps whose value is an array of objects. Each object must have exactly two keys:"
        + ", ".join(available_ops) + "). Dont define at any operation params with layer or layers as all functions are called as func(layers: result, **params)"
        "Example Output:"
        """
        {
        "steps": [
            {
            "operation": "buffer",
            "params": { "radius": 3000, "radius_unit": "meters" }
            },
            {
            "operation": "clip",
            "params": {}
            }
        ]
        }
        """
    )
    user_payload = {
        "query": query,
        "available_operations": available_ops,
        "layers": layer_meta
    }
    user_msg = json.dumps(user_payload)

    # Use LangChain chat generate methods since AzureChatOpenAI doesn't have .chat()
    from langchain.schema import SystemMessage, HumanMessage
    messages = [SystemMessage(content=system_msg), HumanMessage(content=user_msg)]
    # agenerate expects a list of message lists for batching
    response = llm.generate([messages])  
    # extract text from first generation
    content = response.generations[0][0].text

    try:
        plan = json.loads(content)
    except json.JSONDecodeError:
        raise ValueError(f"Failed to parse LLM response as JSON: {content}")
    
    steps = plan.get("steps", [])

    # 2) Execute each step on full geojson layers on full geojson layers
    result = layers
    executed_ops = []
    for step in steps:
        op_name = step.get("operation")
        params = step.get("params", {})
        func = TOOL_REGISTRY.get(op_name)
        if func:
            result = func(result, **params)
            executed_ops.append(op_name)

    return {
        "tool_sequence": executed_ops,
        "result_layers": result
    }

@tool
def geoprocess_tool(
    state:  Annotated[GeoDataAgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Union[Dict[str, Any], Command]:
    """
    Tool to geoprocess geospatial layers and datasets (geodata_layers) based on the user request and available operations (buffer, intersection, union, difference, clip).
    """
    # Safely pull out the list (defaults to [] if key missing or None)
    layers = state.get("geodata_layers") or []
    messages = state.get("messages") or []
    if not layers:
        raise ValueError("No geodata_layers found in state!")
    layer_urls = [
        gd.data_link
        for gd in layers
        if gd.data_type in (DataType.GEOJSON, DataType.UPLOADED)
    ]
    # name derived from input layers
    result_name = "and".join(
        gd.name for gd in layers
        if gd.data_type in (DataType.GEOJSON, DataType.UPLOADED)
    )

    # Load all the GeoJSON feature collections
    input_layers: List[Dict[str, Any]] = []
    for url in layer_urls:
        filename = os.path.basename(url)
        path = os.path.join(LOCAL_UPLOAD_DIR, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                gj = json.load(f)
        except Exception as exc:
            raise ValueError(f"Failed to read {path}: {exc}")

        # Normalize to FeatureCollection
        if isinstance(gj, list):
            gj = gj[0]
        if gj.get("type") == "FeatureCollection":
            input_layers.append(gj)
        elif gj.get("type") == "Feature":
            input_layers.append({
                "type": "FeatureCollection",
                "features": [gj],
            })
    
    query=get_last_human_content(messages)
    # 2) Build the state for the geoprocess executor
    processing_state = {
        "query": query,
        "input_layers": input_layers,
        "available_operations_and_params": [
            "operation: buffer params: radius=1000, radius_unit='meters', buffer_crs=EPSG:3857",
            "operation: intersection params:",
            "operation: union params:",
            "operation: clip params:",
            "operation: difference params:",
            "operation: simplify params: tolerance=0.01"
        ],
        "tool_sequence": [],  # will be filled by the executor
    }

    # 3) Run the (formerly async) executor synchronously
    final_state = geoprocess_executor(processing_state)

    # 4) Collect results
    result_layers = final_state.get("result_layers", [])
    tools_used   = final_state.get("tool_sequence", [])
    if tools_used:
        tools_name='and'.join(tool for tool in tools_used)
        result_name=result_name+tools_name
    # Build new GeoDataObjects
    new_geodata: List[GeoDataObject] = []
    out_urls: List[str] = []
    for layer in result_layers:
        out_uuid = uuid.uuid4().hex
        filename = f"{out_uuid}_geoprocess.geojson"
        path = os.path.join(LOCAL_UPLOAD_DIR, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(layer, f)

        url = f"{BASE_URL}/uploads/{filename}"
        out_urls.append(url)
        new_geodata.append(GeoDataObject(
            id=out_uuid,
            data_source_id="geoprocess",
            data_type=DataType.GEOJSON,
            data_origin=DataOrigin.TOOL,
            data_source="GeoweaverGeoprocess",
            data_link=url,
            name=result_name,
            title=result_name,
            description=result_name,
            llm_description=result_name,
            score=0.2,
            bounding_box=None,
            layer_type="GeoJSON",
            properties=None
        ))

    # 5) Return the update command
    return Command(
        update={
            "messages": [
                ToolMessage(name="geoprocess_tool", content="Tools used: " + ", ".join(tools_used) + f". Added GeoDataObjects into the global_state, use id and data_source_id for reference: {json.dumps([ {"id": result.id, "data_source_id": result.data_source_id, "title": result.title} for result in new_geodata])}", tool_call_id=tool_call_id)
            ],
            "global_geodata": new_geodata,
            "geodata_results": new_geodata
        }
    )