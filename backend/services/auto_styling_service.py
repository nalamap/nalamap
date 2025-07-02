"""
Automatic styling service that can be triggered when layers are uploaded.
"""

import logging
from typing import List, Optional

from langchain_core.messages import AIMessage, HumanMessage

from models.geodata import GeoDataObject
from models.states import GeoDataAgentState
from services.single_agent import single_agent

logger = logging.getLogger(__name__)


async def apply_automatic_styling_to_new_layers(
    geodata_layers: List[GeoDataObject],
) -> List[GeoDataObject]:
    """
    Apply automatic AI-powered styling to newly uploaded layers.

    Args:
        geodata_layers: List of layers that may need automatic styling

    Returns:
        List of layers with AI-applied styling
    """
    if not geodata_layers:
        return geodata_layers

    # Check if any layers need automatic styling (have default blue colors)
    layers_needing_styling = []
    for layer in geodata_layers:
        if not layer.style or (
            layer.style
            and layer.style.stroke_color in ["#3388f", None]
            and layer.style.fill_color in ["#3388f", None]
        ):
            layers_needing_styling.append(layer)

    if not layers_needing_styling:
        logger.info("No layers need automatic styling")
        return geodata_layers

    logger.info("Applying automatic styling to {len(layers_needing_styling)} layers")

    # Create a message that triggers the automatic styling workflow
    layer_names = [layer.name for layer in layers_needing_styling]
    styling_prompt = (
        "I've detected {len(layers_needing_styling)} newly uploaded layer(s) that need automatic styling: "
        "{', '.join(layer_names)}. Please apply intelligent AI-powered styling to these layers based on their names. "
        "Use your best judgment to determine appropriate cartographic colors for each layer."
    )

    # Create state for the agent
    state = GeoDataAgentState(
        messages=[HumanMessage(content=styling_prompt)],
        geodata_last_results=[],
        geodata_layers=geodata_layers,
        results_title="",
        geodata_results=[],
    )

    try:
        # Invoke the single agent to apply automatic styling
        result = single_agent.invoke(state, debug=False)

        # Return the updated layers with applied styling
        updated_layers = result.get("geodata_layers", geodata_layers)
        logger.info(
            "Successfully applied automatic styling to {len(layers_needing_styling)} layers"
        )
        return updated_layers

    except Exception as e:
        logger.error("Error applying automatic styling: {str(e)}")
        # Return original layers if styling fails
        return geodata_layers


def trigger_automatic_styling_for_upload(
    layer_name: str, geodata_layers: List[GeoDataObject]
) -> List[GeoDataObject]:
    """
    Synchronous wrapper for triggering automatic styling when a layer is uploaded.

    Args:
        layer_name: Name of the newly uploaded layer
        geodata_layers: Current list of layers including the new one

    Returns:
        Updated list of layers with styling applied
    """
    # For now, just return the original layers since we need async context
    # This could be enhanced to use asyncio.run() if needed
    logger.info(
        "Layer '{layer_name}' uploaded - automatic styling will be triggered on next chat interaction"
    )
    return geodata_layers
