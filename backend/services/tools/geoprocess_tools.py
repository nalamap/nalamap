# services/agents/geoprocessing_agent.py
import json
import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Union

import requests

# LLM import
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from typing_extensions import Annotated

from core.config import BASE_URL, LOCAL_UPLOAD_DIR
from models.geodata import DataOrigin, DataType, GeoDataObject
from models.states import GeoDataAgentState
from services.ai.llm_config import get_llm
from services.tools.geoprocessing.ops.buffer import op_buffer
from services.tools.geoprocessing.ops.centroid import op_centroid
from services.tools.geoprocessing.ops.merge import op_merge
from services.tools.geoprocessing.ops.overlay import op_overlay
from services.tools.geoprocessing.ops.simplify import op_simplify
from services.tools.geoprocessing.ops.sjoin import op_sjoin
from services.tools.geoprocessing.ops.sjoin_nearest import op_sjoin_nearest

# Imports of operation functions from geoprocessing ops and utils
from services.tools.geoprocessing.utils import get_last_human_content
from services.tools.utils import match_layer_names

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Registry of available tools
TOOL_REGISTRY = {
    "buffer": op_buffer,
    "centroid": op_centroid,
    "simplify": op_simplify,
    "overlay": op_overlay,
    "merge": op_merge,
    "sjoin": op_sjoin,
    "sjoin_nearest": op_sjoin_nearest,
}


# ========== Utility Functions for Enhanced Naming ==========
def _slugify(text: str) -> str:
    """Convert text to a clean slug format (lowercase, spaces to hyphens)."""
    # Convert to lowercase and replace spaces/underscores with hyphens
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[-\s_]+", "-", slug)
    return slug.strip("-")


def _generate_layer_title(query: str, input_layer_names: List[str], operations: List[str]) -> str:
    """Generate a user-facing title for the new layer using LLM."""
    llm = get_llm()

    system_msg = (
        "You are a geographic data assistant. Generate a short, descriptive title (maximum 5 words) "
        "for a new geospatial layer based on the user's query and the operations performed. "
        "The title should be clear, concise, and describe what the resulting layer represents."
    )

    user_msg = (
        f"User query: {query}\n"
        f"Input layers: {', '.join(input_layer_names)}\n"
        f"Operations performed: {', '.join(operations)}\n"
        "Generate a descriptive title (max 5 words) for the resulting layer:"
    )

    from langchain.schema import SystemMessage

    messages = [
        SystemMessage(content=system_msg),
        HumanMessage(content=user_msg),
    ]

    try:
        response = llm.generate([messages])
        title = response.generations[0][0].text.strip()
        # Ensure title is within word limit
        words = title.split()
        if len(words) > 5:
            title = " ".join(words[:5])
        return title
    except Exception as e:
        logger.warning(f"Failed to generate LLM title: {e}")
        # Fallback to a simple descriptive title
        if operations:
            return f"{operations[0].title()} Result"
        return "Geoprocessed Layer"


def _create_unique_name(title: str, layer_uuid: str) -> str:
    """Create a unique name by combining slugified title with UUID prefix."""
    slug = _slugify(title)
    uuid_prefix = layer_uuid[:8]
    return f"{slug}-{uuid_prefix}"


def _format_operation_description(
    title: str, input_layer_names: List[str], operations_details: List[Dict[str, Any]]
) -> str:
    """Format a comprehensive description including operations and parameters."""
    description_parts = [f"Layer: {title}"]

    if input_layer_names:
        description_parts.append(f"Input layers: {', '.join(input_layer_names)}")

    if operations_details:
        description_parts.append("Operations performed:")
        for i, op_detail in enumerate(operations_details, 1):
            op_name = op_detail.get("operation", "Unknown")
            params = op_detail.get("params", {})
            if params:
                params_str = ", ".join([f"{k}={v}" for k, v in params.items()])
                description_parts.append(f"  {i}. {op_name} ({params_str})")
            else:
                description_parts.append(f"  {i}. {op_name}")

    return "\n".join(description_parts)


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
        "You are a geospatial task execution assistant. Your sole job is to translate the user's most recent request into a single geoprocessing operation and its parameters."
        "1. Examine the user's query closely: {query_json_string}."
        "2. Identify the single most appropriate geoprocessing operation from the available list: {available_operations_list_json_string}."
        "3. CRITICAL FOR BUFFER OPERATION: If the chosen operation is 'buffer', you MUST extract 'radius' (a number) and 'radius_unit' (e.g., 'meters', 'kilometers', 'miles') directly and precisely from the user's query. For example, if the user says 'buffer by 100 km', your parameters MUST be `{{\"radius\": 100, \"radius_unit\": \"kilometers\"}}`. If they say 'buffer by 50000 meters', params MUST be `{{\"radius\": 50000, \"radius_unit\": \"meters\"}}`. DO NOT use default values if the user specifies values; use exactly what the user provided."
        "4. For other operations, extract necessary parameters as defined in their descriptions from the user's query. Use default values EPSG:3857 for crs if None where given."
        '5. Return a JSON object structured EXACTLY as follows: `{{"steps": [{{"operation": "chosen_operation_name", "params": {{extracted_parameters}}}}]}}`. The \'steps\' array MUST contain exactly one operation object.'
        "The execution framework handles which layer(s) are passed to the operation; you do not control this with parameters."
        "Example for a user query 'buffer the_roads by 5 kilometers':"
        "```json\n"
        "{{\n"
        '  "steps": [\n'
        "    {{\n"
        '      "operation": "buffer",\n'
        '      "params": {{ "radius": 5, "radius_unit": "kilometers" }}\n'
        "    }}\n"
        "  ]\n"
        "}}\n"
        "```"
        "Example for a user query 'overlay layer1 and layer2 with intersection in EPSG:3413':"
        "```json\n"
        "{{\n"
        '  "steps": [\n'
        "    {{\n"
        '      "operation": "overlay",\n'
        '      "params": {{ "how": intersection, "crs": "EPSG:3413" }}\n'
        "    }}\n"
        "  ]\n"
        "}}\n"
        "```"
    ).format(
        query_json_string=json.dumps(query),
        available_operations_list_json_string=json.dumps(available_ops),
    )
    user_payload = {
        "query": query,
        "available_operations": available_ops,
        "layers": layer_meta,
    }
    user_msg = json.dumps(user_payload)

    # Use LangChain chat generate methods since AzureChatOpenAI doesn't have .chat()
    from langchain.schema import SystemMessage

    messages = [
        SystemMessage(content=system_msg),
        HumanMessage(content=user_msg),
    ]
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
                cleaned_content = "\n".join(lines[start_line + 1 :])
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
    operations_details = []
    for step in steps:
        op_name = step.get("operation")
        params = step.get("params", {})
        func = TOOL_REGISTRY.get(op_name)
        if func:
            result = func(result, **params)
            executed_ops.append(op_name)
            operations_details.append({"operation": op_name, "params": params})

    return {
        "tool_sequence": executed_ops,
        "result_layers": result,
        "operations_details": operations_details,
    }


@tool
def geoprocess_tool(
    state: Annotated[GeoDataAgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    target_layer_names: Optional[List[str]] = None,
    operation: Optional[str] = None,
) -> Union[Dict[str, Any], Command]:
    """
    Tool to geoprocess specific geospatial layers from the state.

    Args:
        state: The agent state containing geodata_layers
        tool_call_id: ID for this tool call
        target_layer_ids: IDs of the specific layers to process. Try to provide and to read out from state.
        operation: Optional operation hint (buffer, overlay, etc.)

    The tool will apply operations like buffer, overlay, simplify, sjoin, merge, sjoin_nearest, centroid to the specified layers.
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
                        status="error",
                    )
                ]
            }
        )

    # Select layers by ID or default to first
    if target_layer_names:
        selected = match_layer_names(layers, target_layer_names)
        missing = len(target_layer_names) - len(selected)
        if missing:
            all_available = [{"name": layer.name, "title": layer.title} for layer in layers]
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            name="geoprocess_tool",
                            content=f"Error: Layer Names not found: {missing}. Available layers: {json.dumps(all_available)}",
                            tool_call_id=tool_call_id,
                            status="error",
                        )
                    ]
                }
            )
    else:
        selected = layers

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
                                status="error",
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
                                status="error",
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
                                    status="error",
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
                                    status="error",
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
                                status="error",
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
            input_layers.append(
                {
                    "type": "FeatureCollection",
                    "features": [gj],
                }
            )

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
            "operation: sjoin_nearest params: how=<inner|left|right>, max_distance=<number>|null, distance_col=<string>|null",
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
                        status="error",
                    )
                ]
            }
        )

    # Collect results
    result_layers = final_state.get("result_layers", [])
    tools_used = final_state.get("tool_sequence", [])
    operations_details = final_state.get("operations_details", [])

    # Get input layer names for metadata
    input_layer_names = [layer.name for layer in selected] if selected else []

    # Build new GeoDataObjects
    new_geodata: List[GeoDataObject]
    if (
        "geodata_results" not in state
        or state["geodata_results"] is None
        or not isinstance(state["geodata_results"], List)
    ):
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

        # Enhanced naming and metadata
        layer_title = _generate_layer_title(query, input_layer_names, tools_used)
        layer_name = _create_unique_name(layer_title, out_uuid)
        layer_description = _format_operation_description(
            layer_title, input_layer_names, operations_details
        )

        new_geodata.append(
            GeoDataObject(
                id=out_uuid,
                data_source_id="geoprocess",
                data_type=DataType.GEOJSON,
                data_origin=DataOrigin.TOOL,
                data_source="NaLaMapGeoprocess",
                data_link=url,
                name=layer_name,
                title=layer_title,
                description=layer_description,
                llm_description=layer_description,
                score=0.2,
                bounding_box=None,
                layer_type="GeoJSON",
                properties=None,
            )
        )

    # Return the update command
    return Command(
        update={
            "messages": [
                ToolMessage(
                    name="geoprocess_tool",
                    content="Tools used: "
                    + ", ".join(tools_used)
                    + f". Added GeoDataObjects into the global_state, use id and data_source_id for reference: {json.dumps([{'id': result.id, 'data_source_id': result.data_source_id, 'title': result.title} for result in new_geodata])}",
                    tool_call_id=tool_call_id,
                )
            ],
            # "global_geodata": new_geodata,
            "geodata_results": new_geodata,
        }
    )
