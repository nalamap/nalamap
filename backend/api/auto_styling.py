import logging
from typing import Any, Dict, List

from fastapi import APIRouter
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from models.geodata import GeoDataObject
from models.states import GeoDataAgentState
from services.single_agent import single_agent

logger = logging.getLogger(__name__)

router = APIRouter()


class AutoStyleRequest(BaseModel):
    layers: List[Dict[str, Any]]


class AutoStyleResponse(BaseModel):
    success: bool
    message: str
    styled_layers: List[Dict[str, Any]]


@router.post("/auto-style", response_model=AutoStyleResponse)
async def auto_style_layers(request: AutoStyleRequest):
    """
    Apply automatic AI-powered styling to uploaded layers based on their names.
    """
    try:
        if not request.layers:
            return AutoStyleResponse(
                success=True, message="No layers provided for styling", styled_layers=[]
            )

        # Convert dict layers to GeoDataObject instances
        geodata_layers = []
        for layer_dict in request.layers:
            try:
                # Create GeoDataObject from the layer dict
                layer = GeoDataObject(**layer_dict)
                geodata_layers.append(layer)
            except Exception as e:
                logger.warning("Could not convert layer to GeoDataObject: {e}")
                continue

        if not geodata_layers:
            return AutoStyleResponse(
                success=False,
                message="No valid layers found for styling",
                styled_layers=[],
            )

        # Check if any layers need automatic styling (have default colors or no style)
        layers_needing_styling = []
        for layer in geodata_layers:
            needs_styling = (
                not hasattr(layer, "style")
                or layer.style is None
                or (
                    layer.style.stroke_color in ["#3388f", None]
                    and layer.style.fill_color in ["#3388f", None]
                )
            )
            if needs_styling:
                layers_needing_styling.append(layer)

        if not layers_needing_styling:
            # Convert back to dicts
            styled_layer_dicts = [
                layer.dict() if hasattr(layer, "dict") else layer.__dict__
                for layer in geodata_layers
            ]
            return AutoStyleResponse(
                success=True,
                message="No layers need automatic styling - all already have custom styling",
                styled_layers=styled_layer_dicts,
            )

        # Create a message that triggers automatic styling
        layer_names = [layer.name for layer in layers_needing_styling]
        styling_prompt = (
            "I've detected {len(layers_needing_styling)} newly uploaded layer(s) that need automatic styling: "
            "{', '.join(layer_names)}. Please check for layers needing styling using check_and_auto_style_layers, "
            "then analyze the layer names using auto_style_new_layers, and finally apply intelligent "
            "AI-powered styling to these layers using style_map_layers with appropriate cartographic colors."
        )

        # Create state for the agent
        state = GeoDataAgentState(
            messages=[HumanMessage(content=styling_prompt)],
            geodata_last_results=[],
            geodata_layers=geodata_layers,
            results_title="",
            geodata_results=[],
        )

        # Invoke the single agent to apply automatic styling
        result = single_agent.invoke(state, debug=False)

        # Get the updated layers with applied styling
        updated_layers = result.get("geodata_layers", geodata_layers)

        # Convert back to dicts for the response
        styled_layer_dicts = []
        for layer in updated_layers:
            if hasattr(layer, "dict"):
                styled_layer_dicts.append(layer.dict())
            else:
                styled_layer_dicts.append(layer.__dict__)

        logger.info(
            "Successfully applied automatic styling to {len(layers_needing_styling)} layers"
        )

        return AutoStyleResponse(
            success=True,
            message=f"Successfully applied automatic AI styling to {len(layers_needing_styling)} layer(s)",
            styled_layers=styled_layer_dicts,
        )

    except Exception as e:
        logger.error("Error in auto_style_layers: {str(e)}")
        return AutoStyleResponse(
            success=False,
            message="Error applying automatic styling: {str(e)}",
            styled_layers=request.layers,  # Return original layers on error
        )
