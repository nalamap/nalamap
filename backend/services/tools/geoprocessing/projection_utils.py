"""
Intelligent planar CRS selection for geoprocessing operations.

Implements deterministic, rule-based projection selection to automatically
choose optimal planar projections for geoprocessing operations. The system
provides excellent accuracy (<1% error) for the vast majority of use cases.

Selection factors:
- Geographic extent (local/regional/global)
- Operation type (area/distance/topology)
- Latitude zone (equatorial/mid-latitude/polar)
- Orientation (EW vs NS dominant)
- UTM zone boundaries
- Antimeridian crossing

Key functions:
- get_optimal_crs_for_bbox(bbox, operation_type) - Main entry point
- decide_projection(bbox, operation_type, ...) - Core decision algorithm
- prepare_gdf_for_operation(gdf, operation_type, ...) - Apply optimal projection
- validate_crs(epsg_code) - Verify CRS validity
- compute_bbox_metrics(bbox) - Helper for extent analysis

Accuracy expectations:
- Local operations (<6° extent): <0.1% error
- Regional operations (6-30° extent): 0.5-1% error
- Polar regions (>80° latitude): 1-3% error (acceptable for most applications)
- Trans-oceanic spans: 2-5% error (inherent limitation of planar projections)

"""

import logging
import math
from typing import Tuple, Optional, Dict, Any, List
from enum import Enum

from pyproj import CRS
from services.tools.geoprocessing.wkt_factory import (
    build_lcc_wkt,
    build_albers_wkt,
    build_laea_polar_wkt,
    build_polar_stere_wkt,
    hash_wkt,
)

logger = logging.getLogger(__name__)


class ProjectionProperty(Enum):
    """Geometric properties of map projections."""

    CONFORMAL = "conformal"
    EQUAL_AREA = "equal-area"
    EQUIDISTANT = "equidistant"
    COMPROMISE = "compromise"


class OperationType(Enum):
    """Types of geoprocessing operations."""

    AREA = "area"
    BUFFER = "buffer"
    OVERLAY = "overlay"
    CLIP = "clip"
    DISSOLVE = "dissolve"
    SIMPLIFY = "simplify"
    SJOIN = "sjoin"
    SJOIN_NEAREST = "sjoin_nearest"


# Whitelist of validated EPSG codes and friendly names
VALIDATED_CRS = {
    # UTM Zones North (EPSG:32601-32660)
    **{f"326{str(i).zfill(2)}": f"UTM Zone {i}N" for i in range(1, 61)},
    # UTM Zones South (EPSG:32701-32760)
    **{f"327{str(i).zfill(2)}": f"UTM Zone {i}S" for i in range(1, 61)},
    # Selected regional EPSG (kept for name mapping if ever referenced)
    "3035": "Europe LAEA (ETRS89)",
    "3577": "Australia Albers",
    "3034": "Europe LCC (ETRS89)",
    "3112": "Australia Lambert Conformal Conic",
    # Polar Projections
    "3995": "Arctic Polar Stereographic",
    "3031": "Antarctic Polar Stereographic",
    "3571": "North Pole LAEA",
    "3572": "Antarctica LAEA",
    # Fallback
    "3857": "Web Mercator (fallback)",
    "4326": "WGS84 Geographic",
}


# Regional boundaries for projection selection (coarse)
REGIONAL_BOUNDARIES = {
    "north_america": {"min_lon": -180, "max_lon": -30, "min_lat": 15, "max_lat": 85},
    "south_america": {"min_lon": -90, "max_lon": -30, "min_lat": -60, "max_lat": 15},
    "europe": {"min_lon": -30, "max_lon": 60, "min_lat": 35, "max_lat": 75},
    "africa": {"min_lon": -30, "max_lon": 60, "min_lat": -40, "max_lat": 40},
    "asia": {"min_lon": 60, "max_lon": 150, "min_lat": 0, "max_lat": 80},
    "australia": {"min_lon": 110, "max_lon": 160, "min_lat": -50, "max_lat": -10},
}


# ========== Helper Functions for Bbox Analysis ==========


def km_per_degree_lon(lat: float) -> float:
    """
    Calculate km per degree of longitude at given latitude.

    At equator: ~111 km/degree
    At poles: ~0 km/degree
    """
    return 111.32 * math.cos(math.radians(lat))


def km_per_degree_lat() -> float:
    """
    Calculate km per degree of latitude (constant).

    Returns ~111 km/degree
    """
    return 111.32


def compute_utm_zone(lon: float) -> int:
    """Compute UTM zone number from longitude."""
    zone = int((lon + 180) / 6) + 1
    return min(max(zone, 1), 60)


def compute_zone_span(min_lon: float, max_lon: float) -> int:
    """
    Calculate how many UTM zones are spanned by longitude extent.

    Returns:
        Number of distinct zones (1 means single zone, 2+ means crossing)
    """
    if min_lon > max_lon:  # Antimeridian crossing
        # Approximate: treat as large span
        return 10

    min_zone = compute_utm_zone(min_lon)
    max_zone = compute_utm_zone(max_lon)
    return abs(max_zone - min_zone) + 1


def is_antimeridian_crossing(min_lon: float, max_lon: float) -> bool:
    """
    Check if bounding box crosses the antimeridian (±180°).

    Returns:
        True if crossing detected
    """
    return min_lon > max_lon


def compute_bbox_metrics(bbox: Tuple[float, float, float, float]) -> Dict[str, Any]:
    """
    Compute comprehensive metrics for bbox to guide CRS selection.

    Args:
        bbox: (min_lon, min_lat, max_lon, max_lat) in EPSG:4326

    Returns:
        Dict with:
        - center_lon, center_lat
        - lon_extent, lat_extent (degrees)
        - lon_extent_km, lat_extent_km (approximate)
        - area_km2 (approximate)
        - orientation_ratio (EW/NS; >1 means EW-dominant)
        - zone_span (number of UTM zones)
        - centroid_zone (UTM zone at centroid)
        - is_polar (|center_lat| >= 80)
        - is_near_equator (|center_lat| <= 10)
        - antimeridian_crossing (bool)
    """
    min_lon, min_lat, max_lon, max_lat = bbox

    # Handle antimeridian crossing
    antimeridian = is_antimeridian_crossing(min_lon, max_lon)

    # Compute center
    if antimeridian:
        # Wrap-around logic
        center_lon = ((min_lon + max_lon + 360) / 2) % 360
        if center_lon > 180:
            center_lon -= 360
        lon_extent = (360 - min_lon) + max_lon
    else:
        center_lon = (min_lon + max_lon) / 2
        lon_extent = max_lon - min_lon

    center_lat = (min_lat + max_lat) / 2
    lat_extent = max_lat - min_lat

    # Compute extents in km (approximate)
    lat_extent_km = lat_extent * km_per_degree_lat()
    # Use average latitude for lon calculation
    avg_lat = center_lat
    lon_extent_km = lon_extent * km_per_degree_lon(avg_lat)

    # Approximate area
    area_km2 = lat_extent_km * lon_extent_km

    # Orientation ratio (EW / NS)
    orientation_ratio = lon_extent_km / max(lat_extent_km, 1.0)

    # UTM zone analysis
    zone_span = compute_zone_span(min_lon, max_lon)
    centroid_zone = compute_utm_zone(center_lon)

    # Latitude classification
    is_polar = abs(center_lat) >= 80 or max_lat > 85 or min_lat < -85
    is_near_equator = abs(center_lat) <= 10

    return {
        "center_lon": center_lon,
        "center_lat": center_lat,
        "lon_extent": lon_extent,
        "lat_extent": lat_extent,
        "lon_extent_km": lon_extent_km,
        "lat_extent_km": lat_extent_km,
        "area_km2": area_km2,
        "orientation_ratio": orientation_ratio,
        "zone_span": zone_span,
        "centroid_zone": centroid_zone,
        "is_polar": is_polar,
        "is_near_equator": is_near_equator,
        "antimeridian_crossing": antimeridian,
    }


# ========== Main Decision Algorithm ==========


def decide_projection(
    bbox: Tuple[float, float, float, float],
    operation_type: OperationType,
    projection_priority: Optional[ProjectionProperty] = None,
    fallback_crs: str = "EPSG:3857",
) -> Dict[str, Any]:
    """
    Multi-factor CRS decision algorithm with full transparency.

    Implements hybrid heuristic considering:
    - Latitude (polar, equatorial, mid-latitude)
    - Longitude span (UTM zone boundaries)
    - Orientation (EW vs NS dominant)
    - Size/extent
    - Operation type requirements

    Args:
        bbox: (min_lon, min_lat, max_lon, max_lat) in EPSG:4326
        operation_type: Type of geoprocessing operation
        projection_priority: Override projection property
        fallback_crs: Fallback if no optimal CRS found

    Returns:
        Dict with:
        - epsg_code
        - crs_name
        - selection_reason
        - auto_selected
        - decision_path (list of decision steps taken)
        - decision_inputs (metrics used in decision)
    """
    decision_path = []
    min_lon, min_lat, max_lon, max_lat = bbox

    # Step 1: Validate bbox
    if not (
        -180 <= min_lon <= 180
        and -90 <= min_lat <= 90
        and -180 <= max_lon <= 180
        and -90 <= max_lat <= 90
    ):
        decision_path.append("Invalid bbox coordinates")
        return _create_response_with_metadata(
            fallback_crs, "Invalid bounding box", decision_path, {}
        )

    # Compute comprehensive metrics
    metrics = compute_bbox_metrics(bbox)
    decision_path.append(
        f"Computed bbox metrics: center=({metrics['center_lon']:.2f}, {metrics['center_lat']:.2f})"
    )

    # Determine required projection property
    if projection_priority:
        required_property = projection_priority
        decision_path.append(f"User override: property={required_property.value}")
    else:
        required_property = _get_required_property(operation_type)
        decision_path.append(
            f"Operation {operation_type.value} requires property={required_property.value}"
        )

    # Store inputs for metadata
    decision_inputs = {
        "bbox": bbox,
        "centroid": (metrics["center_lon"], metrics["center_lat"]),
        "extents_deg": (metrics["lon_extent"], metrics["lat_extent"]),
        "extents_km": (metrics["lon_extent_km"], metrics["lat_extent_km"]),
        "area_km2": metrics["area_km2"],
        "orientation_ratio": metrics["orientation_ratio"],
        "zone_span": metrics["zone_span"],
        "operation_type": operation_type.value,
        "required_property": required_property.value,
    }

    # Step 2: Check for global/near-global extent
    if metrics["lon_extent"] >= 180 or metrics["lat_extent"] >= 170:
        decision_path.append(
            f"Near-global extent: {metrics['lon_extent']:.1f}° × {metrics['lat_extent']:.1f}°"
        )
        return _create_response_with_metadata(
            fallback_crs,
            f"Extent too large ({metrics['lon_extent']:.1f}° × {metrics['lat_extent']:.1f}°)",
            decision_path,
            decision_inputs,
        )

    # Step 3: Check for polar regions
    if metrics["is_polar"]:
        decision_path.append(f"Polar region detected: center_lat={metrics['center_lat']:.1f}°")
        result = _get_polar_custom(metrics["center_lat"], required_property)
        result["decision_path"] = decision_path
        result["decision_inputs"] = decision_inputs
        return result

    # Step 4: Local extent - consider UTM (with zone seam check)
    if metrics["lon_extent"] <= 6 and metrics["lat_extent"] <= 6:
        decision_path.append(
            f"Local extent: {metrics['lon_extent']:.1f}° × {metrics['lat_extent']:.1f}°"
        )

        # Check if we're crossing UTM zone boundary
        if metrics["zone_span"] >= 2 and metrics["lon_extent"] >= 3:
            decision_path.append(
                f"Crossing UTM zone seam: span={metrics['zone_span']} zones, skipping UTM"
            )
            # Fall through to regional selection
        else:
            decision_path.append(f"Using UTM zone {metrics['centroid_zone']}")
            result = _get_utm_crs(metrics["center_lon"], metrics["center_lat"])
            result["decision_path"] = decision_path
            result["decision_inputs"] = decision_inputs
            return result

    # Step 5: Regional extent - check orientation and operation requirements
    region = _identify_region(bbox)

    if region:
        decision_path.append(f"Region identified: {region}")

        # Check for EW-dominant orientation
        if metrics["orientation_ratio"] >= 1.5:
            decision_path.append(
                f"EW-dominant orientation: ratio={metrics['orientation_ratio']:.2f}, prefer LCC"
            )
            # Force conformal (LCC) for wide EW strips
            result = _get_regional_crs(region, ProjectionProperty.CONFORMAL, bbox)
            result["decision_path"] = decision_path
            result["decision_inputs"] = decision_inputs
            return result

        # Check for large area requiring equal-area
        if metrics["area_km2"] >= 2e6:
            decision_path.append(f"Large area: {metrics['area_km2']:.0f} km², prefer equal-area")
            result = _get_regional_crs(region, ProjectionProperty.EQUAL_AREA, bbox)
            result["decision_path"] = decision_path
            result["decision_inputs"] = decision_inputs
            return result

        # Use operation-appropriate projection
        decision_path.append("Using operation-appropriate projection for region")
        result = _get_regional_crs(region, required_property, bbox)
        result["decision_path"] = decision_path
        result["decision_inputs"] = decision_inputs
        return result

    # Step 6: Multi-zone or antimeridian crossing
    if metrics["antimeridian_crossing"]:
        decision_path.append("Antimeridian crossing detected")

    if metrics["zone_span"] >= 3:
        decision_path.append(f"Scattered across {metrics['zone_span']} UTM zones")

    # Final fallback
    decision_path.append("Using fallback projection")
    return _create_response_with_metadata(
        fallback_crs,
        f"Cross-regional extent ({metrics['lon_extent']:.1f}° × {metrics['lat_extent']:.1f}°)",
        decision_path,
        decision_inputs,
    )


def _create_response_with_metadata(
    epsg_code: str,
    reason: str,
    decision_path: List[str],
    decision_inputs: Dict[str, Any],
) -> Dict[str, Any]:
    """Create CRS response with full metadata."""
    # Extract code number from EPSG: or ESRI: prefix
    code_number = epsg_code.replace("EPSG:", "").replace("ESRI:", "")
    return {
        "epsg_code": epsg_code,
        "crs_name": VALIDATED_CRS.get(code_number, "Custom CRS"),
        "selection_reason": reason,
        "auto_selected": True,
        "decision_path": decision_path,
        "decision_inputs": decision_inputs,
    }


def get_optimal_crs_for_bbox(
    bbox: Tuple[float, float, float, float],
    operation_type: OperationType,
    auto_optimize: bool = True,
    projection_priority: Optional[ProjectionProperty] = None,
    fallback_crs: str = "EPSG:3857",
) -> Dict[str, Any]:
    """
    Select optimal CRS for given bounding box and operation.

    This is the main entry point for CRS selection. Uses the enhanced
    decide_projection algorithm when auto_optimize=True.

    Args:
        bbox: (min_lon, min_lat, max_lon, max_lat) in EPSG:4326
        operation_type: Type of geoprocessing operation
        auto_optimize: If False, return fallback_crs
        projection_priority: Override projection property selection
        fallback_crs: CRS to use if selection fails

    Returns:
        Dict with epsg_code, crs_name, selection_reason, auto_selected,
        decision_path, decision_inputs
    """

    if not auto_optimize:
        # Extract code number from EPSG: or ESRI: prefix
        code_number = fallback_crs.replace("EPSG:", "").replace("ESRI:", "")
        return {
            "epsg_code": fallback_crs,
            "crs_name": VALIDATED_CRS.get(code_number, "Custom CRS"),
            "selection_reason": "Auto-optimization disabled",
            "auto_selected": False,
            "decision_path": ["Auto-optimization disabled by user"],
            "decision_inputs": {},
        }

    # Use the enhanced decision algorithm
    return decide_projection(bbox, operation_type, projection_priority, fallback_crs)


def _get_required_property(operation_type: OperationType) -> ProjectionProperty:
    """Determine required projection property for operation."""
    property_map = {
        OperationType.AREA: ProjectionProperty.EQUAL_AREA,
        OperationType.BUFFER: ProjectionProperty.CONFORMAL,
        OperationType.OVERLAY: ProjectionProperty.CONFORMAL,
        OperationType.CLIP: ProjectionProperty.CONFORMAL,
        OperationType.DISSOLVE: ProjectionProperty.EQUAL_AREA,
        OperationType.SIMPLIFY: ProjectionProperty.CONFORMAL,
        OperationType.SJOIN: ProjectionProperty.COMPROMISE,
        OperationType.SJOIN_NEAREST: ProjectionProperty.EQUIDISTANT,
    }
    return property_map.get(operation_type, ProjectionProperty.COMPROMISE)


def _get_utm_crs(center_lon: float, center_lat: float) -> Dict[str, Any]:
    """Calculate appropriate UTM zone for location."""
    zone = int((center_lon + 180) / 6) + 1
    zone = min(max(zone, 1), 60)

    if center_lat >= 0:
        epsg_code = f"EPSG:326{str(zone).zfill(2)}"
        hemisphere = "N"
    else:
        epsg_code = f"EPSG:327{str(zone).zfill(2)}"
        hemisphere = "S"

    return {
        "epsg_code": epsg_code,
        "crs_name": f"WGS 84 / UTM zone {zone}{hemisphere}",
        "selection_reason": f"Local extent - UTM zone {zone}{hemisphere}",
        "auto_selected": True,
    }


def _get_polar_custom(center_lat: float, required_property: ProjectionProperty) -> Dict[str, Any]:
    """Get appropriate polar custom WKT projection."""
    is_arctic = center_lat > 0
    if required_property == ProjectionProperty.EQUAL_AREA:
        info = build_laea_polar_wkt(is_arctic=is_arctic)
        reason = "Polar region - LAEA preserves areas"
    else:
        info = build_polar_stere_wkt(is_arctic=is_arctic)
        reason = "Polar region - Stereographic preserves shapes"
    digest = hash_wkt(info["wkt"])
    return {
        "authority": "WKT",
        "wkt": info["wkt"],
        "crs_name": info["name"],
        "selection_reason": reason,
        "wkt_hash": digest,
        "wkt_params": info.get("params", {}),
        "auto_selected": True,
    }


def _identify_region(bbox: Tuple[float, float, float, float]) -> Optional[str]:
    """Identify which predefined region bbox falls within."""
    min_lon, min_lat, max_lon, max_lat = bbox

    for region_name, bounds in REGIONAL_BOUNDARIES.items():
        if (
            bounds["min_lon"] <= min_lon <= bounds["max_lon"]
            and bounds["min_lon"] <= max_lon <= bounds["max_lon"]
            and bounds["min_lat"] <= min_lat <= bounds["max_lat"]
            and bounds["min_lat"] <= max_lat <= bounds["max_lat"]
        ):
            return region_name

    return None


def _get_regional_crs(
    region: str, required_property: ProjectionProperty, bbox: Tuple[float, float, float, float]
) -> Dict[str, Any]:
    """Get appropriate regional projection as WKT (consistency across regions)."""
    if required_property == ProjectionProperty.EQUAL_AREA:
        info = build_albers_wkt(bbox)
        reason = f"Regional extent ({region}) - Custom Albers optimized for region"
    else:
        info = build_lcc_wkt(bbox)
        reason = f"Regional extent ({region}) - Custom LCC optimized for region"
    digest = hash_wkt(info["wkt"])
    return {
        "authority": "WKT",
        "wkt": info["wkt"],
        "crs_name": info["name"],
        "selection_reason": reason,
        "wkt_hash": digest,
        "wkt_params": info.get("params", {}),
        "auto_selected": True,
    }


def _create_fallback_response(
    fallback_crs: str,
    reason: str,
    decision_path: Optional[List[str]] = None,
    decision_inputs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create fallback CRS response (backwards compatible)."""
    # Extract code number from EPSG: or ESRI: prefix
    code_number = fallback_crs.replace("EPSG:", "").replace("ESRI:", "")
    response = {
        "epsg_code": fallback_crs,
        "crs_name": VALIDATED_CRS.get(code_number, "Custom CRS"),
        "selection_reason": reason,
        "auto_selected": True,
    }

    # Add optional metadata fields if provided
    if decision_path is not None:
        response["decision_path"] = decision_path
    if decision_inputs is not None:
        response["decision_inputs"] = decision_inputs

    return response


def validate_crs(epsg_code: str) -> bool:
    """Validate that CRS exists and is usable."""
    try:
        crs = CRS.from_string(epsg_code)
        return crs is not None
    except Exception as e:
        logger.warning(f"Invalid CRS {epsg_code}: {e}")
        return False


def prepare_gdf_for_operation(
    gdf,
    operation_type: OperationType,
    auto_optimize_crs: bool = True,
    override_crs: Optional[str] = None,
    **kwargs,
):
    """
    Prepare GeoDataFrame with optimal CRS for operation.

    Returns tuple (transformed_gdf, crs_info)
    """
    # geopandas is not required to be imported here; assume caller provides a GeoDataFrame

    # Manual override takes precedence
    if override_crs:
        if validate_crs(override_crs):
            gdf_transformed = gdf.to_crs(override_crs)
            return gdf_transformed, {
                "epsg_code": override_crs,
                "crs_name": "User-specified CRS",
                "selection_reason": "Manual override",
                "auto_selected": False,
            }
        else:
            logger.warning(f"Invalid override CRS {override_crs}, using auto-selection")

    # Ensure GeoDataFrame is in WGS84 for bbox calculation
    try:
        if gdf.crs and str(gdf.crs) != "EPSG:4326":
            gdf_wgs84 = gdf.to_crs("EPSG:4326")
        else:
            gdf_wgs84 = gdf
    except Exception:
        # If conversion fails, assume input coords are lat/lon
        gdf_wgs84 = gdf

    bounds = gdf_wgs84.total_bounds  # [minx, miny, maxx, maxy]
    bbox = (bounds[0], bounds[1], bounds[2], bounds[3])

    crs_info = get_optimal_crs_for_bbox(
        bbox, operation_type, auto_optimize=auto_optimize_crs, **kwargs
    )

    # Determine target CRS
    target_crs_obj = None
    if "wkt" in crs_info and isinstance(crs_info.get("wkt"), str) and crs_info["wkt"]:
        try:
            target_crs_obj = CRS.from_wkt(crs_info["wkt"])
        except Exception as e:
            logger.warning(f"Selected WKT CRS failed to parse: {e}; falling back to EPSG:3857")
            crs_info = _create_fallback_response("EPSG:3857", "Selected CRS invalid")
    else:
        # Validate selected CRS, fallback if invalid
        selected_epsg_raw = crs_info.get("epsg_code")
        if not isinstance(selected_epsg_raw, str) or not selected_epsg_raw:
            logger.warning(f"Selected CRS {selected_epsg_raw!r} invalid, falling back to EPSG:3857")
            crs_info = _create_fallback_response("EPSG:3857", "Selected CRS invalid")
        else:
            selected_epsg = selected_epsg_raw
            if not validate_crs(selected_epsg):
                logger.warning(
                    f"Selected CRS {selected_epsg} failed validation, falling back to EPSG:3857"
                )
                crs_info = _create_fallback_response("EPSG:3857", "Selected CRS invalid")

    # Perform transformation
    try:
        if target_crs_obj is not None:
            gdf_transformed = gdf.to_crs(target_crs_obj)
        else:
            gdf_transformed = gdf.to_crs(crs_info["epsg_code"])
    except Exception as e:
        logger.warning("Failed to transform to target CRS: %s; using original gdf", e)
        gdf_transformed = gdf

    crs_info["auto_selected"] = auto_optimize_crs
    return gdf_transformed, crs_info
