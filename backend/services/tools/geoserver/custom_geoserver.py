"""
This tool is used to get data from a custom GeoServer instance.
It uses the GetCapabilities endpoint of a GeoServer to get a list of layers
and their descriptions across WMS, WFS, WCS, and WMTS services.
"""

import json
import logging
from typing import Any, Dict, List, Union
from urllib.parse import urlencode, urljoin

from owslib.wcs import WebCoverageService
from owslib.wfs import WebFeatureService
from owslib.wms import WebMapService
from owslib.wmts import WebMapTileService
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from typing_extensions import Annotated

from models.geodata import DataOrigin, DataType, GeoDataObject
from models.settings_model import GeoServerBackend, SettingsSnapshot
from models.states import GeoDataAgentState

logger = logging.getLogger(__name__)


def merge_layers(
    base_layers: Dict[str, GeoDataObject], new_layers: Dict[str, GeoDataObject]
) -> Dict[str, GeoDataObject]:
    """Merges new layer information into a base dictionary of layers."""
    for layer_id, new_layer in new_layers.items():
        if layer_id in base_layers:
            # Merge service links
            if new_layer.service_links:
                if base_layers[layer_id].service_links is None:
                    base_layers[layer_id].service_links = {}
                base_layers[layer_id].service_links.update(new_layer.service_links)
            # Optionally, update other fields if they are empty
            if not base_layers[layer_id].description and new_layer.description:
                base_layers[layer_id].description = new_layer.description
            if not base_layers[layer_id].bounding_box and new_layer.bounding_box:
                base_layers[layer_id].bounding_box = new_layer.bounding_box
        else:
            base_layers[layer_id] = new_layer
    return base_layers


def parse_wms_capabilities(
    wms, geoserver_url: str
) -> Dict[str, GeoDataObject]:
    """Parses WMS GetCapabilities and returns a dictionary of GeoDataObjects."""
    layers: Dict[str, GeoDataObject] = {}
    base_url = geoserver_url.split("?")[0]

    for layer_name, layer in wms.contents.items():
        bounding_box = None
        if layer.boundingBoxWGS84:
            min_lon, min_lat, max_lon, max_lat = layer.boundingBoxWGS84
            bounding_box = (
                f"POLYGON(({max_lon} {min_lat}, {max_lon} {max_lat}, "
                f"{min_lon} {max_lat}, {min_lon} {min_lat}, {max_lon} {min_lat}))"
            )

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
            id=layer.name,
            data_source_id=f"geoserver_{layer.name}",
            data_type=DataType.RASTER,
            data_origin=DataOrigin.TOOL.value,
            data_source=wms.provider.contact.organization or "Unknown",
            data_link=data_link,
            name=layer.name,
            title=layer.title or layer.name,
            description=layer.abstract,
            llm_description=f"WMS layer: {layer.title} from GeoServer at {geoserver_url}",
            score=0.9,
            bounding_box=bounding_box,
            layer_type="WMS",
            properties={"srs": layer.crsOptions, "keywords": layer.keywords},
            service_links={"WMS": data_link},
        )
        layers[layer.name] = geo_object
    return layers


def parse_wfs_capabilities(
    wfs, geoserver_url: str
) -> Dict[str, GeoDataObject]:
    """Parses WFS GetCapabilities and returns a dictionary of GeoDataObjects."""
    layers: Dict[str, GeoDataObject] = {}
    base_url = geoserver_url.split("?")[0]

    for ft_name, ft in wfs.contents.items():
        bounding_box = None
        if ft.boundingBoxWGS84:
            min_lon, min_lat, max_lon, max_lat = ft.boundingBoxWGS84
            bounding_box = (
                f"POLYGON(({max_lon} {min_lat}, {max_lon} {max_lat}, "
                f"{min_lon} {max_lat}, {min_lon} {min_lat}, {max_lon} {min_lat}))"
            )

        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeName": ft.id,
            "outputFormat": "application/json",
        }
        data_link = f"{base_url}?{urlencode(params)}"

        geo_object = GeoDataObject(
            id=ft.id,
            data_source_id=f"geoserver_{ft.id}",
            data_type=DataType.GEOJSON,
            data_origin=DataOrigin.TOOL.value,
            data_source=wfs.provider.name or "Unknown",
            data_link=data_link,
            name=ft.id,
            title=ft.title or ft.id,
            description=ft.abstract,
            llm_description=f"WFS layer: {ft.title} from GeoServer at {geoserver_url}",
            score=0.9,
            bounding_box=bounding_box,
            layer_type="WFS",
            properties={"srs": ft.crsOptions, "keywords": ft.keywords},
            service_links={"WFS": data_link},
        )
        layers[ft.id] = geo_object
    return layers


def parse_wcs_capabilities(
    wcs, geoserver_url: str
) -> Dict[str, GeoDataObject]:
    """Parses WCS GetCapabilities and returns a dictionary of GeoDataObjects."""
    layers: Dict[str, GeoDataObject] = {}
    base_url = geoserver_url.split("?")[0]

    for cov_id, cov in wcs.contents.items():
        bounding_box = None
        if cov.boundingBoxWGS84:
            min_lon, min_lat, max_lon, max_lat = cov.boundingBoxWGS84
            bounding_box = (
                f"POLYGON(({max_lon} {min_lat}, {max_lon} {max_lat}, "
                f"{min_lon} {max_lat}, {min_lon} {min_lat}, {max_lon} {min_lat}))"
            )

        params = {
            "service": "WCS",
            "version": "2.0.1",
            "request": "GetCoverage",
            "coverageId": cov.id,
        }
        data_link = f"{base_url}?{urlencode(params)}"

        geo_object = GeoDataObject(
            id=cov.id,
            data_source_id=f"geoserver_{cov.id}",
            data_type=DataType.RASTER,
            data_origin=DataOrigin.TOOL.value,
            data_source=wcs.provider.name or "Unknown",
            data_link=data_link,
            name=cov.id,
            title=cov.title or cov.id,
            description=cov.abstract,
            llm_description=f"WCS layer: {cov.title} from GeoServer at {geoserver_url}",
            score=0.9,
            bounding_box=bounding_box,
            layer_type="WCS",
            properties={"supported_formats": cov.supportedFormats},
            service_links={"WCS": data_link},
        )
        layers[cov.id] = geo_object
    return layers


def parse_wmts_capabilities(
    wmts, geoserver_url: str
) -> Dict[str, GeoDataObject]:
    """Parses WMTS GetCapabilities and returns a dictionary of GeoDataObjects."""
    layers: Dict[str, GeoDataObject] = {}

    for layer_id, layer in wmts.contents.items():
        bounding_box = None
        if layer.boundingBoxWGS84:
            min_lon, min_lat, max_lon, max_lat = layer.boundingBoxWGS84
            bounding_box = (
                f"POLYGON(({max_lon} {min_lat}, {max_lon} {max_lat}, "
                f"{min_lon} {max_lat}, {min_lon} {min_lat}, {max_lon} {min_lat}))"
            )

        # WMTS link is a template
        data_link = ""
        if layer.tilematrixsetlinks:
            # Get the first available tile matrix link template
            first_link = list(layer.tilematrixsetlinks.values())[0]
            data_link = first_link.template.format(
                TileMatrix="{TileMatrix}", TileRow="{TileRow}", TileCol="{TileCol}"
            )

        geo_object = GeoDataObject(
            id=layer.id,
            data_source_id=f"geoserver_{layer.id}",
            data_type=DataType.RASTER,
            data_origin=DataOrigin.TOOL.value,
            data_source=wmts.provider.name or "Unknown",
            data_link=data_link,
            name=layer.id,
            title=layer.title or layer.id,
            description=layer.abstract,
            llm_description=f"WMTS layer: {layer.title} from GeoServer at {geoserver_url}",
            score=0.9,
            bounding_box=bounding_box,
            layer_type="WMTS",
            properties={"tile_matrix_sets": list(layer.tilematrixsetlinks.keys())},
            service_links={"WMTS": data_link},
        )
        layers[layer.id] = geo_object
    return layers


def fetch_all_service_capabilities(
    backend: GeoServerBackend,
) -> Dict[str, GeoDataObject]:
    """Fetches capabilities from all services and merges them."""
    if not backend.enabled:
        return {}

    base_url = backend.url
    username = backend.username
    password = backend.password
    all_layers: Dict[str, GeoDataObject] = {}

    # WMS
    wms_url = urljoin(base_url, "wms")
    try:
        wms = WebMapService(
            wms_url, version="1.3.0", username=username, password=password
        )
        wms_layers = parse_wms_capabilities(wms, wms_url)
        all_layers = merge_layers(all_layers, wms_layers)
    except Exception as e:
        logger.warning(f"Could not fetch WMS capabilities from {wms_url}: {e}")

    # WFS
    wfs_url = urljoin(base_url, "wfs")
    try:
        wfs = WebFeatureService(
            wfs_url, version="2.0.0", username=username, password=password
        )
        wfs_layers = parse_wfs_capabilities(wfs, wfs_url)
        all_layers = merge_layers(all_layers, wfs_layers)
    except Exception as e:
        logger.warning(f"Could not fetch WFS capabilities from {wfs_url}: {e}")

    # WCS
    wcs_url = urljoin(base_url, "wcs")
    try:
        wcs = WebCoverageService(wcs_url, version="2.0.1")
        wcs_layers = parse_wcs_capabilities(wcs, wcs_url)
        all_layers = merge_layers(all_layers, wcs_layers)
    except Exception as e:
        logger.warning(f"Could not fetch WCS capabilities from {wcs_url}: {e}")

    # WMTS
    wmts_url = urljoin(base_url, "gwc/service/wmts")
    try:
        wmts = WebMapTileService(wmts_url, username=username, password=password)
        wmts_layers = parse_wmts_capabilities(wmts, wmts_url)
        all_layers = merge_layers(all_layers, wmts_layers)
    except Exception as e:
        logger.warning(f"Could not fetch WMTS capabilities from {wmts_url}: {e}")

    return all_layers


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

    all_layers_dict: Dict[str, GeoDataObject] = {}
    for backend in enabled_backends:
        backend_layers = fetch_all_service_capabilities(backend)
        all_layers_dict = merge_layers(all_layers_dict, backend_layers)

    if not all_layers_dict:
        return ToolMessage(
            content="No layers found on any of the configured GeoServer instances.",
            tool_call_id=tool_call_id,
        )

    # Update the state with the new layers
    current_layers = state.get("geodata_layers", [])
    # Create a dict of current layers for efficient lookup
    current_layers_dict = {layer.id: layer for layer in current_layers}
    
    updated_layers_dict = merge_layers(current_layers_dict, all_layers_dict)
    
    return {"geodata_layers": list(updated_layers_dict.values())}


def main():
    """Main function for manual testing."""
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting manual test for custom_geoserver tool.")

    # Example GeoServer backends
    test_backends = [
        GeoServerBackend(
            url="https://io.apps.fao.org/geoserver/",
            enabled=True,
            username=None,
            password=None,
        ),
        GeoServerBackend(
            url="https://stable.demo.geonode.org/geoserver/",
            enabled=True,
            username=None,
            password=None,
        ),
    ]

    all_geo_objects_dict: Dict[str, GeoDataObject] = {}
    for backend in test_backends:
        backend_layers = fetch_all_service_capabilities(backend)
        all_geo_objects_dict = merge_layers(all_geo_objects_dict, backend_layers)

    if all_geo_objects_dict:
        logger.info(f"Successfully fetched {len(all_geo_objects_dict)} unique layers.")
        # Print details of the first few layers as an example
        for i, geo_obj in enumerate(list(all_geo_objects_dict.values())[:3]):
            print(f"--- Layer {i+1} ---")
            print(json.dumps(geo_obj.model_dump(), indent=2))
    else:
        logger.warning("No layers were fetched from the test GeoServers.")


if __name__ == "__main__":
    main()
