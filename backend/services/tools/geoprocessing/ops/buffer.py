import json
import logging
from typing import Dict, Any, Tuple

import geopandas as gpd
from shapely.ops import unary_union
from shapely.geometry import Point, MultiPoint, Polygon
from pyproj import Geod

from services.tools.geoprocessing.projection_utils import (
    prepare_gdf_for_operation,
    OperationType,
    compute_bbox_metrics,
)

logger = logging.getLogger(__name__)


# ========== Buffer Method Selection ==========


def choose_buffer_method(
    gdf: gpd.GeoDataFrame, radius_m: float, bbox_metrics: Dict[str, Any]
) -> Tuple[str, str]:
    """
    Decide whether to use planar or geodesic buffering.

    Criteria for geodesic:
    - Large radius (>50 km)
    - High latitude (|center_lat| >= 75°)
    - Cross-zone or antimeridian
    - Non-local extent (>6° either dimension)

    Args:
        gdf: GeoDataFrame in EPSG:4326
        radius_m: Buffer radius in meters
        bbox_metrics: Output from compute_bbox_metrics

    Returns:
        Tuple of (method, reason) where method is 'planar' or 'geodesic'
    """
    reasons = []

    # Check radius threshold
    if radius_m > 50000:  # 50 km
        reasons.append(f"Large radius ({radius_m/1000:.1f} km > 50 km)")

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
        reasons.append(
            f"Non-local extent ({bbox_metrics['lon_extent']:.1f}° × {bbox_metrics['lat_extent']:.1f}°)"
        )

    # Decision
    if reasons:
        return "geodesic", "; ".join(reasons)
    else:
        return "planar", f"Local extent, moderate radius ({radius_m/1000:.1f} km), mid-latitude"


def create_geodesic_buffer_point(
    lon: float, lat: float, radius_m: float, num_points: int = 36
) -> Polygon:
    """
    Create a geodesic buffer around a point using pyproj.Geod.

    Args:
        lon: Longitude in degrees
        lat: Latitude in degrees
        radius_m: Buffer radius in meters
        num_points: Number of points to approximate circle (36 = 10° increments)

    Returns:
        Polygon representing geodesic buffer
    """
    geod = Geod(ellps="WGS84")

    # Generate points along geodesic circle
    circle_lons = []
    circle_lats = []

    for i in range(num_points):
        azimuth = (360.0 / num_points) * i
        # Calculate point at given azimuth and distance
        end_lon, end_lat, _ = geod.fwd(lon, lat, azimuth, radius_m)
        circle_lons.append(end_lon)
        circle_lats.append(end_lat)

    # Close the polygon
    circle_lons.append(circle_lons[0])
    circle_lats.append(circle_lats[0])

    # Create polygon
    coords = list(zip(circle_lons, circle_lats))
    return Polygon(coords)


def create_geodesic_buffer(gdf: gpd.GeoDataFrame, radius_m: float) -> gpd.GeoDataFrame:
    """
    Create geodesic buffers for Point and MultiPoint geometries.

    For other geometry types, logs warning and returns original gdf
    (falls back to planar buffering in caller).

    Args:
        gdf: GeoDataFrame in EPSG:4326
        radius_m: Buffer radius in meters

    Returns:
        GeoDataFrame with buffered geometries
    """
    # Determine resolution based on radius (more points for larger radii)
    if radius_m > 500000:  # >500 km
        num_points = 180  # 2° increments
    elif radius_m > 100000:  # >100 km
        num_points = 72  # 5° increments
    else:
        num_points = 36  # 10° increments

    buffered_geoms = []

    for geom in gdf.geometry:
        if isinstance(geom, Point):
            buffered = create_geodesic_buffer_point(geom.x, geom.y, radius_m, num_points)
            buffered_geoms.append(buffered)
        elif isinstance(geom, MultiPoint):
            # Buffer each point and union
            point_buffers = []
            for pt in geom.geoms:
                buffered = create_geodesic_buffer_point(pt.x, pt.y, radius_m, num_points)
                point_buffers.append(buffered)
            # Union all buffers
            if point_buffers:
                from shapely.ops import unary_union

                buffered_geoms.append(unary_union(point_buffers))
            else:
                buffered_geoms.append(geom)
        else:
            # For other geometries, log and keep original
            # Caller will fall back to planar
            logger.warning(
                f"Geodesic buffering not yet implemented for {geom.geom_type}, "
                "keeping original geometry"
            )
            buffered_geoms.append(geom)

    # Create new GeoDataFrame with buffered geometries
    result = gdf.copy()
    result["geometry"] = buffered_geoms
    return result


def op_buffer(
    layers,
    radius=10000,
    buffer_crs="EPSG:3857",
    radius_unit="meters",
    dissolve=False,
    auto_optimize_crs: bool = False,
    projection_metadata: bool = False,
    override_crs: str | None = None,
):
    """
    Buffers features of a single input layer item individually or dissolved.
    If multiple layers are provided, this function will raise a ValueError.
    Input geometries are assumed in EPSG:4326. This function:
      1) Expects `layers` to be a list containing a single layer item
         (FeatureCollection or Feature).
      2) Converts radius to meters based on radius_unit (default is "meters").
      3) Extracts features from the single layer item.
      4) Creates a GeoDataFrame from these features.
      5) Reprojects the GeoDataFrame to buffer_crs (default EPSG:3857,
         which uses meters).
      6) Applies buffer to each feature geometry with the meter-based radius.
      7) Optionally dissolves all buffered geometries into a single geometry
         if dissolve=True.
      8) Reprojects the GeoDataFrame (with buffered features) back to
         EPSG:4326.
      9) Returns a list containing one FeatureCollection with the individually
         buffered features (or single dissolved feature if dissolve=True).
    Supported radius_unit: "meters", "kilometers", "miles".
    """
    if not layers:
        logger.warning("op_buffer called with no layers")
        return []  # No input layer, return empty list

    if len(layers) > 1:
        # Extract layer names/titles if available for better error information
        layer_info = []
        for i, layer in enumerate(layers):
            name = None
            if isinstance(layer, dict):
                props = layer.get("properties", {})
                if props:
                    name = props.get("name") or props.get("title")
                # Also try to get name from features if it's a FeatureCollection
                if not name and layer.get("type") == "FeatureCollection" and layer.get("features"):
                    first_feat = layer["features"][0] if layer["features"] else None
                    if first_feat and isinstance(first_feat, dict):
                        props = first_feat.get("properties", {})
                        if props:
                            name = props.get("name") or props.get("title")
            layer_info.append("Layer {i+1}" + (": {name}" if name else ""))

        layer_desc = ", ".join(layer_info)
        raise ValueError(
            f"Buffer operation error: Only one layer can be buffered at a time. Received {len(layers)} layers: {layer_desc}. Please specify a single target layer."
        )

    layer_item = layers[0]  # Process the single layer provided
    unit = radius_unit.lower()
    factor = {"meters": 1.0, "kilometers": 1000.0, "miles": 1609.34}.get(unit)
    if factor is None:
        logger.warning(f"Unknown radius_unit '{radius_unit}', assuming meters")
        factor = 1.0

    actual_radius_meters = float(radius) * factor

    current_features = []
    if isinstance(layer_item, dict):
        if layer_item.get("type") == "FeatureCollection":
            current_features = layer_item.get("features", [])
        elif layer_item.get("type") == "Feature":
            current_features = [layer_item]

    if not current_features:
        # This case might occur if the single layer_item was an empty FeatureCollection or invalid
        print(
            "Warning: The provided layer item is empty or not a recognizable Feature/FeatureCollection: {type(layer_item)}"
        )
        return []

    # Ensure all features have 'properties' field (GeoJSON spec requirement)
    # This prevents KeyError when geopandas tries to access feature["properties"]
    for feature in current_features:
        if isinstance(feature, dict) and "properties" not in feature:
            feature["properties"] = {}

    try:
        gdf = gpd.GeoDataFrame.from_features(current_features)
        gdf.set_crs("EPSG:4326", inplace=True)

        # Compute bbox metrics for buffer method selection
        bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
        bbox = (bounds[0], bounds[1], bounds[2], bounds[3])
        bbox_metrics = compute_bbox_metrics(bbox)

        # Decide buffer method when auto_optimize_crs is enabled
        buffer_method = "planar"
        method_reason = "Default planar buffer"
        use_geodesic = False

        if auto_optimize_crs:
            buffer_method, method_reason = choose_buffer_method(
                gdf, actual_radius_meters, bbox_metrics
            )
            use_geodesic = buffer_method == "geodesic"
            logger.info(f"Buffer method selected: {buffer_method} ({method_reason})")

        # Execute buffering
        if use_geodesic:
            # Geodesic buffering (ellipsoid-based)
            logger.info("Applying geodesic buffer")
            gdf_buffered_individual = create_geodesic_buffer(gdf, actual_radius_meters)

            crs_info = {
                "epsg_code": "EPSG:4326",
                "crs_name": "WGS84 Geographic (geodesic buffer)",
                "selection_reason": "Geodesic buffer on ellipsoid",
                "auto_selected": True,
                "buffer_method": "geodesic",
                "buffer_method_reason": method_reason,
                "radius_m": actual_radius_meters,
            }
        else:
            # Planar buffering (projection-based)
            if auto_optimize_crs:
                gdf_reprojected, crs_info = prepare_gdf_for_operation(
                    gdf,
                    OperationType.BUFFER,
                    auto_optimize_crs=auto_optimize_crs,
                    override_crs=override_crs
                    or (None if buffer_crs == "EPSG:3857" else buffer_crs),
                )
            elif override_crs:
                # User specified a CRS explicitly
                gdf_reprojected = gdf.to_crs(override_crs)
                crs_info = {
                    "epsg_code": override_crs,
                    "selection_reason": "User-specified CRS",
                    "auto_selected": False,
                }
            else:
                # Use default buffer_crs
                gdf_reprojected = gdf.to_crs(buffer_crs)
                crs_info = {
                    "epsg_code": buffer_crs,
                    "selection_reason": "Default CRS",
                    "auto_selected": False,
                }

            # Add buffer metadata
            crs_info["buffer_method"] = "planar"
            crs_info["buffer_method_reason"] = method_reason
            crs_info["radius_m"] = actual_radius_meters

            # Apply planar buffer
            gdf_reprojected["geometry"] = gdf_reprojected.geometry.buffer(actual_radius_meters)

            # Reproject back to EPSG:4326
            gdf_buffered_individual = gdf_reprojected.to_crs("EPSG:4326")

        # If dissolve is True, merge all buffered geometries into one
        if dissolve:
            dissolved_geom = unary_union(gdf_buffered_individual.geometry)
            # Create a new GeoDataFrame with the dissolved geometry
            # Keep properties from the first feature
            props = {}
            if len(gdf.columns) > 1:
                for col in gdf.columns:
                    if col != "geometry":
                        props[col] = gdf[col].iloc[0]
            gdf_buffered_individual = gpd.GeoDataFrame(
                [props], geometry=[dissolved_geom], crs=gdf_buffered_individual.crs
            )

        if gdf_buffered_individual.empty:
            return []  # Resulting GeoDataFrame is empty

        fc = json.loads(gdf_buffered_individual.to_json())

        # Inject projection metadata if requested
        if projection_metadata and fc:
            # fc is a FeatureCollection dict
            if "properties" not in fc:
                fc["properties"] = {}
            fc["properties"]["_crs_metadata"] = crs_info

        return [fc]  # Return a list containing the single FeatureCollection
    except Exception as e:
        logger.exception(f"Error in op_buffer: {e}")
        return []
