import logging
import json
from typing import Any, Dict, List, Optional

import geopandas as gpd

logger = logging.getLogger(__name__)


def op_merge(
    layers: List[Dict[str, Any]], on: Optional[List[str]] = None, how: str = "inner"
) -> List[Dict[str, Any]]:
    """
    Perform an attribute-based merge (join) between two layers.
    - layers: expects exactly two FeatureCollections.
    - on: list of column names to join on; if None, GeoPandas uses common columns.
    - how: one of 'inner', 'left', 'right', 'outer'.
    """
    if len(layers) < 2:
        return layers
    try:
        gdf1 = gpd.GeoDataFrame.from_features(layers[0].get("features", []))
        gdf2 = gpd.GeoDataFrame.from_features(layers[1].get("features", []))
        gdf1.set_crs("EPSG:4326", inplace=True)
        gdf2.set_crs("EPSG:4326", inplace=True)

        merged = gdf1.merge(gdf2.drop(columns="geometry"), on=on, how=how)
        # Retain geometry from gdf1
        merged.set_geometry(gdf1.geometry.name, inplace=True)
        return [json.loads(merged.to_json())]
    except Exception as e:
        logger.exception("Error in op_merge: {e}")
        return []
