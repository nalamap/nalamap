import json
import logging
from typing import Any, Dict, List, Optional

import geopandas as gpd

logger = logging.getLogger(__name__)


def op_sjoin_nearest(
    layers: List[Dict[str, Any]],
    how: str = "inner",
    max_distance: Optional[float] = None,
    distance_col: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Perform a nearest-neighbor spatial join between two layers.
    - layers: expects exactly two FeatureCollections (left, right).
    - how: 'left', 'right', or 'inner'.
    - max_distance: maximum search radius (in layer CRS units).
    - distance_col: name of the output column to store distance.
    """
    if len(layers) < 2:
        return layers
    try:
        left_gdf = gpd.GeoDataFrame.from_features(
            layers[0].get("features", [])
        )
        right_gdf = gpd.GeoDataFrame.from_features(
            layers[1].get("features", [])
        )
        left_gdf.set_crs("EPSG:4326", inplace=True)
        right_gdf.set_crs("EPSG:4326", inplace=True)

        joined = gpd.sjoin_nearest(
            left_gdf,
            right_gdf,
            how=how,
            max_distance=max_distance,
            distance_col=distance_col,
        )
        return [json.loads(joined.to_json())]
    except Exception as e:
        logger.exception(f"Error in op_sjoin_nearest: {e}")
        return []
