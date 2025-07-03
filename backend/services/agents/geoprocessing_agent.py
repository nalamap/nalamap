# services/agents/geoprocessing_agent.py
import json
from typing import Any, Dict, List

import geopandas as gpd
from shapely.ops import unary_union

# LLM import
from services.ai.llm_config import get_llm

# ========== Tool Implementations ==========


def _flatten_features(layers):
    """
    Given a list of Feature or FeatureCollection dicts, return a flat list
    of Feature dicts.
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
    Given a list of Feature or FeatureCollection dicts, return a list of
    shapely geometries, each being the unary_union of one layer's features.
    """
    geoms = []
    for layer in layers:
        feats = (
            layer.get("features")
            if layer.get("type") == "FeatureCollection"
            else ([layer] if layer.get("type") == "Feature" else [])
        )
        if not feats:
            continue
        gdf = gpd.GeoDataFrame.from_features(feats)
        geoms.append(gdf.unary_union)
    return geoms


def op_buffer(layers, radius=10000, buffer_crs="EPSG:3857"):
    """
    Buffers each feature by a given radius in meters.
    Input geometries are assumed in EPSG:4326. This function:
      1) Loads features, sets CRS to EPSG:4326
      2) Reprojects to buffer_crs (default EPSG:3857, meters)
      3) Applies buffer with `radius` in meters
      4) Reprojects result back to EPSG:4326
    If `buffer_crs` is provided by user, uses that CRS instead of EPSG:3857.
    """
    feats = _flatten_features(layers)
    if not feats:
        return []
    # Load into GeoDataFrame and set source CRS
    gdf = gpd.GeoDataFrame.from_features(feats)
    gdf.set_crs("EPSG:4326", inplace=True)
    # Reproject to chosen metric CRS for buffering
    gdf = gdf.to_crs(buffer_crs)
    # Buffer in meter units
    gdf["geometry"] = gdf.geometry.buffer(radius)
    # Reproject back to geographic coords
    gdf = gdf.to_crs("EPSG:4326")
    # Export to GeoJSON Feature list
    fc = json.loads(gdf.to_json())
    return fc["features"]


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
    subj_feats = (
        layers[0].get("features", [])
        if layers[0].get("type") == "FeatureCollection"
        else [layers[0]]
    )
    mask_feats = (
        layers[1].get("features", [])
        if layers[1].get("type") == "FeatureCollection"
        else [layers[1]]
    )
    subj_gdf = gpd.GeoDataFrame.from_features(subj_feats)
    mask_geom = unary_union(gpd.GeoDataFrame.from_features(mask_feats).geometry)
    subj_gdf["geometry"] = subj_gdf.geometry.intersection(mask_geom)
    fc = json.loads(subj_gdf.to_json())
    return [fc]


def op_simplify(layers, tolerance=0.01):
    """Simplifies each feature geometry with the given tolerance."""
    feats = _flatten_features(layers)
    if not feats:
        return []
    gdf = gpd.GeoDataFrame.from_features(feats)
    gdf["geometry"] = gdf.geometry.simplify(tolerance)
    fc = json.loads(gdf.to_json())
    return [fc]


# Registry of available tools
TOOL_REGISTRY = {
    "buffer": op_buffer,
    "intersection": op_intersection,
    "union": op_union,
    "difference": op_difference,
    "clip": op_clip,
    "simplify": op_simplify,
}

# ========== Geoprocess Executor ==========


async def geoprocess_executor(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Uses an LLM to plan a sequence of geoprocessing operations based on a
    natural-language query and executes them in order against the input
    GeoJSON layers.

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
        layer_meta.append(
            {
                "resource_id": props.get("resource_id"),
                "name": props.get("name"),
                "geometry_type": gtype,
                "bbox": bbox,
            }
        )

        # 1) Invoke LLM planner with metadata only
    llm = get_llm()
    system_msg = (
        "You are a geospatial processing assistant. "
        "You have the following input layers with metadata "
        "(id, name, geometry_type, bbox). "
        "Based on the user request and available operations, choose the best "
        "sequence of operations. "
        "Return a JSON with 'steps' array, each having 'operation with params' "
        "(one of: "
        + ", ".join(available_ops)
        + "). Dont define at any operation params with layer or layers "
        "as all functions are called as func(layers: result, **params)"
    )
    user_payload = {
        "query": query,
        "available_operations": available_ops,
        "layers": layer_meta,
    }
    user_msg = json.dumps(user_payload)

    # Use LangChain chat generate methods since AzureChatOpenAI doesn't
    # have .chat()
    from langchain.schema import HumanMessage, SystemMessage

    messages = [SystemMessage(content=system_msg), HumanMessage(content=user_msg)]
    # agenerate expects a list of message lists for batching
    response = await llm.agenerate([messages])
    # extract text from first generation
    content = response.generations[0][0].text

    try:
        plan = json.loads(content)
    except json.JSONDecodeError:
        raise ValueError("Failed to parse LLM response as JSON: {content}")

    steps = plan.get("steps", [])

    # 2) Execute each step on full geojson layers
    result = layers
    executed_ops = []
    for step in steps:
        op_name = step.get("operation")
        params = step.get("params", {})
        func = TOOL_REGISTRY.get(op_name)
        if func:
            result = func(result, **params)
            executed_ops.append(op_name)

    return {"tool_sequence": executed_ops, "result_layers": result}
