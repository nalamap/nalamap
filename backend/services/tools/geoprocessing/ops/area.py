"""
Area calculation operation: calculate areas of geometries.

Uses smart planar CRS selection with equal-area projections for accurate
area calculations across different geographic extents.
"""

import json
import logging
from typing import Any, Dict, List

import geopandas as gpd

from services.tools.geoprocessing.projection_utils import (
    prepare_gdf_for_operation,
    OperationType,
)

logger = logging.getLogger(__name__)


def op_area(
    layers: List[Dict[str, Any]],
    unit: str = "square_meters",
    crs: str = "EPSG:3857",
    area_column: str = "area",
    auto_optimize_crs: bool = False,
    projection_metadata: bool = False,
) -> List[Dict[str, Any]]:
    """
    Calculate the area of each geometry and add it as a property.

    Uses smart planar CRS selection with equal-area projections to provide
    accurate area calculations (<1% error) for most geographic extents.

    Args:
        layers: List of GeoJSON Feature or FeatureCollection dicts
        unit: Area unit ('square_meters', 'square_kilometers', 'hectares',
              'square_miles', 'acres')
        crs: Default CRS for area calculation (default EPSG:3857)
        area_column: Name of the property to store the area value
        auto_optimize_crs: Enable smart CRS selection (recommended)
        projection_metadata: Include CRS metadata in response

    Returns:
        List of FeatureCollections with area property added to each feature
    """
    if not layers:
        logger.warning("op_area called with no layers")
        return []

    # Conversion factors from square meters
    unit_factors = {
        "square_meters": 1.0,
        "square_kilometers": 1e-6,
        "hectares": 1e-4,
        "square_miles": 3.861e-7,
        "acres": 0.000247105,
    }

    factor = unit_factors.get(unit.lower())
    if factor is None:
        logger.warning(
            f"Unknown area unit '{unit}', using square_meters. "
            f"Valid units: {list(unit_factors.keys())}"
        )
        factor = 1.0

    result_layers = []

    for layer in layers:
        layer_type = layer.get("type")

        # Extract features
        if layer_type == "FeatureCollection":
            features = layer.get("features", [])
        elif layer_type == "Feature":
            features = [layer]
        else:
            logger.debug(f"Skipping layer with invalid type: {layer_type}")
            continue

        if not features:
            result_layers.append(layer)
            continue

        try:
            # Create GeoDataFrame
            gdf = gpd.GeoDataFrame.from_features(features)
            if gdf.crs is None:
                gdf.set_crs("EPSG:4326", inplace=True)

            # Planar area calculation with smart CRS selection
            if auto_optimize_crs:
                # Use smart equal-area CRS selection
                gdf_calc, crs_info = prepare_gdf_for_operation(
                    gdf,
                    OperationType.AREA,
                    auto_optimize_crs=True,
                    override_crs=(None if crs == "EPSG:3857" else crs),
                )
            else:
                # Use default or specified CRS
                gdf_calc = gdf.to_crs(crs)
                crs_info = {
                    "epsg_code": crs,
                    "crs_name": f"CRS: {crs}",
                    "selection_reason": "Default CRS",
                    "auto_selected": False,
                }

            # Calculate area in the selected CRS (assumed square meters)
            gdf_calc[area_column] = gdf_calc.geometry.area * factor

            # Reproject back to EPSG:4326
            gdf_result = gdf_calc.to_crs("EPSG:4326")

            # Convert back to GeoJSON
            fc = json.loads(gdf_result.to_json())

            # Include metadata if requested or if auto_optimize is on
            if (
                (projection_metadata or auto_optimize_crs)
                and isinstance(fc, dict)
                and fc.get("features")
            ):
                if "properties" not in fc:
                    fc["properties"] = {}
                fc["properties"]["_crs_metadata"] = crs_info

            result_layers.append(fc)

        except Exception as exc:
            logger.exception(f"Error calculating area for layer: {exc}")
            result_layers.append(layer)

    return result_layers if result_layers else []
