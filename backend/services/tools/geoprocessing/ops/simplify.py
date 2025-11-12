import json
import logging
from typing import Any, Dict, List

import geopandas as gpd

from services.tools.geoprocessing.utils import flatten_features
from services.tools.geoprocessing.projection_utils import (
    prepare_gdf_for_operation,
    OperationType,
)

logger = logging.getLogger(__name__)


def op_simplify(
    layers: List[Dict[str, Any]],
    tolerance: float = 0.01,
    preserve_topology: bool = True,
    auto_optimize_crs: bool = False,
    projection_metadata: bool = False,
    override_crs: str | None = None,
) -> List[Dict[str, Any]]:
    """
    Simplify each feature in the first FeatureCollection with the given tolerance.

    Args:
        layers: Input GeoJSON layers
        tolerance: Distance parameter for simplification (in CRS units)
        preserve_topology: Whether to preserve topology during simplification
        auto_optimize_crs: If True, automatically select optimal CRS
        projection_metadata: If True, include CRS metadata in output
        override_crs: Manual CRS override

    Returns:
        List containing simplified FeatureCollection
    """
    feats = flatten_features(layers)
    if not feats:
        return []
    try:
        gdf = gpd.GeoDataFrame.from_features(feats)
        if gdf.crs is None:
            gdf.set_crs("EPSG:4326", inplace=True)

        # Smart CRS selection for simplification (conformal projections preserve shapes)
        if auto_optimize_crs:
            gdf_prepared, crs_info = prepare_gdf_for_operation(
                gdf,
                OperationType.SIMPLIFY,
                auto_optimize_crs=auto_optimize_crs,
                override_crs=override_crs,
            )
        else:
            gdf_prepared = gdf
            crs_info = {
                "epsg_code": str(gdf.crs) if gdf.crs else "EPSG:4326",
                "selection_reason": "No optimization",
                "auto_selected": False,
            }

        # Perform simplification
        gdf_prepared["geometry"] = gdf_prepared.geometry.simplify(
            tolerance, preserve_topology=preserve_topology
        )

        # Reproject back to EPSG:4326 if needed
        if auto_optimize_crs and str(gdf_prepared.crs) != "EPSG:4326":
            gdf_prepared = gdf_prepared.to_crs("EPSG:4326")

        fc = json.loads(gdf_prepared.to_json())

        # Inject metadata if requested
        if projection_metadata and isinstance(fc, dict):
            if "properties" not in fc:
                fc["properties"] = {}
            fc["properties"]["_crs_metadata"] = crs_info

        return [fc]
    except Exception as e:
        logger.exception(f"Error in op_simplify: {e}")
        return []
