import json
import logging
from typing import Any, Dict, List

import geopandas as gpd

logger = logging.getLogger(__name__)


def op_centroid(
    layers: List[Dict[str, Any]],
    projection_metadata: bool = False,
    **kwargs,
) -> List[Dict[str, Any]]:
    """
    Compute the centroid of each feature in the first FeatureCollection and
    return a new FeatureCollection of Point features.
    """
    if not layers:
        return []
    layer = layers[0]
    feats = layer.get("features", [])
    if not feats:
        return []

    try:
        gdf = gpd.GeoDataFrame.from_features(feats)
        gdf.set_crs("EPSG:4326", inplace=True)
        centroids = gdf
        centroids["geometry"] = gdf.geometry.centroid
        fc = json.loads(centroids.to_json())

        if projection_metadata and isinstance(fc, dict):
            if "properties" not in fc:
                fc["properties"] = {}
            fc["properties"]["_crs_metadata"] = {
                "epsg_code": "EPSG:4326",
                "crs_name": "WGS 84 Geographic",
                "selection_reason": "Centroid operation is projection-insensitive",
                "auto_selected": True,
            }

        return [fc]
    except Exception as e:
        logger.exception(f"Error in op_centroid: {e}")
        return []
