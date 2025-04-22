# services/agents/geoprocessing_agent.py

from typing import Dict, List, Any
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
import json

# LLM import
from services.ai.llm_config import get_llm

# ========== Tool Implementations ==========

def op_buffer(layers: List[Dict[str, Any]], radius: float = 1.0) -> List[Dict[str, Any]]:
    out = []
    for feat in layers:
        geom = shape(feat["geometry"])
        buf = geom.buffer(radius)
        out.append({
            "type": "Feature",
            "geometry": mapping(buf),
            "properties": feat.get("properties", {})
        })
    return out


def op_intersection(layers: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
    geoms = [shape(feat["geometry"]) for feat in layers]
    inter = geoms[0]
    for g in geoms[1:]:
        inter = inter.intersection(g)
    return [{"type": "Feature", "geometry": mapping(inter), "properties": {}}]


def op_union(layers: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
    geoms = [shape(feat["geometry"]) for feat in layers]
    uni = unary_union(geoms)
    return [{"type": "Feature", "geometry": mapping(uni), "properties": {}}]


def op_difference(layers: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
    base = shape(layers[0]["geometry"])
    sub = shape(layers[1]["geometry"]) if len(layers) > 1 else None
    diff = base.difference(sub) if sub else base
    return [{"type": "Feature", "geometry": mapping(diff), "properties": {}}]


def op_clip(layers: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
    return op_intersection(layers)


def op_simplify(layers: List[Dict[str, Any]], tolerance: float = 0.01) -> List[Dict[str, Any]]:
    out = []
    for feat in layers:
        geom = shape(feat["geometry"])
        simp = geom.simplify(tolerance)
        out.append({"type": "Feature", "geometry": mapping(simp), "properties": feat.get("properties", {})})
    return out

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

async def geoprocess_executor(state: Dict[str, Any]) -> Dict[str, Any]:
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
        "Return a JSON with 'steps' array, each having 'operation with params' (one of: "
        + ", ".join(available_ops) + "). Dont define at any operation params with layer or layers as all functions are called as func(layers: result, **params)"
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
    response = await llm.agenerate([messages])  
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