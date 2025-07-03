import json
import logging
from typing import Any, Dict, List

import geopandas as gpd

from services.tools.geoprocessing.utils import flatten_features

logger = logging.getLogger(__name__)


def op_simplify(
    layers: List[Dict[str, Any]],
    tolerance: float = 0.01,
    preserve_topology: bool = True,
) -> List[Dict[str, Any]]:
    """
    Simplify each feature in the first FeatureCollection with the given tolerance.
    - tolerance: distance parameter for simplification (in the layer's CRS units, usually degrees).
    - preserve_topology: whether to preserve topology during simplification.
    """
    feats = flatten_features(layers)
    if not feats:
        return []
    try:
        gdf = gpd.GeoDataFrame.from_features(feats)
        gdf["geometry"] = gdf.geometry.simplify(
            tolerance, preserve_topology=preserve_topology
        )
        fc = json.loads(gdf.to_json())
        return [fc]
    except Exception as e:
        logger.exception(f"Error in op_simplify: {e}")
        return []
