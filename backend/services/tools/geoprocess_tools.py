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
        # Extract layer names/titles if available for better error information
        layer_info = []
        for i, layer in enumerate(layers):
            name = None
            if isinstance(layer, dict):
                props = layer.get("properties", {})
                if props:
                    name = props.get("name") or props.get("title")
                # Also try to get name from features if it's a FeatureCollection
                if not name and layer.get("type") == "FeatureCollection" and layer.get("features"):
                    first_feat = layer["features"][0] if layer["features"] else None
                    if first_feat and isinstance(first_feat, dict):
                        props = first_feat.get("properties", {})
                        if props:
                            name = props.get("name") or props.get("title")
            layer_info.append(f"Layer {i+1}" + (f": {name}" if name else ""))
        
        layer_desc = ", ".join(layer_info)
        raise ValueError(f"Buffer operation error: Only one layer can be buffered at a time. Received {len(layers)} layers: {layer_desc}. Please specify a single target layer.")
    
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
    """Clips the first FeatureCollection by the second.
    If fewer than two layers are provided, the original layers are returned unchanged.
    """
    if len(layers) < 2:
        # Not enough layers to perform a clip, return the input layers as is.
        # The geoprocess_executor expects a list of layer-like objects (e.g., FeatureCollections).
        return layers
    
    # Proceed with clipping logic if 2 or more layers are present
    # (Assuming the first layer is subject, second is mask for this basic example)
    subj_layer = layers[0]
    mask_layer = layers[1]

    subj_feats = []
    if subj_layer and isinstance(subj_layer, dict) and subj_layer.get("type") == "FeatureCollection":
        subj_feats = subj_layer.get("features", [])
    elif subj_layer and isinstance(subj_layer, dict) and subj_layer.get("type") == "Feature":
        subj_feats = [subj_layer]
    
    mask_feats = []
    if mask_layer and isinstance(mask_layer, dict) and mask_layer.get("type") == "FeatureCollection":
        mask_feats = mask_layer.get("features", [])
    elif mask_layer and isinstance(mask_layer, dict) and mask_layer.get("type") == "Feature":
        mask_feats = [mask_layer]

    if not subj_feats or not mask_feats:
        # If subject or mask is effectively empty, return original subject layer(s) or all layers
        # to avoid errors and indicate no clip occurred or was possible.
        # Depending on desired strictness, could also return empty list or raise error.
        print("Warning: op_clip called with insufficient features in subject or mask layer(s). Returning original layers.")
        return layers 

    subj_gdf = gpd.GeoDataFrame.from_features(subj_feats)
    if subj_gdf.empty:
        return [{"type": "FeatureCollection", "features": []}] # Return empty FC if subject is empty
    subj_gdf.set_crs("EPSG:4326", inplace=True) # Assume input is 4326

    mask_gdf = gpd.GeoDataFrame.from_features(mask_feats)
    if mask_gdf.empty:
        # No mask to clip with, return original subject features as a FeatureCollection
        print("Warning: op_clip called with an empty mask layer. Returning original subject layer.")
        # Ensure subject_gdf is converted back to the expected list-of-FCs format
        fc = json.loads(subj_gdf.to_json())
        return [fc]
    mask_gdf.set_crs("EPSG:4326", inplace=True) # Assume input is 4326

    # Ensure CRSs match before spatial operations if they might differ; for now, assume they are aligned or handled by user.
    # Reprojecting to a common projected CRS might be needed for accurate geometric operations if inputs are geographic.
    # However, if inputs are already EPSG:4326, intersection works but on degrees.
    # For simplicity here, proceeding with whatever CRS they have (assumed EPSG:4326).

    mask_geom = mask_gdf.geometry.unary_union
    if mask_geom.is_empty:
        print("Warning: op_clip mask geometry is empty. Returning original subject layer.")
        fc = json.loads(subj_gdf.to_json())
        return [fc]

    # Perform the clip (intersection)
    # Note: geopandas.clip is more robust, but uses intersection on GeoDataFrames
    try:
        # Ensure subj_gdf has a valid CRS before to_crs, if it might be lost
        if subj_gdf.crs is None:
             subj_gdf.set_crs("EPSG:4326", inplace=True)
        # It's often better to clip in a projected CRS if inputs are geographic
        # For this example, let's assume we work in the input CRS (e.g. EPSG:4326)
        # or that reprojection is handled by the LLM plan if needed.
        
        clipped_gdf = subj_gdf.clip(mask_geom) # gpd.clip requires mask to be a geometry or GeoDataFrame/Series
    
    except Exception as e:
        print(f"Error during geopandas clip operation: {e}. Returning original subject layer.")
        # Fallback: return original subject layer as a FeatureCollection list
        fc = json.loads(subj_gdf.to_json())
        return [fc]

    if clipped_gdf.empty:
        return [{"type": "FeatureCollection", "features": []}]

    fc = json.loads(clipped_gdf.to_json())
    return [fc] # Return a list containing the single clipped FeatureCollection


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
        "You are a geospatial task execution assistant. Your sole job is to translate the user's most recent request into a single geoprocessing operation and its parameters."
        "1. Examine the user's query closely: {query_json_string}."
        "2. Identify the single most appropriate geoprocessing operation from the available list: {available_operations_list_json_string}."
        "3. CRITICAL FOR BUFFER OPERATION: If the chosen operation is 'buffer', you MUST extract 'radius' (a number) and 'radius_unit' (e.g., 'meters', 'kilometers', 'miles') directly and precisely from the user's query. For example, if the user says 'buffer by 100 km', your parameters MUST be `{{\"radius\": 100, \"radius_unit\": \"kilometers\"}}`. If they say 'buffer by 50000 meters', params MUST be `{{\"radius\": 50000, \"radius_unit\": \"meters\"}}`. DO NOT use default values if the user specifies values; use exactly what the user provided."
        "4. For other operations, extract necessary parameters as defined in their descriptions from the user's query."
        "5. Return a JSON object structured EXACTLY as follows: `{{\"steps\": [{{\"operation\": \"chosen_operation_name\", \"params\": {{extracted_parameters}}}}]}}`. The 'steps' array MUST contain exactly one operation object."
        "The execution framework handles which layer(s) are passed to the operation; you do not control this with parameters."
        "Example for a user query 'buffer the_roads by 5 kilometers':"
        "```json\n"
        "{{\n"
        "  \"steps\": [\n"
        "    {{\n"
        "      \"operation\": \"buffer\",\n"
        "      \"params\": {{ \"radius\": 5, \"radius_unit\": \"kilometers\" }}\n"
        "    }}\n"
        "  ]\n"
        "}}\n"
        "```"
    ).format(
        query_json_string=json.dumps(query),
        available_operations_list_json_string=json.dumps(available_ops) 
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
        # Strip markdown code blocks if present
        cleaned_content = content
        # Check for markdown code block format: ```json ... ```
        if cleaned_content.strip().startswith("```") and "```" in cleaned_content.strip()[3:]:
            # Extract content between first ``` and last ```
            first_delimiter = cleaned_content.find("```")
            last_delimiter = cleaned_content.rfind("```")
            if first_delimiter != last_delimiter:
                # Extract content after first ``` line and before last ```
                lines = cleaned_content.split("\n")
                start_line = 0
                for i, line in enumerate(lines):
                    if "```" in line:
                        start_line = i
                        break
                # Get content starting from the line after the first ``` line
                cleaned_content = "\n".join(lines[start_line+1:])
                # Remove the last ``` and anything after it
                if "```" in cleaned_content:
                    cleaned_content = cleaned_content.split("```")[0]
        
        # Try to parse the cleaned content
        plan = json.loads(cleaned_content)
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
    state: Annotated[GeoDataAgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    target_layer_id: Optional[str] = None,
    operation: Optional[str] = None
) -> Union[Dict[str, Any], Command]:
    """
    Tool to geoprocess a specific geospatial layer from the state.
    
    Args:
        state: The agent state containing geodata_layers
        tool_call_id: ID for this tool call
        target_layer_id: ID of the specific layer to process. If not provided, will attempt to determine from context.
        operation: Optional operation hint (buffer, intersection, etc.)
    
    The tool will apply operations like buffer, intersection, union, difference, or clip to the specified layer.
    """
    # Safely pull out the list (defaults to [] if key missing or None)
    layers = state.get("geodata_layers") or []
    messages = state.get("messages") or []
    
    if not layers:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        name="geoprocess_tool", 
                        content="Error: No geodata layers found in state. Please add or select layers first.", 
                        tool_call_id=tool_call_id,
                        status="error"
                    )
                ]
            }
        )
    
    # If target_layer_id is provided, filter to just that layer
    selected_layers = []
    if target_layer_id:
        selected_layers = [layer for layer in layers if layer.id == target_layer_id]
        if not selected_layers:
            # Provide a helpful error with available layer IDs
            available_layers = [{"id": layer.id, "title": layer.title} for layer in layers]
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            name="geoprocess_tool", 
                            content=f"Error: Layer with ID '{target_layer_id}' not found. Available layers: {json.dumps(available_layers)}", 
                            tool_call_id=tool_call_id,
                            status="error"
                        )
                    ]
                }
            )
    else:
        # If no specific layer ID was provided, use only the first layer
        # This prevents the multiple-layer error
        selected_layers = [layers[0]]
    
    # Get URLs for the selected layers only
    layer_urls = [
        layer.data_link
        for layer in selected_layers
        if layer.data_type in (DataType.GEOJSON, DataType.UPLOADED)
    ]
    
    # Name derived from input layer
    result_name = selected_layers[0].name if selected_layers else ""

    # Load the selected GeoJSON feature collections
    input_layers: List[Dict[str, Any]] = []
    for url in layer_urls:
        filename = os.path.basename(url)
        path = os.path.join(LOCAL_UPLOAD_DIR, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                gj = json.load(f)
        except Exception as exc:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            name="geoprocess_tool", 
                            content=f"Error: Failed to read {path}: {exc}", 
                            tool_call_id=tool_call_id,
                            status="error"
                        )
                    ]
                }
            )

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
    
    query = get_last_human_content(messages)
    # If operation was specified, add it to the query for better context
    if operation:
        query = f"{operation} {query}"
        
    # Build the state for the geoprocess executor
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

    try:
        # Run the executor
        final_state = geoprocess_executor(processing_state)
    except ValueError as e:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        name="geoprocess_tool", 
                        content=f"Error: {str(e)}\n Please fix your mistakes.", 
                        tool_call_id=tool_call_id,
                        status="error"
                    )
                ]
            }
        )

    # Collect results
    result_layers = final_state.get("result_layers", [])
    tools_used = final_state.get("tool_sequence", [])
    if tools_used:
        tools_name = ''.join(tool for tool in tools_used)
        result_name = result_name + tools_name
        
    # Build new GeoDataObjects
    new_geodata: List[GeoDataObject]
    if "geodata_results" not in state or state["geodata_results"] is None or not isinstance(state["geodata_results"], List):
        new_geodata = []
    else:
        new_geodata = state["geodata_results"]
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

    # Return the update command
    return Command(
        update={
            "messages": [
                ToolMessage(
                    name="geoprocess_tool", 
                    content="Tools used: " + ", ".join(tools_used) + f". Added GeoDataObjects into the global_state, use id and data_source_id for reference: {json.dumps([{'id': result.id, 'data_source_id': result.data_source_id, 'title': result.title} for result in new_geodata])}", 
                    tool_call_id=tool_call_id
                )
            ],
            #"global_geodata": new_geodata,
            "geodata_results": new_geodata
        }
    )