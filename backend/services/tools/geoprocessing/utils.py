import logging
from typing import Any, Dict, List

import geopandas as gpd
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)


def get_last_human_content(messages: List[Any]) -> str:
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content
    raise ValueError("No human message found in context")


def flatten_features(layers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Given a list of Feature or FeatureCollection dicts, return a flat list of Feature dicts.
    """
    feats: List[Dict[str, Any]] = []
    for layer in layers:
        if layer.get("type") == "FeatureCollection":
            feats.extend(layer.get("features", []))
        elif layer.get("type") == "Feature":
            feats.append(layer)
        else:
            logger.debug(f"Skipping invalid GeoJSON layer: {layer}")
    return feats


def get_layer_geoms(layers: List[Dict[str, Any]]) -> List[Any]:
    """
    Given a list of GeoJSON Feature or FeatureCollection dicts, return a
    list of Shapely geometries, each being the unary_union of one layer's features.
    """
    geoms: List[Any] = []
    for layer in layers:
        layer_type = layer.get("type")
        if layer_type == "FeatureCollection":
            feats = layer.get("features", [])
        elif layer_type == "Feature":
            feats = [layer]
        else:
            logger.debug(f"Skipping layer with missing or invalid type: {layer_type}")
            continue

        if not feats:
            continue

        try:
            gdf = gpd.GeoDataFrame.from_features(feats)
            gdf.set_crs("EPSG:4326", inplace=True)
            geoms.append(gdf.unary_union)
        except Exception:
            logger.exception("Failed to convert features to GeoDataFrame")
    return geoms
