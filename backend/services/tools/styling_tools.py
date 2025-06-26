"""
AI-powered map layer styling tools for the NaLaMap agent.
"""
from typing import Dict, Any, List, Optional
from typing_extensions import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from langchain_core.tools.base import InjectedToolCallId
from langgraph.types import Command
from langchain_core.messages import ToolMessage
from pydantic import BaseModel, Field
from models.states import GeoDataAgentState
from models.geodata import GeoDataObject, LayerStyle


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
    dash_pattern: Optional[str] = None
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
        return Command(update={
            "messages": [
                *state["messages"], 
                ToolMessage(name="style_map_layers", content=message, tool_call_id=tool_call_id)
            ]
        })
    
    # Determine which layers to style with smart detection
    layers_to_style = []
    
    # Smart single-layer detection
    if len(available_layers) == 1 and not layer_names:
        # Only one layer available and no specific layer names provided
        # Automatically apply styling to the single layer
        layers_to_style = available_layers
    elif layer_names:
        # Use explicitly specified layer names
        for layer_name in layer_names:
            matching_layers = [layer for layer in available_layers if layer.name == layer_name]
            layers_to_style.extend(matching_layers)
    else:
        # Multiple layers available and no specific names provided
        # Style all available layers
        layers_to_style = available_layers
    
    if not layers_to_style:
        message = f"Could not find any layers matching the specified names. Available layers: {', '.join([layer.name for layer in available_layers])}"
        return Command(update={
            "messages": [
                *state["messages"], 
                ToolMessage(name="style_map_layers", content=message, tool_call_id=tool_call_id)
            ]
        })
    
    # Apply styling to selected layers
    styled_layers = []
    for layer in layers_to_style:
        # Create a copy of the layer
        layer_dict = layer.model_dump()
        
        # Build style parameters from the provided arguments
        style_params = {}
        
        if fill_color is not None:
            style_params["fill_color"] = fill_color
        if stroke_color is not None:
            style_params["stroke_color"] = stroke_color
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
        
        # Initialize with defaults if no style exists
        if not layer_dict.get("style"):
            layer_dict["style"] = {
                "stroke_color": "#3388ff",
                "stroke_weight": 2,
                "stroke_opacity": 1.0,
                "fill_color": "#3388ff", 
                "fill_opacity": 0.3,
                "radius": 8,
                "line_cap": "round",
                "line_join": "round"
            }
        
        # Update with the provided parameters
        layer_dict["style"].update(style_params)
        
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
    
    return Command(update={
        "messages": [
            *state["messages"], 
            ToolMessage(name="style_map_layers", content=message, tool_call_id=tool_call_id)
        ], 
        "geodata_layers": updated_layers
    })


# This function is no longer needed - the agent now intelligently chooses colors


@tool
def auto_style_new_layers(
    state: Annotated[Dict[str, Any], InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    layer_names: Optional[List[str]] = None
) -> Command:
    """
    Automatically apply industry-standard colors to new layers based on AI analysis of their names and descriptions.
    
    The agent should analyze each layer name and description, then intelligently choose appropriate colors
    based on cartographic best practices and industry standards. The agent has full knowledge of:
    - Standard cartographic color conventions
    - Industry-standard symbologies for different feature types
    - Color accessibility and contrast principles
    
    This tool should be called when new layers are added to provide appropriate default styling.
    
    Args:
        layer_names: Specific layer names to auto-style (if None, styles all layers needing styling)
    """
    available_layers = state.get("geodata_layers", [])
    
    if not available_layers:
        message = "No layers are currently available to auto-style."
        return Command(update={
            "messages": [
                *state["messages"], 
                ToolMessage(name="auto_style_new_layers", content=message, tool_call_id=tool_call_id)
            ]
        })
    
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
            layer for layer in available_layers 
            if not layer.style or (
                layer.style and 
                layer.style.stroke_color in ["#3388ff", None] and 
                layer.style.fill_color in ["#3388ff", None]
            )
        ]
    
    if not layers_to_style:
        message = "No layers found that need auto-styling."
        return Command(update={
            "messages": [
                *state["messages"], 
                ToolMessage(name="auto_style_new_layers", content=message, tool_call_id=tool_call_id)
            ]
        })
    
    # The agent should now use the style_map_layers tool to apply intelligent styling
    # This approach allows the agent to use its full AI knowledge rather than hardcoded rules
    
    # Create a summary of layers that need styling
    layer_summaries = []
    for layer in layers_to_style:
        summary = f"'{layer.name}'"
        if layer.description:
            summary += f" (description: {layer.description[:100]}...)"
        elif layer.title:
            summary += f" (title: {layer.title})"
        layer_summaries.append(summary)
    
    layers_summary = "; ".join(layer_summaries)
    
    message = (
        f"Ready to apply intelligent auto-styling to {len(layers_to_style)} layer(s): {layers_summary}. "
        f"The agent should now analyze each layer name and description to choose appropriate colors "
        f"using the style_map_layers tool with industry-standard cartographic colors."
    )
    
    return Command(update={
        "messages": [
            *state["messages"], 
            ToolMessage(name="auto_style_new_layers", content=message, tool_call_id=tool_call_id)
        ]
    })

