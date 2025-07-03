import json
import logging
from typing import Any, Dict, List

import geopandas as gpd

logger = logging.getLogger(__name__)


def op_sjoin(
    layers: List[Dict[str, Any]], how: str = "inner", predicate: str = "intersects"
) -> List[Dict[str, Any]]:
    """
    Perform a spatial join between two layers.
    - layers: expects exactly two FeatureCollections (left, right).
    - how: 'left', 'right', or 'inner'.
    - predicate: spatial predicate, e.g. 'intersects', 'contains', 'within'.
    """
    if len(layers) < 2:
        return layers
    try:
        left_gdf = gpd.GeoDataFrame.from_features(layers[0].get("features", []))
        right_gdf = gpd.GeoDataFrame.from_features(layers[1].get("features", []))
        left_gdf.set_crs("EPSG:4326", inplace=True)
        right_gdf.set_crs("EPSG:4326", inplace=True)

        joined = gpd.sjoin(left_gdf, right_gdf, how=how, predicate=predicate)
        return [json.loads(joined.to_json())]
    except Exception as e:
        logger.exception(f"Error in op_sjoin: {e}")
        return []
