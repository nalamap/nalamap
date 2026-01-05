import json
import logging
from typing import Any, Dict, List

import geopandas as gpd
from services.tools.geoprocessing.projection_utils import (
    prepare_gdf_for_operation,
    OperationType,
)

logger = logging.getLogger(__name__)


def op_sjoin(
    layers: List[Dict[str, Any]],
    how: str = "inner",
    predicate: str = "intersects",
    auto_optimize_crs: bool = False,
    projection_metadata: bool = False,
    override_crs: str | None = None,
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

        if auto_optimize_crs:
            left_prepared, left_info = prepare_gdf_for_operation(
                left_gdf,
                OperationType.SJOIN,
                auto_optimize_crs=auto_optimize_crs,
                override_crs=override_crs,
            )
            right_prepared, right_info = prepare_gdf_for_operation(
                right_gdf,
                OperationType.SJOIN,
                auto_optimize_crs=False,
                override_crs=left_info.get("epsg_code"),
            )

            joined = gpd.sjoin(left_prepared, right_prepared, how=how, predicate=predicate)
            fc = json.loads(joined.to_json())
            if projection_metadata and isinstance(fc, dict):
                if "properties" not in fc:
                    fc["properties"] = {}
                fc["properties"]["_crs_metadata"] = {"left": left_info, "right": right_info}
            return [fc]
        else:
            # Legacy behavior: operate in EPSG:4326
            joined = gpd.sjoin(left_gdf, right_gdf, how=how, predicate=predicate)
            return [json.loads(joined.to_json())]
    except Exception as e:
        logger.exception(f"Error in op_sjoin: {e}")
        return []
