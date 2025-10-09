"""
Area calculation operation: calculate areas of geometries.
"""

import json
import logging
from typing import Any, Dict, List

import geopandas as gpd

logger = logging.getLogger(__name__)


def op_area(
    layers: List[Dict[str, Any]],
    unit: str = "square_meters",
    crs: str = "EPSG:3857",
    area_column: str = "area",
) -> List[Dict[str, Any]]:
    """
    Calculate the area of each geometry and add it as a property.

    This operation calculates the area of each feature's geometry and adds
    it as a new property. The calculation is performed in the specified CRS
    to ensure accurate results.

    Args:
        layers: List of GeoJSON Feature or FeatureCollection dicts
        unit: Area unit ('square_meters', 'square_kilometers', 'hectares',
              'square_miles', 'acres')
        crs: CRS to use for area calculation (default EPSG:3857, which uses
             meters). Use an equal-area projection for accurate results.
        area_column: Name of the property to store the area value

    Returns:
        A list of FeatureCollections with area property added to each feature
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

            # Reproject to calculation CRS
            gdf = gdf.to_crs(crs)

            # Calculate area in square meters
            gdf[area_column] = gdf.geometry.area * factor

            # Reproject back to EPSG:4326
            gdf = gdf.to_crs("EPSG:4326")

            # Convert back to GeoJSON
            fc = json.loads(gdf.to_json())
            result_layers.append(fc)

        except Exception as exc:
            logger.exception(f"Error calculating area for layer: {exc}")
            result_layers.append(layer)

    return result_layers if result_layers else []
