"""
Intelligent CRS selection for geoprocessing operations.

Implements deterministic, rule-based projection selection based on:
- Geographic extent (local/regional/global)
- Operation type (area/distance/topology)
- Latitude zone (equatorial/mid-latitude/polar)

This module provides:
- get_optimal_crs_for_bbox(bbox, operation_type)
- prepare_gdf_for_operation(gdf, operation_type, ...)
- validate_crs(epsg_code)

"""

import logging
from typing import Tuple, Optional, Dict, Any
from enum import Enum

from pyproj import CRS

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
    # Regional Equal-Area / Albers-like (note: many are ESRI codes; mapped by string)
    "102003": "USA Contiguous Albers Equal Area",
    "102008": "North America Albers Equal Area",
    "102011": "South America Albers Equal Area",
    "3035": "Europe LAEA (ETRS89)",
    "102022": "Africa Albers Equal Area",
    "102028": "Asia South Albers Equal Area",
    "3577": "Australia Albers",
    # Regional Conformal
    "102004": "USA Contiguous Lambert Conformal Conic",
    "102009": "North America Lambert Conformal Conic",
    "32040": "South America Lambert Conformal Conic",
    "3034": "Europe LCC (ETRS89)",
    "102024": "Africa Lambert Conformal Conic",
    "102027": "Asia North Lambert Conformal Conic",
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


def get_optimal_crs_for_bbox(
    bbox: Tuple[float, float, float, float],
    operation_type: OperationType,
    auto_optimize: bool = True,
    projection_priority: Optional[ProjectionProperty] = None,
    fallback_crs: str = "EPSG:3857",
) -> Dict[str, Any]:
    """
    Select optimal CRS for given bounding box and operation.

    Args:
        bbox: (min_lon, min_lat, max_lon, max_lat) in EPSG:4326
        operation_type: Type of geoprocessing operation
        auto_optimize: If False, return fallback_crs
        projection_priority: Override projection property selection
        fallback_crs: CRS to use if selection fails

    Returns:
        Dict with epsg_code, crs_name, projection_property, selection_reason, expected_error
    """

    if not auto_optimize:
        return {
            "epsg_code": fallback_crs,
            "crs_name": VALIDATED_CRS.get(fallback_crs.replace("EPSG:", ""), "Custom CRS"),
            "projection_property": "unknown",
            "selection_reason": "Auto-optimization disabled",
            "expected_error": None,
        }

    # Validate bbox
    min_lon, min_lat, max_lon, max_lat = bbox
    if not (
        -180 <= min_lon <= 180
        and -90 <= min_lat <= 90
        and -180 <= max_lon <= 180
        and -90 <= max_lat <= 90
    ):
        logger.warning(f"Invalid bbox: {bbox}, using fallback")
        return _create_fallback_response(fallback_crs, "Invalid bounding box")

    # Calculate extent metrics
    lon_extent = max_lon - min_lon
    lat_extent = max_lat - min_lat
    center_lon = (min_lon + max_lon) / 2
    center_lat = (min_lat + max_lat) / 2

    # Determine required projection property
    if projection_priority:
        required_property = projection_priority
    else:
        required_property = _get_required_property(operation_type)

    # 1. If extent is extremely large (global or near-global) -> fallback
    # This prevents misclassification as 'polar' when the bbox spans the globe.
    if lon_extent >= 180 or lat_extent >= 170:
        return _create_fallback_response(
            fallback_crs,
            f"Extent too large ({lon_extent:.1f}° × {lat_extent:.1f}°), using fallback",
        )

    # 2. Check for polar regions (>80° latitude)
    if abs(center_lat) > 80 or max_lat > 85 or min_lat < -85:
        return _get_polar_crs(center_lat, required_property)

    # 2. Check for local extent (<6° in both dimensions) -> UTM
    if abs(lon_extent) <= 6 and abs(lat_extent) <= 6:
        return _get_utm_crs(center_lon, center_lat)

    # 3. Check for regional extent -> Continental projections
    region = _identify_region(bbox)
    if region:
        return _get_regional_crs(region, required_property)

    # 4. Fallback for cross-regional or global extents
    return _create_fallback_response(
        fallback_crs, f"Extent too large ({lon_extent:.1f}° × {lat_extent:.1f}°), using fallback"
    )


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
        "projection_property": "conformal",
        "selection_reason": (
            f"Local extent - UTM zone {zone}{hemisphere}; " "<0.1% distance error"
        ),
        "expected_error": 0.1,
    }


def _get_polar_crs(center_lat: float, required_property: ProjectionProperty) -> Dict[str, Any]:
    """Get appropriate polar projection."""
    is_arctic = center_lat > 0

    if required_property == ProjectionProperty.EQUAL_AREA:
        if is_arctic:
            return {
                "epsg_code": "EPSG:3571",
                "crs_name": "North Pole Lambert Azimuthal Equal Area",
                "projection_property": "equal-area",
                "selection_reason": "Arctic region - LAEA preserves areas",
                "expected_error": 0.0,
            }
        else:
            return {
                "epsg_code": "EPSG:3572",
                "crs_name": "Antarctica Lambert Azimuthal Equal Area",
                "projection_property": "equal-area",
                "selection_reason": "Antarctic region - LAEA preserves areas",
                "expected_error": 0.0,
            }
    else:
        if is_arctic:
            return {
                "epsg_code": "EPSG:3995",
                "crs_name": "Arctic Polar Stereographic",
                "projection_property": "conformal",
                "selection_reason": "Arctic region - Stereographic preserves shapes",
                "expected_error": 2.0,
            }
        else:
            return {
                "epsg_code": "EPSG:3031",
                "crs_name": "Antarctic Polar Stereographic",
                "projection_property": "conformal",
                "selection_reason": "Antarctic region - Stereographic preserves shapes",
                "expected_error": 2.0,
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


def _get_regional_crs(region: str, required_property: ProjectionProperty) -> Dict[str, Any]:
    """Get appropriate regional projection."""
    regional_crs = {
        "north_america": {
            ProjectionProperty.EQUAL_AREA: ("EPSG:102008", "North America Albers Equal Area", 0.5),
            ProjectionProperty.CONFORMAL: (
                "EPSG:102009",
                "North America Lambert Conformal Conic",
                1.0,
            ),
        },
        "south_america": {
            ProjectionProperty.EQUAL_AREA: ("EPSG:102011", "South America Albers Equal Area", 0.5),
            ProjectionProperty.CONFORMAL: (
                "EPSG:32040",
                "South America Lambert Conformal Conic",
                1.0,
            ),
        },
        "europe": {
            ProjectionProperty.EQUAL_AREA: ("EPSG:3035", "Europe LAEA (ETRS89)", 0.5),
            ProjectionProperty.CONFORMAL: ("EPSG:3034", "Europe LCC (ETRS89)", 1.0),
        },
        "africa": {
            ProjectionProperty.EQUAL_AREA: ("EPSG:102022", "Africa Albers Equal Area", 0.5),
            ProjectionProperty.CONFORMAL: ("EPSG:102024", "Africa Lambert Conformal Conic", 1.0),
        },
        "asia": {
            ProjectionProperty.EQUAL_AREA: ("EPSG:102028", "Asia South Albers Equal Area", 0.5),
            ProjectionProperty.CONFORMAL: (
                "EPSG:102027",
                "Asia North Lambert Conformal Conic",
                1.0,
            ),
        },
        "australia": {
            ProjectionProperty.EQUAL_AREA: ("EPSG:3577", "Australia Albers", 0.5),
            ProjectionProperty.CONFORMAL: ("EPSG:3112", "Australia Lambert Conformal Conic", 1.0),
        },
    }

    region_projections = regional_crs.get(region, {})
    if required_property in region_projections:
        epsg_code, crs_name, error = region_projections[required_property]
    else:
        epsg_code, crs_name, error = region_projections.get(
            ProjectionProperty.EQUAL_AREA, ("EPSG:3857", "Web Mercator (fallback)", 10.0)
        )

    return {
        "epsg_code": epsg_code,
        "crs_name": crs_name,
        "projection_property": required_property.value,
        "selection_reason": f"Regional extent ({region}) - {crs_name} optimized for region",
        "expected_error": error,
    }


def _create_fallback_response(fallback_crs: str, reason: str) -> Dict[str, Any]:
    """Create fallback CRS response."""
    return {
        "epsg_code": fallback_crs,
        "crs_name": VALIDATED_CRS.get(fallback_crs.replace("EPSG:", ""), "Custom CRS"),
        "projection_property": "compromise",
        "selection_reason": reason,
        "expected_error": 10.0 if "3857" in fallback_crs else None,
    }


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
                "projection_property": "unknown",
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

    # Validate selected CRS, fallback if invalid
    selected_epsg_raw = crs_info.get("epsg_code")
    # Normalize and validate selected CRS; fallback if missing or invalid
    if not isinstance(selected_epsg_raw, str) or not selected_epsg_raw:
        logger.warning(f"Selected CRS {selected_epsg_raw!r} invalid, falling back to EPSG:3857")
        crs_info = _create_fallback_response("EPSG:3857", "Selected CRS invalid")
        selected_epsg = crs_info["epsg_code"]
    else:
        selected_epsg = selected_epsg_raw
        if not validate_crs(selected_epsg):
            logger.warning(
                f"Selected CRS {selected_epsg} failed validation, falling back to EPSG:3857"
            )
            crs_info = _create_fallback_response("EPSG:3857", "Selected CRS invalid")
            selected_epsg = crs_info["epsg_code"]

    # Perform transformation
    try:
        gdf_transformed = gdf.to_crs(selected_epsg)
    except Exception as e:
        logger.warning(f"Failed to transform to {selected_epsg}: {e}; using original gdf")
        gdf_transformed = gdf

    crs_info["auto_selected"] = auto_optimize_crs
    return gdf_transformed, crs_info
