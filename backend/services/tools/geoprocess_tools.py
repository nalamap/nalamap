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
from services.storage.file_management import store_file
from services.tools.geoprocessing.ops.area import op_area
from services.tools.geoprocessing.ops.buffer import op_buffer
from services.tools.geoprocessing.ops.centroid import op_centroid
from services.tools.geoprocessing.ops.clip import op_clip
from services.tools.geoprocessing.ops.dissolve import op_dissolve
from services.tools.geoprocessing.ops.merge import op_merge
from services.tools.geoprocessing.ops.overlay import op_overlay
from services.tools.geoprocessing.ops.simplify import op_simplify
from services.tools.geoprocessing.ops.sjoin import op_sjoin
from services.tools.geoprocessing.ops.sjoin_nearest import op_sjoin_nearest

# Imports of operation functions from geoprocessing ops and utils
from services.tools.geoprocessing.utils import get_last_human_content
from services.tools.utils import match_layer_names


def slugify(text: str) -> str:
    """
    Convert a title to a URL and filename friendly slug.

    Args:
        text: The text to convert to a slug (handles None and special characters)

    Returns:
        A slug version of the text (lowercase, spaces to hyphens, alphanumeric and underscores only)
    """
    # Handle None and empty strings
    if not text or not isinstance(text, str):
        return "geoprocessing-result"

    # Strip whitespace and limit length
    text = text.strip()[:100]  # Limit to 100 chars to avoid overly long filenames

    if not text:
        return "geoprocessing-result"

    # Convert to lowercase
    text = text.lower()
    # Replace spaces with hyphens
    text = text.replace(" ", "-")
    # Remove non-alphanumeric characters (except hyphens and underscores)
    text = re.sub(r"[^a-z0-9\-_]", "", text)
    # Remove multiple consecutive hyphens
    text = re.sub(r"-+", "-", text)
    # Remove leading and trailing hyphens
    text = text.strip("-")

    # Return a default if the slug is empty
    return text or "geoprocessing-result"


def ensure_unique_name(name: str, existing_names: List[str], uuid_prefix: str = "") -> str:
    """
    Ensure a name is unique by appending a suffix if needed.

    Args:
        name: The base name to make unique
        existing_names: List of existing names to check against
        uuid_prefix: Optional UUID prefix to guarantee uniqueness

    Returns:
        A unique name, either the original if it's unique, or with a suffix or UUID
    """
    # If the name is already unique, return it
    if name not in existing_names:
        return name

    # Try adding a numeric suffix
    counter = 2
    while f"{name}-{counter}" in existing_names:
        counter += 1

    # If UUID prefix is provided, use it for extra uniqueness
    if uuid_prefix:
        return f"{name}-{uuid_prefix}"
    else:
        return f"{name}-{counter}"


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Registry of available tools
TOOL_REGISTRY = {
    "area": op_area,
    "buffer": op_buffer,
    "centroid": op_centroid,
    "clip": op_clip,
    "dissolve": op_dissolve,
    "merge": op_merge,
    "overlay": op_overlay,
    "simplify": op_simplify,
    "sjoin": op_sjoin,
    "sjoin_nearest": op_sjoin_nearest,
}


# ========== Geoprocess Executor ==========
def geoprocess_executor(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Uses an LLM to plan a sequence of geoprocessing operations based on a natural-language query
    and executes them in order against the input GeoJSON layers.

    Returns:
      - tool_sequence: List of operation names executed
      - result_layers: List of GeoJSON Feature dicts
      - result_name: Descriptive name for the result layer
      - result_description: Detailed description of the operation
      - operation_details: JSON object with details of operations performed
    """
    query = state.get("query", "")
    layers: List[Dict[str, Any]] = state.get("input_layers", [])
    available_ops: List[str] = state.get("available_operations_and_params", [])
    model_settings = state.get("model_settings")  # Get user's model configuration

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
                "title": props.get("title", props.get("name")),
                "geometry_type": gtype,
                "bbox": bbox,
            }
        )

    # 1) Invoke LLM planner with metadata only
    # Use user-configured model if available, otherwise fall back to environment default
    if model_settings is not None:
        from services.ai.llm_config import get_llm_for_provider

        llm, _ = get_llm_for_provider(
            provider_name=model_settings.model_provider,
            max_tokens=model_settings.max_tokens,
            model_name=model_settings.model_name,
        )
    else:
        # Fall back to environment-configured provider
        llm = get_llm()

    system_msg = (
        "You are a geospatial task execution assistant. Your role is to "
        "translate the user's most recent request into a single geoprocessing "
        "operation with parameters, and provide helpful metadata about the result. "
        "1. Examine the user's query closely: {query_json_string}. "
        "2. Identify the single most appropriate geoprocessing operation from "
        "the available list: {available_operations_list_json_string}. "
        "3. CRITICAL FOR BUFFER OPERATION: If the chosen operation is 'buffer', "
        "you MUST extract 'radius' (a number) and 'radius_unit' (e.g., 'meters', "
        "'kilometers', 'miles') directly and precisely from the user's query. "
        "For example, if the user says 'buffer by 100 km', your parameters MUST "
        'be `{{"radius": 100, "radius_unit": "kilometers"}}`. If they say '
        "'buffer by 50000 meters', params MUST be `{{\"radius\": 50000, "
        '"radius_unit": "meters"}}`. DO NOT use default values if the user '
        "specifies values; use exactly what the user provided. "
        "4. For other operations, extract necessary parameters as defined in "
        "their descriptions from the user's query. Use default values EPSG:3857 "
        "for crs if None where given. "
        "5. Create a short, descriptive title (maximum 5 words) for the result "
        "layer based on the operation and the input layers. "
        "6. Write a brief description (1-2 sentences) explaining what the "
        "operation does to the input layers. "
        "7. Return a JSON object structured EXACTLY as follows: "
        '`{{"steps": [{{"operation": "chosen_operation_name", '
        '"params": {{extracted_parameters}}}}], "result_name": '
        '"Short Descriptive Title", "result_description": '
        '"Brief description of what this operation does."}}`. '
        "The 'steps' array MUST contain exactly one operation object. "
        "The execution framework handles which layer(s) are passed to the "
        "operation; you do not control this with parameters. "
        "Example for a user query 'buffer the_roads by 5 kilometers':"
        "```json\n"
        "{{\n"
        '  "steps": [\n'
        "    {{\n"
        '      "operation": "buffer",\n'
        '      "params": {{ "radius": 5, "radius_unit": "kilometers" }}\n'
        "    }}\n"
        "  ],\n"
        '  "result_name": "Roads 5km Buffer",\n'
        '  "result_description": "Creates a 5 kilometer buffer zone around all road features."\n'
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
        "  ],\n"
        '  "result_name": "Layer1 Layer2 Intersection",\n'
        '  "result_description": "Shows areas where Layer1 and Layer2 overlap '
        'using EPSG:3413 coordinate system."\n'
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
    from langchain_core.messages import SystemMessage

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
    result_name = plan.get("result_name", "")
    result_description = plan.get("result_description", "")

    # 2) Execute each step on full geojson layers on full geojson layers
    result = layers
    executed_ops = []
    executed_steps = []

    # Get enable_smart_crs setting from state (defaults to True for better accuracy)
    enable_smart_crs = state.get("enable_smart_crs", True)

    for step in steps:
        op_name = step.get("operation")
        params = step.get("params", {})
        func = TOOL_REGISTRY.get(op_name)
        if func:
            # Check if user specified a CRS parameter
            user_specified_crs = params.get("crs") or params.get("buffer_crs")

            # Inject auto_optimize_crs for operations that support it
            # Only inject if CRS not already specified by user
            if (
                not user_specified_crs
                and "auto_optimize_crs" not in params
                and op_name
                in [
                    "buffer",
                    "area",
                    "overlay",
                    "clip",
                    "dissolve",
                    "sjoin_nearest",
                    "sjoin",
                    "simplify",
                ]
            ):
                params["auto_optimize_crs"] = enable_smart_crs
                # Also request projection metadata when auto-optimizing
                params["projection_metadata"] = True
            elif user_specified_crs:
                # User specified CRS - pass it as override_crs for operations that support it
                if op_name in ["buffer", "area", "overlay", "clip", "dissolve"]:
                    # Remove the generic 'crs' parameter if present
                    if "crs" in params:
                        del params["crs"]
                    # Set override_crs to disable auto-selection
                    params["override_crs"] = user_specified_crs
                    # Still request metadata to show what was used
                    params["projection_metadata"] = True
                    # Disable auto-optimization when user specifies CRS
                    params["auto_optimize_crs"] = False

            result = func(result, **params)
            executed_ops.append(op_name)
            executed_steps.append({"operation": op_name, "params": params})

    # Create a detailed record of the operation
    operation_details = {
        "query": query,
        "steps": executed_steps,
        "input_layers": state.get("layer_titles", []),  # Use actual layer titles
    }

    return {
        "tool_sequence": executed_ops,
        "result_layers": result,
        "result_name": result_name,
        "result_description": result_description,
        "operation_details": operation_details,
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

    # Name derived from input layer
    result_name = selected[0].name if selected else ""

    # Load GeoJSONs from either local disk or remote URL
    input_layers: List[Dict[str, Any]] = []
    layer_titles: List[str] = []  # Track layer titles for origin_layers metadata
    for layer in selected:
        if layer.data_type not in (DataType.GEOJSON, DataType.UPLOADED):
            continue

        # Store layer title for metadata
        layer_titles.append(layer.title or layer.name)

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

    # Get enable_smart_crs from model settings (default to True for better accuracy)
    options = state.get("options")
    enable_smart_crs = True  # Default to enabled
    model_settings = None  # Will be passed to executor

    if options and hasattr(options, "model_settings"):
        enable_smart_crs = getattr(options.model_settings, "enable_smart_crs", True)
        model_settings = options.model_settings  # Pass model settings to executor

    # Build the state for the geoprocess executor
    processing_state = {
        "query": query,
        "input_layers": input_layers,
        "layer_titles": layer_titles,  # Pass layer titles for origin_layers metadata
        "enable_smart_crs": enable_smart_crs,
        "model_settings": model_settings,  # Pass user's model configuration
        "available_operations_and_params": [
            (
                "CRS PARAMETER: Most operations support an optional 'crs' parameter "
                "(e.g., EPSG:4326, EPSG:3857, EPSG:32633) to override automatic CRS "
                "selection. If not specified, the system will auto-select an optimal "
                "CRS. Example: 'crs=EPSG:32633' to force UTM zone 33N projection."
            ),
            (
                "operation: area params: unit=<square_meters|square_kilometers|"
                "hectares|square_miles|acres>, crs=<EPSG_code_optional>, "
                "area_column=<string>"
            ),
            (
                "operation: buffer params: radius=<number>, "
                "radius_unit=<meters|kilometers|miles>, crs=<EPSG_code_optional>, "
                "dissolve=<bool>"
            ),
            "operation: centroid params:",
            "operation: clip params: crs=<EPSG_code_optional>",
            (
                "operation: dissolve params: by=<string>|null, "
                "aggfunc=<first|last|sum|mean|min|max>, crs=<EPSG_code_optional>"
            ),
            ("operation: merge params: on=<list_of_strings>|null, " "how=<inner|left|right|outer>"),
            (
                "operation: overlay params: "
                "how=<intersection|union|difference|symmetric_difference|identity>, "
                "crs=<EPSG_code_optional>"
            ),
            ("operation: simplify params: tolerance=<number>, " "preserve_topology=<bool>"),
            ("operation: sjoin params: how=<inner|left|right>, " "predicate=<string>"),
            (
                "operation: sjoin_nearest params: how=<inner|left|right>, "
                "max_distance=<number>|null, distance_col=<string>|null"
            ),
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
    operation_details = final_state.get("operation_details", {})

    # Get LLM-generated title and description if available
    llm_title = final_state.get("result_name", "")
    llm_description = final_state.get("result_description", "")

    # Create a descriptive name (fallback if LLM doesn't provide one)
    if not llm_title and tools_used:
        tools_name = "".join(tool for tool in tools_used)
        default_name = result_name + tools_name
    else:
        default_name = result_name or "GeoprocessedLayer"

    # Use LLM-generated title or fallback to default
    display_title = llm_title if llm_title else default_name

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

    # Get existing names to ensure uniqueness
    existing_layer_names = []
    if "geodata_layers" in state and state["geodata_layers"]:
        existing_layer_names.extend([layer.name for layer in state["geodata_layers"]])
    if "geodata_results" in state and state["geodata_results"]:
        existing_layer_names.extend([layer.name for layer in state["geodata_results"]])

    out_urls: List[str] = []
    for layer in result_layers:
        # Generate a unique ID
        out_uuid = uuid.uuid4().hex
        short_uuid = out_uuid[:8]  # First 8 chars of UUID for uniqueness

        # Create a slugified name from the title and ensure uniqueness
        slug_name = slugify(display_title)
        unique_name = ensure_unique_name(slug_name, existing_layer_names, short_uuid)
        existing_layer_names.append(unique_name)  # Add to list to avoid duplicates

        # Extract CRS metadata if present in the layer
        processing_metadata = None
        if isinstance(layer, dict) and "properties" in layer:
            layer_props = layer.get("properties", {})
            if "_crs_metadata" in layer_props:
                crs_meta = layer_props["_crs_metadata"]
                # Get the operation name from the last executed step
                last_operation = (
                    operation_details.get("steps", [{}])[-1].get("operation", "unknown")
                    if operation_details.get("steps")
                    else "unknown"
                )

                # Import ProcessingMetadata here to avoid circular imports
                from models.geodata import ProcessingMetadata

                # Filter out None values from origin_layers
                origin_layer_names = [
                    name
                    for name in operation_details.get("input_layers", [])
                    if name is not None and name != ""
                ]

                processing_metadata = ProcessingMetadata(
                    operation=last_operation,
                    crs_used=crs_meta.get("epsg_code", "EPSG:4326"),
                    crs_name=crs_meta.get("crs_name", "Unknown"),
                    projection_property=crs_meta.get("projection_property", "unknown"),
                    auto_selected=crs_meta.get("auto_selected", False),
                    selection_reason=crs_meta.get("selection_reason"),
                    expected_error=crs_meta.get("expected_error"),
                    origin_layers=origin_layer_names,
                )
                # Remove the internal metadata from properties before storing
                del layer_props["_crs_metadata"]

        # Create a filename with the unique name and serialize to JSON
        filename = f"{unique_name}_{short_uuid}.geojson"
        json_content = json.dumps(layer).encode("utf-8")

        # Use centralized file management (supports both local and Azure Blob Storage)
        url, stored_filename = store_file(filename, json_content)
        out_urls.append(url)

        # Format the operation details for the description
        # Safely format operation steps, handling potential None values
        operation_steps_list = []
        for step in operation_details.get("steps", []):
            if step is not None and isinstance(step, dict):
                op = step.get("operation", "unknown")
                params = step.get("params", {})
                if params is not None:
                    operation_steps_list.append(f"- {op}: {json.dumps(params)}")
                else:
                    operation_steps_list.append(f"- {op}: {{}}")
        operation_steps = "\n".join(operation_steps_list)

        # Filter out None values to prevent TypeError
        input_layer_names = [
            layer_name
            for layer_name in operation_details.get("input_layers", [])
            if layer_name is not None
        ]
        input_layers_str = ", ".join(input_layer_names)

        # Create the full description with operation details
        full_description = f"{llm_description}\n\nOperation Details:\n"
        full_description += f"Query: {operation_details.get('query', '')}\n"
        full_description += f"Input Layers: {input_layers_str}\n"
        full_description += f"Operations:\n{operation_steps}"

        new_geodata.append(
            GeoDataObject(
                id=out_uuid,
                data_source_id="geoprocess",
                data_type=DataType.GEOJSON,
                data_origin=DataOrigin.TOOL,
                data_source="NaLaMapGeoprocess",
                data_link=url,
                name=unique_name,
                title=display_title,
                description=full_description,
                llm_description=llm_description if llm_description else display_title,
                score=0.2,
                bounding_box=None,
                layer_type="GeoJSON",
                properties=None,
                processing_metadata=processing_metadata,
            )
        )

    # Create reference data for tool message
    ref_data = [
        {"id": r.id, "data_source_id": r.data_source_id, "title": r.title} for r in new_geodata
    ]

    # Build CRS information message for the agent
    crs_info_messages = []
    for r in new_geodata:
        if r.processing_metadata:
            pm = r.processing_metadata
            crs_msg = (
                f"{r.title}: Used {pm.crs_used} ({pm.crs_name}) "
                f"{'🎯 AUTO-SELECTED' if pm.auto_selected else 'USER-SPECIFIED'}"
            )
            if pm.auto_selected and pm.selection_reason:
                crs_msg += f" - {pm.selection_reason}"
            if pm.expected_error is not None:
                crs_msg += f" (Expected error: <{pm.expected_error}%)"
            crs_info_messages.append(crs_msg)

    # Construct the tool message content
    tool_content = (
        f"Successfully processed {len(new_geodata)} layer(s). "
        f"Operations: {', '.join(tools_used)}. "
    )

    if crs_info_messages:
        crs_details = "\n".join(f"- {msg}" for msg in crs_info_messages)
        tool_content += f"\n\nCRS Information:\n{crs_details}"

    tool_content += f"\n\nReference data (use id and data_source_id): " f"{json.dumps(ref_data)}"

    # Return the update command
    return Command(
        update={
            "messages": [
                ToolMessage(
                    name="geoprocess_tool",
                    content=tool_content,
                    tool_call_id=tool_call_id,
                )
            ],
            # "global_geodata": new_geodata,
            "geodata_results": new_geodata,
        }
    )
