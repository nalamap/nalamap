"""
AI-powered map layer styling tools for the NaLaMap agent.
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from typing_extensions import Annotated

from models.geodata import GeoDataObject
from services.ai.automatic_styling import (
    detect_layer_type,
    generate_automatic_style,
    parse_color_scheme_request,
    parse_intelligent_color,
)

logger = logging.getLogger(__name__)


def normalize_color(color: str) -> str:
    """
    Normalize color input to hex format.
    Now supports a wide range of color inputs including:
    - Basic color names (red, blue, etc.)
    - Web color names (forestgreen, dodgerblue, etc.)
    - Hex codes (#FF0000, FF0000, etc.)
    - ColorBrewer palette names (returns first color)
    """
    if not color:
        return color

    # Use the intelligent color parsing system
    parsed_color = parse_intelligent_color(color)
    if parsed_color:
        return parsed_color

    # If not recognized, return original (for backward compatibility)
    return color


@tool
def style_map_layers(
    state: Annotated[Dict[str, Any], InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    layer_names: Optional[List[str]] = None,
    fill_color: Optional[str] = None,
    stroke_color: Optional[str] = None,
    stroke_width: Optional[int] = None,
    fill_opacity: Optional[float] = None,
    stroke_opacity: Optional[float] = None,
    radius: Optional[int] = None,
    dash_pattern: Optional[str] = None,
) -> Command:
    """
    Style map layers with visual properties. Tool automatically provides current color context.

    CRITICAL: For colorblind-safe, accessibility, or distinguishable styling:
    - NEVER use one call without layer_names (this makes all layers identical!)
    - ALWAYS use separate calls: layer_names=["specific_layer"] with different colors
    - Each call must target ONE layer with a UNIQUE color combination

    COLOR SELECTION GUIDANCE - Use HEX colors (#RRGGBB format):

    WARM COLOR SCHEMES - Choose from diverse warm families:
    - Red family: #DC143C, #B22222, #8B0000, #CD5C5C
    - Orange family: #FF4500, #FF6347, #D2691E, #A0522D
    - Yellow family: #FFD700, #DAA520, #B8860B, #F4A460
    - Brown family: #A52A2A, #8B4513, #CD853F, #DEB887
    - Ensure HIGH CONTRAST between layers (avoid similar hues like #FFCC00 vs #FFB300)

    COOL COLOR SCHEMES - Choose from diverse cool families:
    - Blue family: #0000FF, #4169E1, #1E90FF, #87CEEB
    - Green family: #008000, #228B22, #32CD32, #90EE90
    - Purple family: #800080, #9370DB, #8A2BE2, #DDA0DD
    - Teal family: #008080, #20B2AA, #48D1CC, #AFEEEE

    COLORBLIND-SAFE SCHEMES - Use these proven combinations:
    - Orange: #E69F00, Sky Blue: #56B4E9, Green: #009E73
    - Yellow: #F0E442, Blue: #0072B2, Vermillion: #D55E00
    - Purple: #CC79A7, Grey: #999999

    EARTH TONE SCHEMES:
    - Browns: #8B4513, #A0522D, #CD853F, #DEB887
    - Greens: #556B2F, #6B8E23, #808000, #9ACD32
    - Tans: #D2B48C, #BC8F8F, #F5DEB3, #DDD8C7

    GENERAL PRINCIPLES:
    - Maintain 3:1 contrast ratio minimum between adjacent colors
    - Use darker stroke colors than fill colors for definition
    - Test color combinations for accessibility
    - Consider the map background when choosing colors
    - For 3+ layers, use colors from different families (red, blue, green, not red, pink, coral)

    For uniform appearance (all layers same color):
    - Use one call without layer_names
    - Example: style_map_layers(fill_color="#FF0000", stroke_color="#8B0000")

    Args:
        layer_names: Target specific layers (REQUIRED for distinguishable styling)
        fill_color: Fill color as hex (#RRGGBB) - agent should choose intelligently
        stroke_color: Border color as hex (#RRGGBB) - should be darker than fill
        stroke_width: Border width in pixels
        fill_opacity: Fill transparency (0.0 to 1.0)
        stroke_opacity: Border transparency (0.0 to 1.0)
        radius: Point marker size
        dash_pattern: Line dash pattern like "5,5"
    """

    # Get available layers from state
    available_layers = state.get("geodata_layers", [])

    if not available_layers:
        message = (
            "No layers are currently available to style. Please add some layers to the map first."
        )
        return Command(
            update={
                "messages": [
                    *state["messages"],
                    ToolMessage(
                        name="style_map_layers",
                        content=message,
                        tool_call_id=tool_call_id,
                    ),
                ]
            }
        )

    # Extract current colors for context (helps choose distinct colors)
    current_colors = []
    for layer in available_layers:
        if layer.style and layer.style.fill_color:
            fill = layer.style.fill_color
            stroke = layer.style.stroke_color or "none"
            current_colors.append(f"{layer.name}: fill={fill}, stroke={stroke}")

    color_context = (
        f"Current layer colors: {'; '.join(current_colors)}"
        if current_colors
        else "No existing colors to avoid."
    )

    # Determine which layers to style with smart detection
    layers_to_style = []

    # Log available layers for debugging
    logger.info(f"Available layers: {[layer.name for layer in available_layers]}")
    logger.info(f"Requested layer_names: {layer_names}")

    # Smart single-layer detection
    if len(available_layers) == 1 and not layer_names:
        # Only one layer available and no specific layer names provided
        # Automatically apply styling to the single layer
        layers_to_style = available_layers
        logger.info("Single layer auto-detection: styling the only available layer")
    elif layer_names:
        # Use explicitly specified layer names
        for layer_name in layer_names:
            matching_layers = [layer for layer in available_layers if layer.name == layer_name]
            if matching_layers:
                layers_to_style.extend(matching_layers)
                logger.info(
                    f"Found matching layer for '{layer_name}': "
                    f"{[layer.name for layer in matching_layers]}"
                )
            else:
                logger.warning(f"No matching layer found for '{layer_name}'")
    else:
        # Multiple layers available and no specific names provided
        # Style all available layers
        layers_to_style = available_layers
        logger.info("Multiple layers: styling all available layers")

    if not layers_to_style:
        message = f"Could not find any layers matching the specified names. Available layers: {', '.join([layer.name for layer in available_layers])}"
        return Command(
            update={
                "messages": [
                    *state["messages"],
                    ToolMessage(
                        name="style_map_layers",
                        content=message,
                        tool_call_id=tool_call_id,
                    ),
                ]
            }
        )

    # Apply styling to selected layers
    styled_layers = []
    for layer in layers_to_style:
        # Create a copy of the layer
        layer_dict = layer.model_dump()

        # Build style parameters from the provided arguments
        style_params = {}

        if fill_color is not None:
            style_params["fill_color"] = normalize_color(fill_color)
        if stroke_color is not None:
            style_params["stroke_color"] = normalize_color(stroke_color)
        if stroke_width is not None:
            style_params["stroke_weight"] = stroke_width  # Note: stroke_weight in the model
        if fill_opacity is not None:
            style_params["fill_opacity"] = fill_opacity
        if stroke_opacity is not None:
            style_params["stroke_opacity"] = stroke_opacity
        if radius is not None:
            style_params["radius"] = radius
        if dash_pattern is not None:
            style_params["stroke_dash_array"] = dash_pattern

        # Log the styling parameters being applied
        logger.info(f"Applying styling to layer '{layer.name}': {style_params}")

        # Initialize with defaults if no style exists
        if not layer_dict.get("style"):
            layer_dict["style"] = {
                "stroke_color": "#3388FF",
                "stroke_weight": 2,
                "stroke_opacity": 0.85,  # Changed from 1.0 to 0.85 (85% opacity)
                "fill_color": "#3388f",
                "fill_opacity": 0.15,  # Changed from 0.3 to 0.15 for less transparency
                "radius": 6,  # Changed from 8 to 6
                "line_cap": "round",
                "line_join": "round",
            }

        # Update with the provided parameters
        layer_dict["style"].update(style_params)

        # Log the final style after update
        logger.info(f"Final style for layer '{layer.name}': {layer_dict['style']}")

        # Create new GeoDataObject
        updated_layer = GeoDataObject(**layer_dict)
        styled_layers.append(updated_layer)

    # Update the state with styled layers
    updated_layers = []
    for layer in available_layers:
        styled_layer = next((sl for sl in styled_layers if sl.id == layer.id), None)
        if styled_layer:
            updated_layers.append(styled_layer)
        else:
            updated_layers.append(layer)

    # Return success message and update state
    styled_layer_names = [layer.name for layer in layers_to_style]
    if len(styled_layer_names) == 1:
        message = f"Successfully applied styling to layer '{styled_layer_names[0]}'. The changes should be visible on the map."
    else:
        message = f"Successfully applied styling to {len(styled_layer_names)} layers: {', '.join(styled_layer_names)}. The changes should be visible on the map."

    message += f"\n\n{color_context}\n\n"

    return Command(
        update={
            "messages": [
                *state["messages"],
                ToolMessage(name="style_map_layers", content=message, tool_call_id=tool_call_id),
            ],
            "geodata_layers": updated_layers,
        }
    )


@tool
def auto_style_new_layers(
    state: Annotated[Dict[str, Any], InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    layer_names: Optional[List[str]] = None,
) -> Command:
    """
    Automatically apply intelligent styling to newly uploaded layers with default colors.

    This tool directly applies appropriate cartographic colors based on layer names and descriptions,
    using the comprehensive automatic styling system that analyzes layer names and applies contextually
    appropriate colors and styles for different geographic feature types.

    Key examples: hospitals→red family, rivers→blue family, forests→green family, roads→gray family.

    Args:
        layer_names: Specific layer names to auto-style (if None, styles all layers needing styling)
    """
    available_layers = state.get("geodata_layers", [])

    if not available_layers:
        message = "No layers are currently available to auto-style."
        return Command(
            update={
                "messages": [
                    *state["messages"],
                    ToolMessage(
                        name="auto_style_new_layers",
                        content=message,
                        tool_call_id=tool_call_id,
                    ),
                ]
            }
        )

    # Determine which layers to auto-style
    layers_to_style = []

    if layer_names:
        # Style specific layers
        for layer_name in layer_names:
            matching_layers = [layer for layer in available_layers if layer.name == layer_name]
            layers_to_style.extend(matching_layers)
    else:
        # Style all layers that have default styling or no styling
        layers_to_style = [
            layer
            for layer in available_layers
            if not layer.style
            or (
                layer.style
                and layer.style.stroke_color in ["#3388FF", "#3388f", None]
                and layer.style.fill_color in ["#3388FF", "#3388f", None]
            )
        ]

    if not layers_to_style:
        message = "No layers found that need auto-styling. All layers appear to have custom styling already."
        return Command(
            update={
                "messages": [
                    *state["messages"],
                    ToolMessage(
                        name="auto_style_new_layers",
                        content=message,
                        tool_call_id=tool_call_id,
                    ),
                ]
            }
        )

    # Apply automatic styling using the comprehensive styling system
    styled_layers = []
    used_colors = set()

    # Extract existing colors to avoid conflicts
    for layer in available_layers:
        if layer.style and layer.style.fill_color and layer not in layers_to_style:
            used_colors.add(layer.style.fill_color.upper())

    for layer in layers_to_style:
        # Use the automatic styling system to generate appropriate styling
        layer_description = getattr(layer, "description", None) or getattr(layer, "title", None)
        auto_style = generate_automatic_style(
            layer_name=layer.name,
            layer_description=layer_description,
            geometry_type=getattr(layer, "geometry_type", None),
        )

        # Convert LayerStyle to dictionary for the layer
        layer_dict = layer.model_dump()
        layer_dict["style"] = {
            "stroke_color": auto_style.stroke_color,
            "fill_color": auto_style.fill_color,
            "stroke_weight": auto_style.stroke_weight,
            "fill_opacity": auto_style.fill_opacity,
            "stroke_opacity": auto_style.stroke_opacity,
            "radius": auto_style.radius,
            "stroke_dash_array": auto_style.stroke_dash_array,
            "line_cap": auto_style.line_cap,
            "line_join": auto_style.line_join,
        }

        # Remove None values
        layer_dict["style"] = {k: v for k, v in layer_dict["style"].items() if v is not None}

        # Track used colors
        if auto_style.fill_color:
            used_colors.add(auto_style.fill_color.upper())
        if auto_style.stroke_color:
            used_colors.add(auto_style.stroke_color.upper())

        styled_layer = GeoDataObject(**layer_dict)
        styled_layers.append(styled_layer)

    # Update the state with styled layers
    updated_layers = []
    for layer in available_layers:
        styled_layer = next((sl for sl in styled_layers if sl.id == layer.id), None)
        if styled_layer:
            updated_layers.append(styled_layer)
        else:
            updated_layers.append(layer)

    # Create success message with layer type information
    styled_layer_info = []
    for layer in styled_layers:
        layer_type = detect_layer_type(
            layer.name, getattr(layer, "description", None) or getattr(layer, "title", None)
        )
        styled_layer_info.append(f"{layer.name} ({layer_type}): {layer.style.fill_color}")

    message = (
        f"Successfully applied intelligent automatic styling to {len(styled_layers)} layer(s) using "
        f"the comprehensive automatic styling system. Each layer received contextually appropriate "
        f"colors and styles based on geographic feature type analysis. Styling applied: "
        f"{'; '.join(styled_layer_info)}"
    )

    return Command(
        update={
            "messages": [
                *state["messages"],
                ToolMessage(
                    name="auto_style_new_layers",
                    content=message,
                    tool_call_id=tool_call_id,
                ),
            ],
            "geodata_layers": updated_layers,
        }
    )


@tool
def check_and_auto_style_layers(
    state: Annotated[Dict[str, Any], InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """
    Check for newly uploaded layers that have default styling (blue #3388ff colors) and need initial styling.

    IMPORTANT: This tool ONLY works for layers with default styling. Do NOT use this tool when:
    - Users want to change existing styled layers (use style_map_layers instead)
    - Users request colorblind-safe styling (use style_map_layers instead)
    - Users want to restyle any layers that already have custom colors (use style_map_layers instead)

    Only use this tool proactively when detecting newly uploaded layers that need initial styling.
    """
    available_layers = state.get("geodata_layers", [])

    if not available_layers:
        return Command(
            update={
                "messages": [
                    *state["messages"],
                    ToolMessage(
                        name="check_and_auto_style_layers",
                        content="No layers available for auto-styling.",
                        tool_call_id=tool_call_id,
                    ),
                ]
            }
        )

    # Find layers that need styling (have default colors)
    layers_needing_style = [
        layer
        for layer in available_layers
        if not layer.style
        or (
            layer.style
            and layer.style.stroke_color in ["#3388FF", "#3388f", None]
            and layer.style.fill_color in ["#3388FF", "#3388f", None]
        )
    ]

    if not layers_needing_style:
        return Command(
            update={
                "messages": [
                    *state["messages"],
                    ToolMessage(
                        name="check_and_auto_style_layers",
                        content="All layers already have custom styling.",
                        tool_call_id=tool_call_id,
                    ),
                ]
            }
        )

    # Trigger auto-styling workflow
    layer_names = [layer.name for layer in layers_needing_style]
    message = (
        f"Detected {len(layers_needing_style)} newly uploaded layer(s) that need styling: {', '.join(layer_names)}. "
        "Automatically applying intelligent cartographic styling based on layer names..."
    )

    return Command(
        update={
            "messages": [
                *state["messages"],
                ToolMessage(
                    name="check_and_auto_style_layers",
                    content=message,
                    tool_call_id=tool_call_id,
                ),
            ]
        }
    )


@tool
def apply_intelligent_color_scheme(
    state: Annotated[Dict[str, Any], InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    scheme_request: str,
    layer_names: Optional[List[str]] = None,
) -> Command:
    """
    Apply intelligent color schemes to layers based on natural language requests.

    Supports:
    - "colorblind safe" or "accessible" - applies colorblind-safe palette
    - "Set1", "Set2", "Spectral" - applies ColorBrewer schemes
    - "warm colors" - applies warm color palette
    - "cool colors" - applies cool color palette

    Each layer gets a unique color from the scheme to ensure distinguishability.

    Args:
        scheme_request: Natural language color scheme request
        layer_names: Specific layers to style (if None, styles all layers)
    """
    available_layers = state.get("geodata_layers", [])

    if not available_layers:
        message = "No layers are currently available to apply color schemes to."
        return Command(
            update={
                "messages": [
                    *state["messages"],
                    ToolMessage(
                        name="apply_intelligent_color_scheme",
                        content=message,
                        tool_call_id=tool_call_id,
                    ),
                ]
            }
        )

    # Parse the color scheme request
    scheme_info = parse_color_scheme_request(scheme_request)

    if not scheme_info["colors"]:
        message = f"Could not understand color scheme request: '{scheme_request}'"
        return Command(
            update={
                "messages": [
                    *state["messages"],
                    ToolMessage(
                        name="apply_intelligent_color_scheme",
                        content=message,
                        tool_call_id=tool_call_id,
                    ),
                ]
            }
        )

    # Determine which layers to style
    if layer_names:
        layers_to_style = [layer for layer in available_layers if layer.name in layer_names]
    else:
        layers_to_style = available_layers

    if not layers_to_style:
        message = "No matching layers found to style."
        return Command(
            update={
                "messages": [
                    *state["messages"],
                    ToolMessage(
                        name="apply_intelligent_color_scheme",
                        content=message,
                        tool_call_id=tool_call_id,
                    ),
                ]
            }
        )

    # Apply colors from the scheme to layers
    updated_layers = []
    scheme_colors = scheme_info["colors"]
    styled_layers = []

    for i, layer in enumerate(available_layers):
        if layer in layers_to_style:
            # Get color from scheme (cycle through if more layers than colors)
            color_index = i % len(scheme_colors)
            fill_color = scheme_colors[color_index]
            stroke_color = normalize_color(fill_color).replace("ff", "cc")  # Darker stroke

            # Apply the styling
            layer_dict = layer.model_dump()
            if not layer_dict.get("style"):
                layer_dict["style"] = {}

            layer_dict["style"].update(
                {
                    "fill_color": fill_color,
                    "stroke_color": stroke_color,
                    "fill_opacity": 0.6,
                    "stroke_opacity": 1.0,
                    "stroke_weight": 2,
                }
            )

            styled_layer = GeoDataObject(**layer_dict)
            updated_layers.append(styled_layer)
            styled_layers.append(layer.name)
        else:
            updated_layers.append(layer)

    # Create success message
    message = (
        f"Successfully applied '{scheme_info['name']}' color scheme to "
        f"{len(styled_layers)} layer(s): {', '.join(styled_layers)}. "
        f"Description: {scheme_info['description']}"
    )

    return Command(
        update={
            "messages": [
                *state["messages"],
                ToolMessage(
                    name="apply_intelligent_color_scheme",
                    content=message,
                    tool_call_id=tool_call_id,
                ),
            ],
            "geodata_layers": updated_layers,
        }
    )


def _detect_layers_needing_styling(available_layers):
    """Helper function to detect layers that need styling (used for testing)."""
    return [
        layer
        for layer in available_layers
        if not layer.style
        or (
            layer.style
            and layer.style.stroke_color in ["#3388FF", "#3388f", None]
            and layer.style.fill_color in ["#3388FF", "#3388ff", None]
        )
    ]
