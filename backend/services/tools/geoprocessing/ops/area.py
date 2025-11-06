"""
Area calculation operation: calculate areas of geometries.

Supports hybrid planar/geodesic area calculation:
- Planar: uses equal-area projection (fast, accurate for local/regional)
- Geodesic: uses ellipsoid math (accurate globally, high latitudes, zone seams)
"""

import json
import logging
from typing import Any, Dict, List, Literal, Tuple

import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
from pyproj import Geod

from services.tools.geoprocessing.projection_utils import (
    prepare_gdf_for_operation,
    OperationType,
    compute_bbox_metrics,
)

logger = logging.getLogger(__name__)


# ========== Area Method Selection ==========


def choose_area_method(bbox_metrics: Dict[str, Any]) -> Tuple[str, str]:
    """
    Decide whether to use planar or geodesic area calculation.

    Criteria for geodesic:
    - High latitude (|center_lat| >= 75°)
    - Cross-zone (zone_span >= 2)
    - Antimeridian crossing
    - Non-local extent (>6° either dimension)

    Args:
        bbox_metrics: Output from compute_bbox_metrics

    Returns:
        Tuple of (method, reason) where method is 'planar' or 'geodesic'
    """
    reasons = []

    # Check latitude
    if abs(bbox_metrics["center_lat"]) >= 75:
        reasons.append(f"High latitude ({bbox_metrics['center_lat']:.1f}°)")

    # Check zone boundaries
    if bbox_metrics["zone_span"] >= 2:
        reasons.append(f"Crosses {bbox_metrics['zone_span']} UTM zones")

    # Check antimeridian
    if bbox_metrics["antimeridian_crossing"]:
        reasons.append("Crosses antimeridian")

    # Check if non-local
    if bbox_metrics["lon_extent"] > 6 or bbox_metrics["lat_extent"] > 6:
        lon_ext = bbox_metrics["lon_extent"]
        lat_ext = bbox_metrics["lat_extent"]
        reasons.append(f"Non-local extent ({lon_ext:.1f}° × {lat_ext:.1f}°)")

    # Decision
    if reasons:
        return "geodesic", "; ".join(reasons)
    else:
        return "planar", "Local/regional extent, equal-area CRS suitable"


def compute_geodesic_area(geometry, geod: Geod) -> float:
    """
    Calculate geodesic area on ellipsoid using pyproj.Geod.

    Args:
        geometry: Shapely Polygon or MultiPolygon
        geod: pyproj Geod instance

    Returns:
        Area in square meters (always positive)
    """
    if isinstance(geometry, Polygon):
        # Exterior ring
        exterior_coords = list(geometry.exterior.coords)
        lons = [c[0] for c in exterior_coords]
        lats = [c[1] for c in exterior_coords]
        area, _ = geod.polygon_area_perimeter(lons, lats)
        total_area = abs(area)

        # Subtract holes
        for interior in geometry.interiors:
            interior_coords = list(interior.coords)
            lons = [c[0] for c in interior_coords]
            lats = [c[1] for c in interior_coords]
            hole_area, _ = geod.polygon_area_perimeter(lons, lats)
            total_area -= abs(hole_area)

        return total_area

    elif isinstance(geometry, MultiPolygon):
        # Sum areas of all parts
        return sum(compute_geodesic_area(poly, geod) for poly in geometry.geoms)

    else:
        # Non-polygon geometries have zero area
        logger.debug(f"Geodesic area not supported for {geometry.geom_type}, returning 0")
        return 0.0


def op_area(
    layers: List[Dict[str, Any]],
    unit: str = "square_meters",
    crs: str = "EPSG:3857",
    area_column: str = "area",
    auto_optimize_crs: bool = False,
    area_method: Literal["auto", "planar", "geodesic"] = "auto",
    projection_metadata: bool = False,
) -> List[Dict[str, Any]]:
    """
    Calculate the area of each geometry and add it as a property.

    This operation calculates the area of each feature's geometry and adds
    it as a new property. Supports hybrid planar/geodesic calculation.

    Args:
        layers: List of GeoJSON Feature or FeatureCollection dicts
        unit: Area unit ('square_meters', 'square_kilometers', 'hectares',
              'square_miles', 'acres')
        crs: CRS to use for planar area calculation (default EPSG:3857).
             Use an equal-area projection for accurate results.
        area_column: Name of the property to store the area value
        auto_optimize_crs: Enable smart CRS selection for planar path
        area_method: Calculation method:
            - 'auto': Choose planar or geodesic based on data characteristics
            - 'planar': Use projected CRS (fast, good for local/regional)
            - 'geodesic': Use ellipsoid math (accurate globally, high lat, seams)
        projection_metadata: Include CRS and method metadata in response

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

            # Compute bbox metrics for method selection
            bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
            bbox = (bounds[0], bounds[1], bounds[2], bounds[3])
            bbox_metrics = compute_bbox_metrics(bbox)

            # Decide area calculation method
            if area_method == "auto":
                chosen_method, method_reason = choose_area_method(bbox_metrics)
            else:
                chosen_method = area_method
                method_reason = f"User-specified method: {area_method}"

            logger.info(f"Area method selected: {chosen_method} ({method_reason})")

            # Branch: Geodesic or Planar
            if chosen_method == "geodesic":
                # Geodesic path - ellipsoid calculation
                logger.info("Calculating geodesic area on WGS84 ellipsoid")
                geod = Geod(ellps="WGS84")

                # Calculate area for each geometry
                areas = []
                for geom in gdf.geometry:
                    try:
                        area_m2 = compute_geodesic_area(geom, geod)
                        areas.append(area_m2 * factor)
                    except Exception as e:
                        logger.warning(f"Error computing geodesic area: {e}, setting to 0")
                        areas.append(0.0)

                gdf[area_column] = areas

                # Geometry stays in EPSG:4326, no reprojection needed
                gdf_result = gdf

                # Create metadata
                crs_info = {
                    "epsg_code": "EPSG:4326",
                    "crs_name": "WGS84 Geographic (geodesic area)",
                    "selection_reason": "Geodesic area on ellipsoid",
                    "auto_selected": area_method == "auto",
                    "area_method": "geodesic",
                    "area_method_reason": method_reason,
                }

            else:
                # Planar path - projected CRS calculation
                if auto_optimize_crs:
                    gdf_calc, crs_info = prepare_gdf_for_operation(
                        gdf,
                        OperationType.AREA,
                        auto_optimize_crs=True,
                        override_crs=(None if crs == "EPSG:3857" else crs),
                    )
                else:
                    gdf_calc = gdf.to_crs(crs)
                    crs_info = {
                        "epsg_code": crs,
                        "crs_name": f"User-specified CRS: {crs}",
                        "selection_reason": "Default CRS",
                        "auto_selected": False,
                    }

                # Calculate area in calculation CRS units (assumed square meters)
                gdf_calc[area_column] = gdf_calc.geometry.area * factor

                # Reproject back to EPSG:4326
                gdf_result = gdf_calc.to_crs("EPSG:4326")

                # Add area method metadata
                crs_info["area_method"] = "planar"
                crs_info["area_method_reason"] = method_reason

            # Convert back to GeoJSON
            fc = json.loads(gdf_result.to_json())

            # Include metadata if requested or if auto_optimize is on
            if (
                (projection_metadata or auto_optimize_crs or chosen_method == "geodesic")
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
