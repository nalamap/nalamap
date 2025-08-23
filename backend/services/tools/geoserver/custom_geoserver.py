"""
This tool is used to get data from a custom GeoServer instance.
It uses the GetCapabilities endpoint of a GeoServer to get a list of layers
and their descriptions.
"""

import json
import logging
from typing import Any, Dict, List, Union
from urllib.parse import urlencode

from owslib.wms import WebMapService
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from typing_extensions import Annotated

from models.geodata import DataOrigin, DataType, GeoDataObject
from models.settings_model import GeoServerBackend, SettingsSnapshot
from models.states import GeoDataAgentState

logger = logging.getLogger(__name__)


def parse_wms_capabilities(
    wms: WebMapService, geoserver_url: str
) -> List[GeoDataObject]:
    """Parses the WMS GetCapabilities response and returns a list of GeoDataObjects."""
    layers: List[GeoDataObject] = []
    for layer_name, layer in wms.contents.items():
        bounding_box = None
        if layer.boundingBoxWGS84:
            min_lon, min_lat, max_lon, max_lat = layer.boundingBoxWGS84
            bounding_box = (
                f"POLYGON(({max_lon} {min_lat}, {max_lon} {max_lat}, "
                f"{min_lon} {max_lat}, {min_lon} {min_lat}, {max_lon} {min_lat}))"
            )

        # Construct a unique ID from the layer name and server URL
        unique_id = f"geoserver_{geoserver_url}_{layer_name}"

        # Construct a GetMap URL for the data_link
        base_url = geoserver_url.split("?")[0]
        params = {
            "service": "WMS",
            "request": "GetMap",
            "layers": layer.name,
            "format": "image/png",
            "transparent": "true",
            "width": 256,
            "height": 256,
            "bbox": "{bbox-epsg-3857}",
            "srs": "EPSG:3857",
        }
        
        data_link = f"{base_url}?{urlencode(params)}"

        geo_object = GeoDataObject(
            id=unique_id,
            data_source_id=f"geoserver_{layer.name}",
            data_type=DataType.RASTER,
            data_origin=DataOrigin.TOOL.value,
            data_source=wms.provider.contact.organization or "Unknown",
            data_link=data_link,
            name=layer.name,
            title=layer.title,
            description=layer.abstract,
            llm_description=f"WMS layer: {layer.title} from GeoServer at {geoserver_url}",
            score=0.9,
            bounding_box=bounding_box,
            layer_type="WMS",
            properties={
                "styles": layer.styles,
                "srs": layer.crsOptions,
                "keywords": layer.keywords,
            },
        )
        layers.append(geo_object)
    return layers


def fetch_geoserver_capabilities(
    backend: GeoServerBackend,
) -> List[GeoDataObject]:
    """Fetches and parses GetCapabilities from a single GeoServer backend."""
    if not backend.enabled:
        return []

    try:
        wms = WebMapService(
            backend.url,
            version="1.3.0",
            username=backend.username,
            password=backend.password,
        )
        return parse_wms_capabilities(wms, backend.url)
    except Exception as e:
        logger.error(f"Failed to get capabilities from {backend.url}: {e}")
        return []


@tool
def get_custom_geoserver_data(
    state: Annotated[GeoDataAgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Union[Dict[str, Any], ToolMessage]:
    """
    Use this tool to discover available data layers from pre-configured custom GeoServer instances.
    This is useful for finding specific geospatial data that is not available through other tools
    but might be hosted on a dedicated GeoServer.
    The tool returns a list of available layers with their descriptions, which can then be used
    for visualization or analysis.
    """
    options = state.get("options")
    backends: List[GeoServerBackend] = []

    if isinstance(options, SettingsSnapshot):
        backends = options.geoserver_backends
    elif isinstance(options, dict) and "geoserver_backends" in options:
        geoserver_backends_dicts = options["geoserver_backends"]
        if geoserver_backends_dicts:
            backends = [GeoServerBackend(**b) for b in geoserver_backends_dicts]

    if not backends:
        return ToolMessage(
            content="No GeoServer backends configured.", tool_call_id=tool_call_id
        )

    enabled_backends = [b for b in backends if b.enabled]
    if not enabled_backends:
        return ToolMessage(
            content="All configured GeoServer backends are disabled.",
            tool_call_id=tool_call_id,
        )

    all_layers = []
    for backend in enabled_backends:
        all_layers.extend(fetch_geoserver_capabilities(backend))

    if not all_layers:
        return ToolMessage(
            content="No layers found on any of the configured GeoServer instances.",
            tool_call_id=tool_call_id,
        )

    # Update the state with the new layers
    current_layers = state.get("geodata_layers", [])
    updated_layers = current_layers + all_layers
    return {"geodata_layers": updated_layers}


def main():
    """Main function for manual testing."""
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting manual test for custom_geoserver tool.")

    # Example GeoServer backends
    test_backends = [
        GeoServerBackend(
            url="https://io.apps.fao.org/geoserver/wms",
            enabled=True,
            username=None,
            password=None,
        ),
        GeoServerBackend(
            url="https://stable.demo.geonode.org/geoserver/wms",
            enabled=True,
            username=None,
            password=None,
        ),
        GeoServerBackend(
            url="http://invalid.url/geoserver/wms",
            enabled=True,
            username=None,
            password=None,
        ),
    ]

    all_geo_objects = []
    for backend in test_backends:
        all_geo_objects.extend(fetch_geoserver_capabilities(backend))

    if all_geo_objects:
        logger.info(f"Successfully fetched {len(all_geo_objects)} layers.")
        # Print details of the first few layers as an example
        for i, geo_obj in enumerate(all_geo_objects[:3]):
            print(f"--- Layer {i+1} ---")
            print(json.dumps(geo_obj.model_dump(), indent=2)[:2000])
    else:
        logger.warning("No layers were fetched from the test GeoServers.")


if __name__ == "__main__":
    main()
