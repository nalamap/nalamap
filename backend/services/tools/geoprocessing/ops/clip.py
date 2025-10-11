"""
Clip operation: clip one layer by the geometry of another.
"""

import json
import logging
from typing import Any, Dict, List

import geopandas as gpd

from services.tools.geoprocessing.utils import flatten_features

logger = logging.getLogger(__name__)


def op_clip(
    layers: List[Dict[str, Any]],
    crs: str = "EPSG:3857",
) -> List[Dict[str, Any]]:
    """
    Clip the first layer by the geometry of the second layer.

    This operation clips (cuts) the features of the first layer using the
    boundary of the second layer. Only the parts of features from the first
    layer that fall within the second layer are retained.

    Args:
        layers: List of exactly 2 GeoJSON layers. The first layer will be
                clipped by the second layer.
        crs: Working CRS for the operation (default EPSG:3857)

    Returns:
        A list containing a single FeatureCollection with clipped features
    """
    if len(layers) < 2:
        logger.warning("op_clip requires at least 2 layers")
        return layers

    if len(layers) > 2:
        logger.warning(f"op_clip received {len(layers)} layers, using only first 2")

    # Layer to be clipped (target)
    target_layer = layers[0]
    # Layer to clip by (mask)
    mask_layer = layers[1]

    try:
        # Convert target layer to GeoDataFrame
        target_features = flatten_features([target_layer])
        if not target_features:
            return [{"type": "FeatureCollection", "features": []}]

        target_gdf = gpd.GeoDataFrame.from_features(target_features)
        if target_gdf.crs is None:
            target_gdf.set_crs("EPSG:4326", inplace=True)
        target_gdf = target_gdf.to_crs(crs)

        # Convert mask layer to GeoDataFrame
        mask_features = flatten_features([mask_layer])
        if not mask_features:
            return [{"type": "FeatureCollection", "features": []}]

        mask_gdf = gpd.GeoDataFrame.from_features(mask_features)
        if mask_gdf.crs is None:
            mask_gdf.set_crs("EPSG:4326", inplace=True)
        mask_gdf = mask_gdf.to_crs(crs)

        # Combine all mask geometries into one
        from shapely.ops import unary_union

        mask_geometry = unary_union(mask_gdf.geometry)

        # Clip the target layer
        clipped_gdf = target_gdf.clip(mask_geometry)

        # If result is empty, return empty FeatureCollection
        if clipped_gdf.empty:
            return [{"type": "FeatureCollection", "features": []}]

        # Reproject back to EPSG:4326
        clipped_gdf = clipped_gdf.to_crs("EPSG:4326")

        # Convert to GeoJSON
        fc = json.loads(clipped_gdf.to_json())
        return [fc]

    except Exception as exc:
        logger.exception(f"Error in op_clip: {exc}")
        return []
