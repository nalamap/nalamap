# services/agents/geoprocessing_agent.py
import geopandas as gpd
import requests
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
import itertools
import os
import uuid
from core.config import BASE_URL, LOCAL_UPLOAD_DIR
import json
import logging
# LLM import
from langchain_core.messages import HumanMessage
from services.ai.llm_config import get_llm


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

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
             # skip anything that is not a Feature or FeatureCollection
            logger.debug(f"Skipping invalid GeoJSON layer: {layer}")
    return feats


def _get_layer_geoms(layers):
    """
    Given a list of GeoJSON Feature or FeatureCollection dicts, return a
    list of Shapely geometries, each being the unary_union of one layer's features.
    """
    geoms: List[Any] = []
    for layer in layers:
        layer_type = layer.get("type")
        if layer_type == "FeatureCollection":
            feats = layer.get("features", [])
        elif layer_type == "Feature":
            feats = [layer]
        else:
            logger.debug(f"Skipping layer with missing or invalid type: {layer_type}")
            continue

        if not feats:
            continue

        try:
            gdf = gpd.GeoDataFrame.from_features(feats)
            gdf.set_crs("EPSG:4326", inplace=True)
            geoms.append(gdf.unary_union)
        except Exception:
            logger.exception("Failed to convert features to GeoDataFrame")
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
        logger.warning("op_buffer called with no layers")
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
    unit = radius_unit.lower()
    factor = {"meters": 1.0, "kilometers": 1000.0, "miles": 1609.34}.get(unit)
    if factor is None:
        logger.warning(f"Unknown radius_unit '{radius_unit}', assuming meters")
        factor = 1.0

    actual_radius_meters = float(radius) * factor
    
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

    try:
        gdf = gpd.GeoDataFrame.from_features(current_features)
        gdf.set_crs("EPSG:4326", inplace=True)

        gdf_reprojected = gdf.to_crs(buffer_crs)
        gdf_reprojected['geometry'] = gdf_reprojected.geometry.buffer(actual_radius_meters)
        gdf_buffered_individual = gdf_reprojected.to_crs("EPSG:4326")

        if gdf_buffered_individual.empty:
            return [] # Resulting GeoDataFrame is empty

        fc = json.loads(gdf_buffered_individual.to_json())
        return [fc] # Return a list containing the single FeatureCollection
    except Exception as e:
        logger.exception(f"Error in op_buffer: {e}")


def op_centroid(layers: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
    """
    Compute the centroid of each feature in the first FeatureCollection and
    return a new FeatureCollection of Point features.
    """
    if not layers:
        return []
    layer = layers[0]
    feats = layer.get("features", [])
    if not feats:
        return []

    try:
        gdf = gpd.GeoDataFrame.from_features(feats)
        gdf.set_crs("EPSG:4326", inplace=True)
        centroids = gdf
        centroids['geometry'] = gdf.geometry.centroid
        fc = json.loads(centroids.to_json())
        return [fc]
    except Exception as e:
        logger.exception(f"Error in op_centroid: {e}")
        return []


def op_simplify(
    layers: List[Dict[str, Any]],
    tolerance: float = 0.01,
    preserve_topology: bool = True
) -> List[Dict[str, Any]]:
    """
    Simplify each feature in the first FeatureCollection with the given tolerance.
    - tolerance: distance parameter for simplification (in the layer's CRS units, usually degrees).
    - preserve_topology: whether to preserve topology during simplification.
    """
    feats = _flatten_features(layers)
    if not feats:
        return []
    try:
        gdf = gpd.GeoDataFrame.from_features(feats)
        gdf["geometry"] = gdf.geometry.simplify(tolerance, preserve_topology=preserve_topology)
        fc = json.loads(gdf.to_json())
        return [fc]
    except Exception as e:
        logger.exception(f"Error in op_simplify: {e}")
        return []
    
def op_overlay(
    layers: List[Dict[str, Any]],
    how: str = "intersection",
    crs: str = "EPSG:3857"
) -> List[Dict[str, Any]]:
    """
    Perform a set-based overlay across N layers. Supports 'intersection', 'union',
    'difference', 'symmetric_difference', and 'identity'. For N > 2, applies the operation iteratively:
      result = overlay(layer1, layer2, how)
      result = overlay(result, layer3, how)
      crs : str, default "EPSG:3857"
        Working Coordinate Reference System used *internally* for the overlay.
        Provide a projected CRS (e.g. equal-area or Web Mercator) for more
        accurate operations. **The output will always be reprojected to
        EPSG:4326.**
      ...
    Returns a single FeatureCollection (in a list) of the final result.
    """
    if len(layers) < 2:
        # Not enough layers to overlay; return original layers unchanged
        return layers
    
    # Helper: convert a layer to a GeoDataFrame in working CRS
    def _layer_to_gdf(layer: Dict[str, Any]) -> gpd.GeoDataFrame:
        feats = _flatten_features([layer])
        gdf = gpd.GeoDataFrame.from_features(feats)
        # Assume incoming CRS is WGS84 if undefined
        if gdf.crs is None:
            gdf.set_crs("EPSG:4326", inplace=True)
        return gdf.to_crs(crs)

    
    
    # Prepare the base layer
    try:
        result_gdf = _layer_to_gdf(layers[0])
    except Exception as exc:
        logger.exception("Error preparing base layer for overlay: %s", exc)
        return []
    

    # Iterate through the remaining layers
    for layer in layers[1:]:
        try:
            next_gdf = _layer_to_gdf(layer)
            result_gdf = gpd.overlay(result_gdf, next_gdf, how=how)

            # Exit early if the intermediate result is empty
            if result_gdf.empty:
                return [{"type": "FeatureCollection", "features": []}]

        except Exception as exc:
            logger.exception("Error during overlay with layer: %s", exc)
            return []

    # Re‑project the final result back to EPSG:4326 for output
    try:
        if not result_gdf.empty:
            result_gdf = result_gdf.to_crs("EPSG:4326")
    except Exception as exc:
        logger.exception("Error reprojecting result to EPSG:4326: %s", exc)
        return [{"type": "FeatureCollection", "features": []}]

    fc = json.loads(result_gdf.to_json())
    return [fc]

def op_merge(
    layers: List[Dict[str, Any]],
    on: Optional[List[str]] = None,
    how: str = "inner"
) -> List[Dict[str, Any]]:
    """
    Perform an attribute-based merge (join) between two layers.
    - layers: expects exactly two FeatureCollections.
    - on: list of column names to join on; if None, GeoPandas uses common columns.
    - how: one of 'inner', 'left', 'right', 'outer'.
    """
    if len(layers) < 2:
        return layers
    try:
        gdf1 = gpd.GeoDataFrame.from_features(layers[0].get("features", []))
        gdf2 = gpd.GeoDataFrame.from_features(layers[1].get("features", []))
        gdf1.set_crs("EPSG:4326", inplace=True)
        gdf2.set_crs("EPSG:4326", inplace=True)

        merged = gdf1.merge(gdf2.drop(columns="geometry"), on=on, how=how)
        # Retain geometry from gdf1
        merged.set_geometry(gdf1.geometry.name, inplace=True)
        return [json.loads(merged.to_json())]
    except Exception as e:
        logger.exception(f"Error in op_merge: {e}")
        return []


def op_sjoin(
    layers: List[Dict[str, Any]],
    how: str = "inner",
    predicate: str = "intersects"
) -> List[Dict[str, Any]]:
    """
    Perform a spatial join between two layers.
    - layers: expects exactly two FeatureCollections (left, right).
    - how: 'left', 'right', or 'inner'.
    - predicate: spatial predicate, e.g. 'intersects', 'contains', 'within'.
    """
    if len(layers) < 2:
        return layers
    try:
        left_gdf = gpd.GeoDataFrame.from_features(layers[0].get("features", []))
        right_gdf = gpd.GeoDataFrame.from_features(layers[1].get("features", []))
        left_gdf.set_crs("EPSG:4326", inplace=True)
        right_gdf.set_crs("EPSG:4326", inplace=True)

        joined = gpd.sjoin(left_gdf, right_gdf, how=how, predicate=predicate)
        return [json.loads(joined.to_json())]
    except Exception as e:
        logger.exception(f"Error in op_sjoin: {e}")
        return []


def op_sjoin_nearest(
    layers: List[Dict[str, Any]],
    how: str = "inner",
    max_distance: Optional[float] = None,
    distance_col: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Perform a nearest-neighbor spatial join between two layers.
    - layers: expects exactly two FeatureCollections (left, right).
    - how: 'left', 'right', or 'inner'.
    - max_distance: maximum search radius (in layer CRS units).
    - distance_col: name of the output column to store distance.
    """
    if len(layers) < 2:
        return layers
    try:
        left_gdf = gpd.GeoDataFrame.from_features(layers[0].get("features", []))
        right_gdf = gpd.GeoDataFrame.from_features(layers[1].get("features", []))
        left_gdf.set_crs("EPSG:4326", inplace=True)
        right_gdf.set_crs("EPSG:4326", inplace=True)

        joined = gpd.sjoin_nearest(
            left_gdf,
            right_gdf,
            how=how,
            max_distance=max_distance,
            distance_col=distance_col
        )
        return [json.loads(joined.to_json())]
    except Exception as e:
        logger.exception(f"Error in op_sjoin_nearest: {e}")
        return []

# Registry of available tools
TOOL_REGISTRY = {
    "buffer": op_buffer,
    "centroid": op_centroid,
    "simplify": op_simplify,
    "overlay": op_overlay,
    "merge": op_merge,
    "sjoin": op_sjoin,
    "sjoin_nearest": op_sjoin_nearest
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
         "Example for a user query 'overlay layer1 and layer2 with intersection in EPSG:3413':"
        "```json\n"
        "{{\n"
        "  \"steps\": [\n"
        "    {{\n"
        "      \"operation\": \"overlay\",\n"
        "      \"params\": {{ \"how\": intersection, \"crs\": \"EPSG:3413\" }}\n"
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
    target_layer_ids: Optional[List[str]] = None,
    operation: Optional[str] = None
) -> Union[Dict[str, Any], Command]:
    """
    Tool to geoprocess a specific geospatial layer from the state.
    
    Args:
        state: The agent state containing geodata_layers
        tool_call_id: ID for this tool call
        target_layer_id: ID of the specific layer to process. If not provided, will attempt to determine from context.
        operation: Optional operation hint (buffer, overlay, etc.)
    
    The tool will apply operations like buffer, overlay, simplify, sjoin, merge, sjoin_nearest, centroid to the specified layer.
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
    
    # Select layers by ID or default to first
    if target_layer_ids:
        selected = [layer for layer in layers if layer.id in target_layer_ids]
        missing = set(target_layer_ids) - {l.id for l in selected}
        if missing:
            available = [{"id": l.id, "title": l.title} for l in layers]
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            name="geoprocess_tool",
                            content=f"Error: Layer IDs not found: {missing}. Available layers: {json.dumps(available)}",
                            tool_call_id=tool_call_id,
                            status="error"
                        )
                    ]
                }
            )
    else:
        selected = [layers[0]]
    
    # Get URLs for the selected layers only
    layer_urls = [
        layer.data_link
        for layer in selected
        if layer.data_type in (DataType.GEOJSON, DataType.UPLOADED)
    ]
    
    # Name derived from input layer
    result_name = selected[0].name if selected else ""

    # Load GeoJSONs from either local disk or remote URL
    input_layers: List[Dict[str, Any]] = []
    for layer in selected:
        if layer.data_type not in (DataType.GEOJSON, DataType.UPLOADED):
            continue

        url = layer.data_link
        gj: Optional[Dict[str, Any]] = None

        # 1) If the URL matches BASE_URL/uploads/, load from LOCAL_UPLOAD_DIR
        if url.startswith(f"{BASE_URL}/uploads/"):
            filename = os.path.basename(url)
            local_path = os.path.join(LOCAL_UPLOAD_DIR, filename)
            try:
                with open(local_path, "r", encoding="utf-8") as f:
                    gj = json.load(f)
            except Exception as exc:
                return {
                    "update": {
                        "messages": [
                            ToolMessage(
                                name="geoprocess_tool",
                                content=f"Error: Failed to read local file '{local_path}': {exc}",
                                tool_call_id=tool_call_id,
                                status="error"
                            )
                        ]
                    }
                }

        # 2) Else if url is a local filesystem path
        elif os.path.isfile(url):
            try:
                with open(url, "r", encoding="utf-8") as f:
                    gj = json.load(f)
            except Exception as exc:
                return {
                    "update": {
                        "messages": [
                            ToolMessage(
                                name="geoprocess_tool",
                                content=f"Error: Failed to read local file '{url}': {exc}",
                                tool_call_id=tool_call_id,
                                status="error"
                            )
                        ]
                    }
                }

        # 3) Else if url is under LOCAL_UPLOAD_DIR by filename
        else:
            filename = os.path.basename(url)
            local_path = os.path.join(LOCAL_UPLOAD_DIR, filename)
            if os.path.isfile(local_path):
                try:
                    with open(local_path, "r", encoding="utf-8") as f:
                        gj = json.load(f)
                except Exception as exc:
                    return {
                        "update": {
                            "messages": [
                                ToolMessage(
                                    name="geoprocess_tool",
                                    content=f"Error: Failed to read local file '{local_path}': {exc}",
                                    tool_call_id=tool_call_id,
                                    status="error"
                                )
                            ]
                        }
                    }

        # 4) Else if it looks like a remote URL, fetch via requests
        if gj is None:
            if url.startswith("http://") or url.startswith("https://"):
                try:
                    resp = requests.get(url, timeout=20)
                    if resp.status_code != 200:
                        raise IOError(f"HTTP {resp.status_code} when fetching {url}")
                    gj = resp.json()
                except Exception as exc:
                    return {
                        "update": {
                            "messages": [
                                ToolMessage(
                                    name="geoprocess_tool",
                                    content=f"Error: Failed to fetch GeoJSON from '{url}': {exc}",
                                    tool_call_id=tool_call_id,
                                    status="error"
                                )
                            ]
                        }
                    }
            else:
                return {
                    "update": {
                        "messages": [
                            ToolMessage(
                                name="geoprocess_tool",
                                content=f"Error: GeoJSON path '{url}' is neither a local file nor a valid HTTP URL.",
                                tool_call_id=tool_call_id,
                                status="error"
                            )
                        ]
                    }
                }

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
            "operation: buffer params: radius=<number>, radius_unit=<meters|kilometers|miles>, buffer_crs=<string>",
            "operation: centroid params:",
            "operation: simplify params: tolerance=<number>, preserve_topology=<bool>",
            "operation: overlay params: how=<intersection|union|difference|symmetric_difference|identity>, crs=<string>",
            "operation: merge params: on=<list_of_strings>|null, how=<inner|left|right|outer>",
            "operation: sjoin params: how=<inner|left|right>, predicate=<string>",
            "operation: sjoin_nearest params: how=<inner|left|right>, max_distance=<number>|null, distance_col=<string>|null"
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