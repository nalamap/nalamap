import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from models.geodata import GeoDataObject
from services.ai.llm_config import get_llm

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatMessage(BaseModel):
    type: str
    content: str


class AIChatRequest(BaseModel):
    query: str
    messages: List[ChatMessage] = []
    geodata_layers: List[GeoDataObject] = []
    geodata_last_results: List[GeoDataObject] = []
    options: Optional[Dict[str, Any]] = None


class AIChatResponse(BaseModel):
    response: str
    updated_layers: List[GeoDataObject] = []
    messages: List[ChatMessage] = []


def parse_color(color_name: str) -> str:
    """Convert color names to hex values"""
    color_map = {
        "red": "#ff0000",
        "blue": "#0000ff",  # Fixed: was "#0000f"
        "green": "#00ff00",
        "yellow": "#ffff00",
        "orange": "#ffa500",
        "purple": "#800080",
        "pink": "#ffc0cb",
        "brown": "#a52a2a",
        "black": "#000000",
        "white": "#ffffff",  # Fixed: was "#fffff"
        "gray": "#808080",
        "grey": "#808080",
        "cyan": "#00ffff",  # Fixed: was "#00fff"
        "magenta": "#ff00ff",  # Fixed: was "#ff00f"
        "lime": "#00ff00",
        "navy": "#000080",
        "silver": "#c0c0c0",
        "maroon": "#800000",
        "olive": "#808000",
        "teal": "#008080",
        "aqua": "#00ffff",  # Fixed: was "#00fff"
    }
    return color_map.get(color_name.lower(), color_name)


def extract_layer_names_from_text(text: str, available_layers: List[GeoDataObject]) -> List[str]:
    """Extract layer names mentioned in the user's request"""
    text_lower = text.lower()
    mentioned_layers = []

    logger.debug(f"Extracting layer names from text: '{text}'")
    logger.debug(f"Available layers: {[layer.name for layer in available_layers]}")

    # Create a mapping of possible layer identifiers to actual layer names
    layer_identifiers = {}
    for layer in available_layers:
        # Add the actual name (exact match)
        layer_identifiers[layer.name.lower()] = layer.name

        # Add the title if it exists
        if layer.title:
            layer_identifiers[layer.title.lower()] = layer.name

        # Add simple words from the name (e.g., "rivers" from "AQUAMAPS:rivers_africa")
        # Split on common separators and take meaningful words
        separators = [":", "_", "-", ".", " "]
        name_words = layer.name.lower()
        for sep in separators:
            name_words = name_words.replace(sep, " ")

        words = name_words.split()
        for word in words:
            if len(word) > 3:  # Only consider words longer than 3 characters
                layer_identifiers[word] = layer.name
                logger.debug(f"  Mapped keyword '{word}' -> '{layer.name}'")

    logger.debug(f"Layer identifiers: {layer_identifiers}")

    # Look for layer mentions in the text
    # First try exact matches, then partial matches
    for identifier, actual_name in sorted(
        layer_identifiers.items(), key=lambda x: len(x[0]), reverse=True
    ):
        if identifier in text_lower and actual_name not in mentioned_layers:
            mentioned_layers.append(actual_name)
            logger.debug(f"  Found match: '{identifier}' -> '{actual_name}'")

    logger.debug(f"Final mentioned layers: {mentioned_layers}")
    return mentioned_layers


def extract_style_from_ai_response(ai_response: str, geometry_type: str = None) -> Dict[str, Any]:
    """Extract styling parameters from AI response"""
    style = {}

    # Extract colors - improved patterns to handle "change to X" and "make it X"
    color_patterns = [
        r"(?:change|make|set).*?(?:color|it).*?(?:to|as)\s+([a-zA-Z]+)",
        # "change color to red", "make it blue"
        r"(?:to|as)\s+([a-zA-Z]+)\s*color",  # "to red color"
        r"([a-zA-Z]+)\s+(?:color|borders?|stroke|outline)",
        # "red color", "red borders", "red stroke"
        r"color[:\s]+([#\w]+)",
        r"make\s+(?:it\s+)?([a-zA-Z]+)",
        r"stroke[:\s]+([#\w]+)",
        r"fill[:\s]+([#\w]+)",
    ]

    for pattern in color_patterns:
        matches = re.findall(pattern, ai_response.lower())
        for match in matches:
            color = parse_color(match)
            if color.startswith("#"):
                # Always set stroke color for all geometry types
                style["stroke_color"] = color

                # Only set fill color for polygons and points, not for polylines
                if geometry_type != "LineString" and geometry_type != "MultiLineString":
                    style["fill_color"] = color
                # Found a valid color, no need to check more matches for this pattern
                break
        # If we found a color, we can stop checking other patterns
        if "stroke_color" in style:
            break

    # Extract opacity
    opacity_match = re.search(r"opacity[:\s]+(\d*\.?\d+)", ai_response.lower())
    if opacity_match:
        opacity = float(opacity_match.group(1))
        if opacity > 1:
            opacity = opacity / 100  # Convert percentage to decimal
        style["fill_opacity"] = opacity
        style["stroke_opacity"] = opacity

    # Extract stroke weight
    weight_patterns = [
        r"thick(?:er)?|bold",
        r"thin(?:ner)?|fine",
        r"stroke[:\s]*weight[:\s]*(\d+)",
        r"border[:\s]*(\d+)",
        r"width[:\s]*(\d+)",
    ]

    for pattern in weight_patterns:
        if pattern in ["thick(?:er)?|bold", "thin(?:ner)?|fine"]:
            if re.search(pattern, ai_response.lower()):
                style["stroke_weight"] = 4 if "thick" in pattern or "bold" in pattern else 1
                break
        else:
            match = re.search(pattern, ai_response.lower())
            if match:
                style["stroke_weight"] = int(match.group(1))
                break

    # Extract transparency/fill
    if re.search(r"transparent|no\s+fill|empty", ai_response.lower()):
        if geometry_type not in ["LineString", "MultiLineString"]:
            style["fill_opacity"] = 0.0
    elif re.search(r"solid|filled?", ai_response.lower()):
        if geometry_type not in ["LineString", "MultiLineString"]:
            style["fill_opacity"] = 0.6

    # Extract dash patterns
    if re.search(r"dash(?:ed)?|dotted", ai_response.lower()):
        if "dotted" in ai_response.lower():
            style["stroke_dash_array"] = "3,3"
        else:
            style["stroke_dash_array"] = "5,5"
    elif re.search(r"solid", ai_response.lower()):
        style["stroke_dash_array"] = None

    # Extract radius for points (only applicable to Point geometries)
    if geometry_type in ["Point", "MultiPoint", "Unknown", "Mixed"]:
        radius_match = re.search(r"radius[:\s]*(\d+)|size[:\s]*(\d+)", ai_response.lower())
        if radius_match:
            radius = radius_match.group(1) or radius_match.group(2)
            if radius:
                style["radius"] = int(radius)
        elif re.search(r"large", ai_response.lower()):
            style["radius"] = 12
        elif re.search(r"small", ai_response.lower()):
            style["radius"] = 4

    # For polylines, ensure we have some default styling if no specific styling was extracted
    if geometry_type in ["LineString", "MultiLineString"] and not style:
        # Set default stroke properties for polylines
        style["stroke_weight"] = 2
        style["stroke_opacity"] = 1.0

    return style


def detect_geometry_type(data_link: str) -> str:
    """
    Detect the geometry type from GeoJSON data by examining the first feature.
    Returns the geometry type or 'Mixed' if multiple types are found.
    """
    # Default to Polygon for uploaded files as a fallback
    default_type = "Polygon"
    
    try:
        import requests
        import json

        # Add a cache buster to avoid any potential caching issues
        cache_buster = f"?cb={hash(data_link) % 10000}"
        request_url = f"{data_link}{cache_buster}" if "?" not in data_link else f"{data_link}&cb={hash(data_link) % 10000}"
        
        logger.info(f"Fetching geometry type from: {request_url}")
        response = requests.get(request_url, timeout=10)
        
        if response.status_code == 200:
            try:
                geojson_data = response.json()
                
                if "features" in geojson_data and geojson_data["features"]:
                    # Check the first few features to determine the geometry type
                    geometry_types = set()
                    for feature in geojson_data["features"][:5]:  # Check first 5 features
                        if "geometry" in feature and "type" in feature["geometry"]:
                            geometry_types.add(feature["geometry"]["type"])
                            
                    if len(geometry_types) == 1:
                        detected_type = list(geometry_types)[0]
                        logger.info(f"Detected geometry type: {detected_type}")
                        return detected_type
                    elif len(geometry_types) > 1:
                        logger.info(f"Detected mixed geometry types: {geometry_types}")
                        return "Mixed"
            except json.JSONDecodeError as je:
                logger.error(f"JSON decode error for {data_link}: {str(je)}")
                
        logger.warning(f"Could not detect geometry type from {data_link}, defaulting to {default_type}")
        return default_type
    except Exception as e:
        logger.error(f"Error detecting geometry type from {data_link}: {str(e)}")
        return default_type


@router.post("/ai-style", response_model=AIChatResponse)
async def ai_style(request: AIChatRequest):
    """
    AI-powered layer styling endpoint
    """
    try:
        if not request.geodata_layers:
            response_messages = [
                *request.messages,
                ChatMessage(type="human", content=request.query),
                ChatMessage(
                    type="ai",
                    content="No layers available to style. Please add some layers first.",
                ),
            ]

            return AIChatResponse(
                response="No layers available to style. Please add some layers first.",
                updated_layers=[],
                messages=response_messages,
            )

        # Get AI interpretation of the styling request
        llm = get_llm()

        system_prompt = """You are a geospatial styling assistant. Your job is to interpret user \
requests for map layer styling and IMMEDIATELY APPLY the styling without hesitation.

CRITICAL INSTRUCTIONS:
1. ALWAYS apply styling immediately - never just describe what you will do
2. If user mentions specific layer name/keyword (rivers, hospitals, basins, etc.), \
style ONLY that layer RIGHT NOW
3. If user doesn't specify a layer AND multiple layers exist, ask for clarification - \
do NOT apply styling
4. If only one layer exists, style it IMMEDIATELY
5. Be conversational but ACTION-ORIENTED - do the work, don't just talk about it

Layer identification: Use name, title, or keywords (rivers, hospitals, africa, basins, etc.)
Style properties: stroke_color, fill_color (hex codes), opacity (0.0-1.0), \
stroke_weight (1-10), radius (pixels)
Color standards: rivers→blue, hospitals→red, forests→green, roads→gray, agriculture→yellow
Examples:
- "Making the rivers blue now!" (rivers→blue)
- "Making hospitals red for visibility!" (hospitals→red)
- "Which layer would you like me to style?" (multiple layers, no specification)

Current layers available:
"""

        layer_info = []
        for layer in request.geodata_layers:
            layer_info.append(f"- {layer.name} ({layer.layer_type or 'unknown type'})")

        system_prompt += "\n".join(layer_info)

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"User request: {request.query}"),
        ]

        ai_response = await llm.ainvoke(messages)
        ai_response_text = ai_response.content

        # Check if AI is asking for clarification
        # (contains question marks or clarification keywords)
        is_clarification = any(
            keyword in ai_response_text.lower()
            for keyword in [
                "which",
                "what",
                "?",
                "clarify",
                "specify",
                "multiple layers",
                "available",
            ]
        )

        if is_clarification and len(request.geodata_layers) > 1:
            # AI is asking for clarification, don't apply any styling
            response_messages = [
                *request.messages,
                ChatMessage(type="human", content=request.query),
                ChatMessage(type="ai", content=ai_response_text),
            ]

            return AIChatResponse(
                response=ai_response_text,
                updated_layers=request.geodata_layers,  # Return original layers unchanged
                messages=response_messages,
            )

        # Extract styling parameters from the AI response and user query
        combined_text = request.query + " " + ai_response_text
        logger.debug(f"Extracting style from: {combined_text}")

        # Extract mentioned layer names from the user query and AI response
        mentioned_layers = extract_layer_names_from_text(combined_text, request.geodata_layers)
        logger.debug(f"Mentioned layers: {mentioned_layers}")

        # Determine which layers to style
        layers_to_style_ids = []

        if mentioned_layers:
            # Style only the mentioned layers
            logger.debug(f"User mentioned specific layers: {mentioned_layers}")
            for layer in request.geodata_layers:
                if layer.name in mentioned_layers:
                    layers_to_style_ids.append(layer.id)
                    logger.debug(f"Will style layer: {layer.name} (ID: {layer.id})")
        elif len(request.geodata_layers) == 1:
            # If only one layer, style it
            layers_to_style_ids = [request.geodata_layers[0].id]
            logger.debug(f"Single layer, will style: {request.geodata_layers[0].name}")
        else:
            # Multiple layers but none specified - ask for clarification
            layer_names = [layer.name for layer in request.geodata_layers]
            clarification_message = (
                f"I see you have multiple layers available: {', '.join(layer_names)}. "
                f"Which layer would you like me to style?"
            )
            logger.debug("Multiple layers without specification, asking for clarification")

            response_messages = [
                *request.messages,
                ChatMessage(type="human", content=request.query),
                ChatMessage(type="ai", content=clarification_message),
            ]

            return AIChatResponse(
                response=clarification_message,
                updated_layers=request.geodata_layers,  # Return original layers unchanged
                messages=response_messages,
            )

        logger.debug(f"Final layers to style (IDs): {layers_to_style_ids}")

        # Apply styling to selected layers
        updated_layers = []
        for layer in request.geodata_layers:
            if layer.id in layers_to_style_ids:
                logger.debug(f"Applying styling to layer: {layer.name} (ID: {layer.id})")

                # Detect geometry type for this layer
                geometry_type = "Unknown"
                if (
                    layer.layer_type and layer.layer_type.upper() in ["WFS", "UPLOADED"]
                ) or layer.data_link.lower().endswith((".geojson", ".json")):
                    geometry_type = detect_geometry_type(layer.data_link)
                    logger.debug(f"Detected geometry type for layer {layer.name}: {geometry_type}")

                # Extract style parameters with geometry type awareness
                layer_style_params = extract_style_from_ai_response(combined_text, geometry_type)
                logger.debug(f"Layer-specific style params for {layer.name}: {layer_style_params}")

                # Create a copy of the layer with updated styling
                layer_dict = layer.model_dump()

                # Initialize style if it doesn't exist
                if not layer_dict.get("style"):
                    layer_dict["style"] = {}

                # Apply the extracted style parameters
                layer_dict["style"].update(layer_style_params)
                logger.debug(f"Applied style: {layer_style_params}")

                # Create new GeoDataObject with updated style
                updated_layer = GeoDataObject(**layer_dict)
                updated_layers.append(updated_layer)
            else:
                logger.debug(f"Keeping layer unchanged: {layer.name} (ID: {layer.id})")
                # Keep the layer unchanged
                updated_layers.append(layer)

        # Create response messages
        response_messages = [
            *request.messages,
            ChatMessage(type="human", content=request.query),
            ChatMessage(type="ai", content=ai_response_text),
        ]

        return AIChatResponse(
            response=ai_response_text,
            updated_layers=updated_layers,
            messages=response_messages,
        )

    except Exception:
        logger.error("Error in AI styling")
        error_message = (
            "I encountered an error while processing your styling request. "
            "Please try again or use the manual styling panel."
        )
        response_messages = [
            *request.messages,
            ChatMessage(type="human", content=request.query),
            ChatMessage(type="ai", content=error_message),
        ]

        return AIChatResponse(
            response=error_message,
            updated_layers=request.geodata_layers,  # Return original layers on error
            messages=response_messages,
        )
