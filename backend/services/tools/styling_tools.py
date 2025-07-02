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
from pydantic import BaseModel, Field
from typing_extensions import Annotated

from models.geodata import GeoDataObject
from models.states import GeoDataAgentState

logger = logging.getLogger(__name__)


# Color name to hex mapping for consistent color handling
COLOR_NAME_MAP = {
    # Warm colors
    "coral": "#FF7F50",
    "peach": "#FFCBA4",
    "goldenrod": "#DAA520",
    "gold": "#FFD700",
    "salmon": "#FA8072",
    "orange": "#FFA500",
    "darkorange": "#FF8C00",
    "brown": "#A52A2A",
    "darkred": "#8B0000",
    "tomato": "#FF6347",
    "orangered": "#FF4500",
    # Cool colors
    "lightblue": "#ADD8E6",
    "darkblue": "#00008B",
    "lightgreen": "#90EE90",
    "darkgreen": "#006400",
    "lightgray": "#D3D3D3",
    "darkgray": "#A9A9A9",
    "gray": "#808080",
    "grey": "#808080",
    # Basic colors
    "red": "#FF0000",
    "green": "#008000",
    "blue": "#0000FF",
    "yellow": "#FFFF00",
    "purple": "#800080",
    "pink": "#FFC0CB",
    "white": "#FFFFFF",
    "black": "#000000",
}


def normalize_color(color: str) -> str:
    """
    Normalize color names to hex values for consistent handling.
    Returns hex value if color is a known name, otherwise returns the input.
    """
    if color and color.lower() in COLOR_NAME_MAP:
        hex_color = COLOR_NAME_MAP[color.lower()]
        logger.info("Converted color name '{color}' to hex '{hex_color}'")
        return hex_color
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
    Style map layers with specific visual properties. The agent should interpret user requests and provide explicit styling parameters.

    Smart Layer Detection:
    - When there's only ONE layer available, the tool will automatically apply styling to it (no need to specify layer_names)
    - When there are MULTIPLE layers, specify layer_names to target specific layers
    - If layer_names is None with multiple layers, all layers will be styled

    Examples:
    - Single layer: fill_color="red", stroke_color="yellow" (automatically applies to the only layer)
    - Multiple layers: layer_names=["Roads", "Buildings"], stroke_color="blue", stroke_width=5
    - For "transparent fill": fill_opacity=0.0
    - For "dashed lines": dash_pattern="5,5"

    Args:
        layer_names: List of layer names to style (optional - auto-detects single layer)
        fill_color: Fill color (CSS color name, hex, or rgb)
        stroke_color: Stroke/border color (CSS color name, hex, or rgb)
        stroke_width: Width of stroke/border in pixels
        fill_opacity: Fill opacity (0.0 to 1.0)
        stroke_opacity: Stroke opacity (0.0 to 1.0)
        radius: Radius for point markers
        dash_pattern: Dash pattern like "5,5" for dashed lines
    """

    # Get available layers from state
    available_layers = state.get("geodata_layers", [])

    if not available_layers:
        message = "No layers are currently available to style. Please add some layers to the map first."
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

    # Determine which layers to style with smart detection
    layers_to_style = []

    # Log available layers for debugging
    logger.info("Available layers: {[layer.name for layer in available_layers]}")
    logger.info("Requested layer_names: {layer_names}")

    # Smart single-layer detection
    if len(available_layers) == 1 and not layer_names:
        # Only one layer available and no specific layer names provided
        # Automatically apply styling to the single layer
        layers_to_style = available_layers
        logger.info("Single layer auto-detection: styling the only available layer")
    elif layer_names:
        # Use explicitly specified layer names
        for layer_name in layer_names:
            matching_layers = [
                layer for layer in available_layers if layer.name == layer_name
            ]
            if matching_layers:
                layers_to_style.extend(matching_layers)
                logger.info(
                    "Found matching layer for '{layer_name}': {[l.name for l in matching_layers]}"
                )
            else:
                logger.warning("No matching layer found for '{layer_name}'")
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
            style_params["stroke_weight"] = (
                stroke_width  # Note: stroke_weight in the model
            )
        if fill_opacity is not None:
            style_params["fill_opacity"] = fill_opacity
        if stroke_opacity is not None:
            style_params["stroke_opacity"] = stroke_opacity
        if radius is not None:
            style_params["radius"] = radius
        if dash_pattern is not None:
            style_params["stroke_dash_array"] = dash_pattern

        # Log the styling parameters being applied
        logger.info("Applying styling to layer '{layer.name}': {style_params}")

        # Initialize with defaults if no style exists
        if not layer_dict.get("style"):
            layer_dict["style"] = {
                "stroke_color": "#3388f",
                "stroke_weight": 2,
                "stroke_opacity": 1.0,
                "fill_color": "#3388f",
                "fill_opacity": 0.3,
                "radius": 8,
                "line_cap": "round",
                "line_join": "round",
            }

        # Update with the provided parameters
        layer_dict["style"].update(style_params)

        # Log the final style after update
        logger.info("Final style for layer '{layer.name}': {layer_dict['style']}")

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
        message = "Successfully applied styling to layer '{styled_layer_names[0]}'. The changes should be visible on the map."
    else:
        message = f"Successfully applied styling to {len(styled_layer_names)} layers: {', '.join(styled_layer_names)}. The changes should be visible on the map."

    return Command(
        update={
            "messages": [
                *state["messages"],
                ToolMessage(
                    name="style_map_layers", content=message, tool_call_id=tool_call_id
                ),
            ],
            "geodata_layers": updated_layers,
        }
    )


# This function is no longer needed - the agent now intelligently chooses colors


@tool
def auto_style_new_layers(
    state: Annotated[Dict[str, Any], InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    layer_names: Optional[List[str]] = None,
) -> Command:
    """
    Automatically detect and trigger styling for newly uploaded layers that have default styling.

    This tool identifies layers that need intelligent styling (those with default blue colors)
    and prompts the agent to apply appropriate cartographic colors based on layer names and descriptions.

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
            matching_layers = [
                layer for layer in available_layers if layer.name == layer_name
            ]
            layers_to_style.extend(matching_layers)
    else:
        # Style all layers that have default styling or no styling
        layers_to_style = [
            layer
            for layer in available_layers
            if not layer.style
            or (
                layer.style
                and layer.style.stroke_color in ["#3388f", None]
                and layer.style.fill_color in ["#3388f", None]
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

    # Create a summary of layers that need styling
    layer_summaries = []

    for layer in layers_to_style:
        summary = "'{layer.name}'"
        if layer.description:
            summary += " (description: {layer.description[:100]}...)"
        elif layer.title:
            summary += " (title: {layer.title})"
        layer_summaries.append(summary)

    layers_summary = "; ".join(layer_summaries)

    message = (
        "Automatically detected {len(layers_to_style)} layer(s) that need intelligent styling: {layers_summary}.\n\n"
        f"I will now analyze each layer name using AI to determine the most appropriate cartographic styling and apply the colors automatically..."
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
            ]
        }
    )


@tool
def check_and_auto_style_layers(
    state: Annotated[Dict[str, Any], InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """
    Automatically check for new layers that need styling and apply appropriate colors.
    This tool should be called proactively when the agent detects layer changes.
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
            and layer.style.stroke_color in ["#3388f", None]
            and layer.style.fill_color in ["#3388f", None]
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
        "Detected {len(layers_needing_style)} newly uploaded layer(s) that need styling: {', '.join(layer_names)}. "
        f"Automatically applying intelligent cartographic styling based on layer names..."
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


def _detect_layers_needing_styling(available_layers):
    """Helper function to detect layers that need styling (used for testing)."""
    return [
        layer
        for layer in available_layers
        if not layer.style
        or (
            layer.style
            and layer.style.stroke_color in ["#3388f", None]
            and layer.style.fill_color in ["#3388ff", None]
        )
    ]
