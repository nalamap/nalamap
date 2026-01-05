from __future__ import annotations

import hashlib
from typing import Any, Dict, Tuple

from pyproj import CRS

# Note on approach:
# We generate deterministic, portable custom projections based on bbox:
# - Conformal: Lambert Conformal Conic 2SP (LCC)
# - Equal-area: Albers Equal Area Conic 2SP (AEA)
# - Polar equal-area: LAEA around pole
# - Polar conformal: Polar Stereographic
# We build PROJ strings with WGS84 ellipsoid and convert them to WKT via pyproj.


def _normalize_lon(lon: float) -> float:
    """Normalize longitude to [-180, 180]."""
    lon = ((lon + 180) % 360) - 180
    # Map -180 to 180 consistently
    if lon == -180:
        return 180.0
    return lon


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _center_lon_lat(bbox: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
    min_lon, min_lat, max_lon, max_lat = bbox
    # Handle antimeridian: if min > max, treat as crossing; shift longitudes
    if min_lon > max_lon:
        # unwrap by adding 360 to max_lon for mean computation
        c_lon = _normalize_lon((min_lon + (max_lon + 360.0)) / 2.0)
        lon_span = (max_lon + 360.0) - min_lon
    else:
        c_lon = (min_lon + max_lon) / 2.0
        lon_span = max_lon - min_lon
    c_lat = (min_lat + max_lat) / 2.0
    lat_span = max_lat - min_lat
    return c_lon, c_lat, lon_span, lat_span


def _compute_standard_parallels(lat0: float, lat_span: float) -> Tuple[float, float]:
    """
    Compute standard parallels symmetrically around lat0 using 1/3 of span,
    with clamping to avoid degenerate cases. Ensures |lat2-lat1| >= 8 deg.
    """
    delta = max(8.0, (lat_span / 3.0))
    lat1 = _clamp(lat0 - delta / 2.0, -75.0, 75.0)
    lat2 = _clamp(lat0 + delta / 2.0, -75.0, 75.0)
    if abs(lat2 - lat1) < 8.0:
        # enforce minimum separation
        mid = lat0
        lat1 = _clamp(mid - 4.0, -75.0, 75.0)
        lat2 = _clamp(mid + 4.0, -75.0, 75.0)
    # Ensure ordering
    if lat1 > lat2:
        lat1, lat2 = lat2, lat1
    return lat1, lat2


def _proj_to_wkt(proj_string: str) -> str:
    """Convert a PROJ string to WKT using pyproj."""
    crs = CRS.from_proj4(proj_string)
    return crs.to_wkt()


def build_lcc_wkt(bbox: Tuple[float, float, float, float]) -> Dict[str, Any]:
    """
    Build Lambert Conformal Conic (2SP) WKT for a bbox.
    Returns dict with wkt, name and params.
    """
    c_lon, c_lat, lon_span, lat_span = _center_lon_lat(bbox)
    lon0 = _normalize_lon(c_lon)
    lat0 = _clamp(c_lat, -75.0, 75.0)
    lat1, lat2 = _compute_standard_parallels(lat0, lat_span)
    name = "Custom LCC (WGS84)"
    proj = (
        f"+proj=lcc +lat_1={lat1} +lat_2={lat2} +lat_0={lat0} +lon_0={lon0} "
        f"+x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
    )
    wkt = _proj_to_wkt(proj)
    return {
        "wkt": wkt,
        "name": name,
        "params": {"lat_1": lat1, "lat_2": lat2, "lat_0": lat0, "lon_0": lon0},
    }


def build_albers_wkt(bbox: Tuple[float, float, float, float]) -> Dict[str, Any]:
    """
    Build Albers Equal Area Conic (2SP) WKT for a bbox.
    Returns dict with wkt, name and params.
    """
    c_lon, c_lat, lon_span, lat_span = _center_lon_lat(bbox)
    lon0 = _normalize_lon(c_lon)
    lat0 = _clamp(c_lat, -75.0, 75.0)
    lat1, lat2 = _compute_standard_parallels(lat0, lat_span)
    name = "Custom Albers (WGS84)"
    proj = (
        f"+proj=aea +lat_1={lat1} +lat_2={lat2} +lat_0={lat0} +lon_0={lon0} "
        f"+x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
    )
    wkt = _proj_to_wkt(proj)
    return {
        "wkt": wkt,
        "name": name,
        "params": {"lat_1": lat1, "lat_2": lat2, "lat_0": lat0, "lon_0": lon0},
    }


def build_laea_polar_wkt(is_arctic: bool) -> Dict[str, Any]:
    """
    Build Lambert Azimuthal Equal Area centered on the pole.
    """
    lat0 = 90.0 if is_arctic else -90.0
    lon0 = 0.0
    name = "Custom Polar LAEA (WGS84)"
    proj = f"+proj=laea +lat_0={lat0} +lon_0={lon0} +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
    wkt = _proj_to_wkt(proj)
    return {
        "wkt": wkt,
        "name": name,
        "params": {"lat_0": lat0, "lon_0": lon0},
    }


def build_polar_stere_wkt(is_arctic: bool) -> Dict[str, Any]:
    """
    Build Polar Stereographic centered on the pole (conformal).
    """
    lat0 = 90.0 if is_arctic else -90.0
    lon0 = 0.0
    name = "Custom Polar Stereographic (WGS84)"
    # standard Latitude of true scale near pole, use 70deg
    lat_ts = 70.0 if is_arctic else -70.0
    proj = (
        f"+proj=stere +lat_0={lat0} +lon_0={lon0} +lat_ts={lat_ts} "
        f"+x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
    )
    wkt = _proj_to_wkt(proj)
    return {
        "wkt": wkt,
        "name": name,
        "params": {"lat_0": lat0, "lon_0": lon0, "lat_ts": lat_ts},
    }


def hash_wkt(wkt: str) -> str:
    """Short stable hash for WKT fingerprints in metadata."""
    return hashlib.sha1(wkt.encode("utf-8")).hexdigest()[:10]
