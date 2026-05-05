"""
Overpass API Module - Modular architecture for OSM data retrieval.

This module provides a clean, modular interface for querying the Overpass API,
converting OSM elements to GeoJSON, and building Overpass QL queries.

Components:
- OverpassClient: HTTP client for Overpass API with error handling
- OverpassQueryBuilder: Builds Overpass QL queries for various search types
- OverpassResultConverter: Converts OSM elements to GeoJSON features
"""

import hashlib
import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests

from models.geodata import DataOrigin, DataType, GeoDataObject
from services.storage.file_management import store_file

from .constants import get_geometry_display_label

logger = logging.getLogger(__name__)

# Default headers for Overpass API requests
OVERPASS_HEADERS = {
    "User-Agent": "NaLaMap, github.com/nalamap, next generation geospatial analysis using agents",
    "Content-Type": "application/x-www-form-urlencoded",
}

# Default Overpass API endpoint
OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"


@dataclass
class OverpassLocation:
    """Represents a geocoded location for Overpass queries."""

    display_name: str
    osm_relation_id: Optional[int] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    bbox: Optional[Tuple[float, float, float, float]] = None  # (south, west, north, east)

    @property
    def has_area(self) -> bool:
        """Check if location has an OSM relation ID for area-based queries."""
        return self.osm_relation_id is not None

    @property
    def has_bbox(self) -> bool:
        """Check if location has a bounding box."""
        return self.bbox is not None

    @property
    def has_point(self) -> bool:
        """Check if location has lat/lon coordinates."""
        return self.lat is not None and self.lon is not None


class OverpassClient:
    """HTTP client for Overpass API with error handling and retry logic."""

    def __init__(
        self,
        api_url: str = OVERPASS_API_URL,
        headers: Optional[Dict[str, str]] = None,
    ):
        self.api_url = api_url
        self.headers = headers or OVERPASS_HEADERS

    def execute_query(
        self, query: str, timeout: int = 300
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Execute an Overpass QL query.

        Args:
            query: The Overpass QL query string
            timeout: Request timeout in seconds

        Returns:
            Tuple of (response_data, error_message)
            - If successful: (data_dict, None)
            - If failed: (None, error_message)
        """
        try:
            response = requests.post(
                self.api_url,
                data={"data": query},
                headers=self.headers,
                timeout=timeout + 10,  # Allow slightly more time than query timeout
            )
            response.raise_for_status()
            return response.json(), None

        except requests.exceptions.Timeout:
            return None, f"Overpass API query timed out after {timeout} seconds."

        except requests.exceptions.HTTPError as e:
            error_detail = e.response.text[:500] if e.response else str(e)
            status_code = e.response.status_code if e.response else "N/A"

            if "runtime error: Query timed out" in error_detail:
                return None, (
                    f"Overpass API query was too complex or timed out. "
                    f"Try a smaller radius or more specific location. Status: {status_code}"
                )

            return None, f"Overpass API error. Status: {status_code}. Details: {error_detail}"

        except requests.exceptions.RequestException as e:
            return None, f"Error connecting to Overpass API: {str(e)}"

        except json.JSONDecodeError:
            return None, "Error parsing Overpass API response (invalid JSON)."


class OverpassQueryBuilder:
    """Builds Overpass QL queries for various search types."""

    def __init__(self, timeout: int = 300, max_results: int = 5000, maxsize: int = 67108864):
        self.timeout = timeout
        self.max_results = max_results
        self.maxsize = maxsize

    @staticmethod
    def format_tag_filter(key: str, value: str) -> str:
        """Format OSM tag filter, handling wildcard queries.

        Args:
            key: OSM tag key (e.g., "highway")
            value: OSM tag value (e.g., "motorway" or "*" for wildcard)

        Returns:
            Overpass QL tag filter string
        """
        if value == "*":
            # Wildcard query - match any value for the key
            return f'["{key}"]'
        else:
            # Specific value query
            return f'["{key}"="{value}"]'

    def build_amenity_query(
        self,
        osm_tag_key: str,
        osm_tag_value: str,
        location: OverpassLocation,
        radius_meters: int = 10000,
        prioritize_ways_relations: bool = False,
    ) -> str:
        """
        Build an Overpass QL query for searching amenities.

        Supports wildcard queries (value="*") which match any value for the key.
        Uses geometry preferences to determine which element types to query.

        Args:
            osm_tag_key: OSM tag key (e.g., "amenity")
            osm_tag_value: OSM tag value (e.g., "restaurant" or "*" for wildcard)
            location: OverpassLocation object with geocoded data
            radius_meters: Search radius for point-based queries
            prioritize_ways_relations: If True, query ways/relations first for highway queries

        Returns:
            Overpass QL query string
        """
        from services.tools.geocoding import should_include_element_in_query

        parts = [f"[out:json][timeout:{self.timeout}][maxsize:{self.maxsize}];"]
        tag_filter = self.format_tag_filter(osm_tag_key, osm_tag_value)

        if location.has_area:
            # Area-based search using relation ID
            overpass_area_id = location.osm_relation_id + 3600000000
            parts.append(f"area({overpass_area_id})->.search_area;")
            location_filter = "(area.search_area)"
        elif location.has_bbox:
            # Bounding box search
            s, w, n, e = location.bbox
            location_filter = f"({s},{w},{n},{e})"
        elif location.has_point:
            # Radius around point search
            location_filter = f"(around:{radius_meters},{location.lat},{location.lon})"
        else:
            raise ValueError("Location must have area, bbox, or point coordinates")

        # Build the query using geometry preferences
        if prioritize_ways_relations:
            # For highway/linear queries, get ways and relations first
            parts.append("(")
            if should_include_element_in_query(osm_tag_key, osm_tag_value, "way"):
                parts.append(f"  way{tag_filter}{location_filter};")
            if should_include_element_in_query(osm_tag_key, osm_tag_value, "relation"):
                parts.append(f"  relation{tag_filter}{location_filter};")
            parts.append(");")
            parts.append(f"out geom {self.max_results};")
        else:
            # Standard query: use geometry preferences to determine element types
            parts.append("(")
            if should_include_element_in_query(osm_tag_key, osm_tag_value, "node"):
                parts.append(f"  node{tag_filter}{location_filter};")
            if should_include_element_in_query(osm_tag_key, osm_tag_value, "way"):
                parts.append(f"  way{tag_filter}{location_filter};")
            if should_include_element_in_query(osm_tag_key, osm_tag_value, "relation"):
                parts.append(f"  relation{tag_filter}{location_filter};")
            parts.append(");")
            parts.append(f"out geom {self.max_results};")

        return "\n".join(parts)

    def build_multi_tag_query(
        self,
        tags: List[Dict[str, str]],
        location: OverpassLocation,
        radius_meters: int = 10000,
    ) -> str:
        """
        Build an Overpass QL query matching ANY of the given tags (OR semantics).

        Groups tags by key and uses regex filters when multiple values share the same key
        (e.g. building=residential|apartments|house). Cross-key tags use a union block.

        Args:
            tags: List of {"key": ..., "value": ...} dicts
            location: OverpassLocation with geocoded data
            radius_meters: Search radius for point-based queries

        Returns:
            Overpass QL query string
        """
        from services.tools.geocoding import should_include_element_in_query

        parts = [f"[out:json][timeout:{self.timeout}][maxsize:{self.maxsize}];"]

        if location.has_area:
            overpass_area_id = location.osm_relation_id + 3600000000
            parts.append(f"area({overpass_area_id})->.search_area;")
            location_filter = "(area.search_area)"
        elif location.has_bbox:
            s, w, n, e = location.bbox
            location_filter = f"({s},{w},{n},{e})"
        elif location.has_point:
            location_filter = f"(around:{radius_meters},{location.lat},{location.lon})"
        else:
            raise ValueError("Location must have area, bbox, or point coordinates")

        # Group values by key for regex optimisation
        by_key: Dict[str, List[str]] = defaultdict(list)
        for tag in tags:
            by_key[tag["key"]].append(tag["value"])

        parts.append("(")
        for key, values in by_key.items():
            if len(values) == 1:
                if values[0] == "*":
                    tag_filter = f'["{key}"]'
                else:
                    tag_filter = f'["{key}"="{values[0]}"]'
            else:
                # Multiple values for same key → anchored regex OR
                pattern = "|".join(re.escape(v) for v in values)
                tag_filter = f'["{key}"~"^({pattern})$"]'

            # Use the first value as representative for element-type preferences
            ref_value = values[0]
            for elem_type in ["node", "way", "relation"]:
                if should_include_element_in_query(key, ref_value, elem_type):
                    parts.append(f"  {elem_type}{tag_filter}{location_filter};")

        parts.append(");")
        parts.append(f"out geom {self.max_results};")

        return "\n".join(parts)

    def build_name_search_query(
        self,
        name: str,
        location: OverpassLocation,
        radius_meters: int = 10000,
    ) -> str:
        """
        Build an Overpass QL query for searching by name with fallback name fields.

        This searches for the name in multiple OSM name tags:
        - name
        - name:en
        - name:de
        - alt_name
        - old_name
        - official_name

        Args:
            name: The name to search for
            location: OverpassLocation object with geocoded data
            radius_meters: Search radius for point-based queries

        Returns:
            Overpass QL query string
        """
        parts = [f"[out:json][timeout:{self.timeout}][maxsize:{self.maxsize}];"]

        if location.has_area:
            overpass_area_id = location.osm_relation_id + 3600000000
            parts.append(f"area({overpass_area_id})->.search_area;")
            location_filter = "(area.search_area)"
        elif location.has_bbox:
            s, w, n, e = location.bbox
            location_filter = f"({s},{w},{n},{e})"
        elif location.has_point:
            location_filter = f"(around:{radius_meters},{location.lat},{location.lon})"
        else:
            raise ValueError("Location must have area, bbox, or point coordinates")

        # Search multiple name fields for better coverage
        name_tags = ["name", "name:en", "name:de", "alt_name", "old_name", "official_name"]

        # Escape regex special characters in user-provided name
        escaped_name = re.escape(name)

        parts.append("(")
        for tag in name_tags:
            # Case-insensitive regex search
            parts.append(f'  nwr["{tag}"~"{escaped_name}",i]{location_filter};')
        parts.append(");")
        parts.append(f"out geom {self.max_results};")

        return "\n".join(parts)

    def build_address_query(
        self,
        address_components: Dict[str, str],
        location: Optional[OverpassLocation] = None,
        radius_meters: int = 10000,
    ) -> str:
        """
        Build an Overpass QL query for structured address lookups using addr:* tags.

        Constructs a multi-condition query that searches for OSM elements tagged
        with all provided address components simultaneously, e.g.:
            node["addr:street"="Baker Street"]["addr:housenumber"="221B"]["addr:city"="London"]

        Args:
            address_components: Mapping of addr:* tag names to values, e.g.
                {"addr:street": "Baker Street", "addr:housenumber": "221B",
                 "addr:city": "London"}.  Keys must start with "addr:".
            location: Optional OverpassLocation to spatially constrain results.
                When omitted the search is global (use sparingly).
            radius_meters: Search radius for point-based location constraints.

        Returns:
            Overpass QL query string.

        Raises:
            ValueError: If address_components is empty or contains no addr:* keys.
        """
        if not address_components:
            raise ValueError("address_components must not be empty")

        valid_items: List[Tuple[str, str]] = []
        for key, value in address_components.items():
            if not key.startswith("addr:"):
                raise ValueError("address_components must only contain addr:* keys")
            if not re.fullmatch(r"addr:[A-Za-z0-9:_-]+", key):
                raise ValueError(f"Invalid addr key: {key}")

            normalized_value = str(value).strip()
            if not normalized_value:
                raise ValueError(f"address_components contains empty value for key '{key}'")

            valid_items.append((key, normalized_value))

        if not valid_items:
            raise ValueError("address_components must contain at least one addr:* key")

        def _escape_overpass_string(raw: str) -> str:
            # Keep escaping consistent with JSON string escaping for quotes,
            # backslashes and control chars.
            return json.dumps(raw, ensure_ascii=False)[1:-1]

        parts = [f"[out:json][timeout:{self.timeout}][maxsize:{self.maxsize}];"]

        if location is not None:
            if location.has_area:
                overpass_area_id = location.osm_relation_id + 3600000000
                parts.append(f"area({overpass_area_id})->.search_area;")
                location_filter = "(area.search_area)"
            elif location.has_bbox:
                s, w, n, e = location.bbox
                location_filter = f"({s},{w},{n},{e})"
            elif location.has_point:
                location_filter = f"(around:{radius_meters},{location.lat},{location.lon})"
            else:
                location_filter = ""
        else:
            location_filter = ""

        tag_filters = "".join(
            f'["{key}"="{_escape_overpass_string(value)}"]'
            for key, value in valid_items
        )

        parts.append("(")
        for osm_type in ("node", "way", "relation"):
            parts.append(f"  {osm_type}{tag_filters}{location_filter};")
        parts.append(");")
        # Recurse into member nodes so way geometry is available
        parts.append("(._; >;);")
        parts.append(f"out geom {self.max_results};")

        return "\n".join(parts)

    def build_center_query(
        self,
        osm_tag_key: str,
        osm_tag_value: str,
        lat: float,
        lon: float,
        radius_meters: int = 10000,
    ) -> str:
        """
        Build an Overpass QL query centered on explicit lat/lon coordinates.

        Supports wildcard queries (value="*") which match any value for the key.

        Args:
            osm_tag_key: OSM tag key (e.g., "amenity")
            osm_tag_value: OSM tag value (e.g., "restaurant" or "*" for wildcard)
            lat: Latitude of the center point
            lon: Longitude of the center point
            radius_meters: Search radius in meters

        Returns:
            Overpass QL query string
        """
        from services.tools.geocoding import should_include_element_in_query

        parts = [f"[out:json][timeout:{self.timeout}][maxsize:{self.maxsize}];"]
        tag_filter = self.format_tag_filter(osm_tag_key, osm_tag_value)
        location_filter = f"(around:{radius_meters},{lat},{lon})"

        parts.append("(")
        if should_include_element_in_query(osm_tag_key, osm_tag_value, "node"):
            parts.append(f"  node{tag_filter}{location_filter};")
        if should_include_element_in_query(osm_tag_key, osm_tag_value, "way"):
            parts.append(f"  way{tag_filter}{location_filter};")
        if should_include_element_in_query(osm_tag_key, osm_tag_value, "relation"):
            parts.append(f"  relation{tag_filter}{location_filter};")
        parts.append(");")
        parts.append(f"out geom {self.max_results};")

        return "\n".join(parts)


class OverpassResultConverter:
    """Converts OSM elements from Overpass API to GeoJSON features."""

    @staticmethod
    def convert_element_to_geojson(
        element: Dict[str, Any],
        osm_tag_filter: Optional[Tuple[str, str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Convert a single Overpass API element to a GeoJSON Feature.

        Args:
            element: OSM element dictionary from Overpass API
            osm_tag_filter: Optional (key, value) tuple to filter elements

        Returns:
            GeoJSON Feature dictionary or None if conversion fails
        """
        if not element or "type" not in element or "id" not in element:
            return None

        osm_type = element["type"]
        osm_id = str(element["id"])
        properties = element.get("tags", {})

        # Apply tag filter if provided
        if osm_tag_filter:
            key, value = osm_tag_filter
            if value == "*":
                # Wildcard: check if the key exists in properties
                if key not in properties:
                    if osm_type == "node":
                        pass  # Let it through, might be part of a way
                    else:
                        return None
            else:
                # Specific value: check exact match
                if properties.get(key) != value:
                    if osm_type == "node":
                        pass  # Let it through, might be part of a way
                    else:
                        return None

        feature_id = f"{osm_type}/{osm_id}"
        geometry = OverpassResultConverter._extract_geometry(element, osm_type)

        if geometry is None:
            return None

        return {
            "type": "Feature",
            "id": feature_id,
            "properties": properties,
            "geometry": geometry,
        }

    @staticmethod
    def _extract_geometry(element: Dict[str, Any], osm_type: str) -> Optional[Dict[str, Any]]:
        """Extract GeoJSON geometry from an OSM element."""
        if osm_type == "node":
            if "lat" in element and "lon" in element:
                return {
                    "type": "Point",
                    "coordinates": [float(element["lon"]), float(element["lat"])],
                }

        elif osm_type == "way" and "geometry" in element:
            coords = [[float(pt["lon"]), float(pt["lat"])] for pt in element["geometry"]]

            if len(coords) < 2:
                return None

            # Check if it's a closed polygon
            if len(coords) >= 4 and coords[0][0] == coords[-1][0] and coords[0][1] == coords[-1][1]:
                return {"type": "Polygon", "coordinates": [coords]}
            else:
                return {"type": "LineString", "coordinates": coords}

        elif osm_type == "relation":
            # Try to extract geometry from relation
            if (
                "geometry" in element
                and isinstance(element["geometry"], list)
                and len(element["geometry"]) > 0
            ):
                coords = [
                    [float(pt["lon"]), float(pt["lat"])]
                    for pt in element["geometry"]
                    if "lon" in pt and "lat" in pt
                ]

                if len(coords) >= 2:
                    if (
                        len(coords) >= 4
                        and coords[0][0] == coords[-1][0]
                        and coords[0][1] == coords[-1][1]
                    ):
                        return {"type": "Polygon", "coordinates": [coords]}
                    else:
                        return {"type": "LineString", "coordinates": coords}

            # Fallback to center point
            if "center" in element and "lat" in element["center"] and "lon" in element["center"]:
                return {
                    "type": "Point",
                    "coordinates": [
                        float(element["center"]["lon"]),
                        float(element["center"]["lat"]),
                    ],
                }

        return None

    @staticmethod
    def group_features_by_geometry(
        features: List[Dict[str, Any]],
    ) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """
        Group GeoJSON features by their geometry type.

        Args:
            features: List of GeoJSON Feature dictionaries

        Returns:
            Tuple of (point_features, polygon_features, linestring_features)
        """
        points = []
        polygons = []
        linestrings = []

        for feature in features:
            if not feature or not feature.get("geometry"):
                continue

            geom_type = feature["geometry"]["type"]
            if geom_type == "Point":
                points.append(feature)
            elif geom_type == "Polygon":
                polygons.append(feature)
            elif geom_type == "LineString":
                linestrings.append(feature)

        return points, polygons, linestrings

    @staticmethod
    def filter_point_noise(
        point_features: List[Dict],
        polygon_features: List[Dict],
        linestring_features: List[Dict],
    ) -> List[Dict]:
        """
        Filter out point features when polygons/lines are available.

        For highway queries and similar, having way geometries makes point
        nodes redundant noise on the map.

        Args:
            point_features: List of point GeoJSON features
            polygon_features: List of polygon GeoJSON features
            linestring_features: List of linestring GeoJSON features

        Returns:
            Filtered list of point features (empty if polygons/lines exist)
        """
        if polygon_features or linestring_features:
            logger.info(
                f"Filtering out {len(point_features)} point features "
                f"(have {len(polygon_features)} polygons and {len(linestring_features)} lines)"
            )
            return []
        return point_features

    @staticmethod
    def deduplicate_features(features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate features based on their OSM ID.

        Args:
            features: List of GeoJSON Feature dictionaries

        Returns:
            Deduplicated list of features
        """
        seen_ids = set()
        unique_features = []

        for feature in features:
            feature_id = feature.get("id")
            if feature_id and feature_id not in seen_ids:
                seen_ids.add(feature_id)
                unique_features.append(feature)
            elif not feature_id:
                # Keep features without IDs (shouldn't happen normally)
                unique_features.append(feature)

        if len(features) != len(unique_features):
            logger.info(f"Deduplicated features: {len(features)} -> {len(unique_features)}")

        return unique_features


def create_feature_collection_geodata(
    features: List[Dict[str, Any]],
    collection_type: str,  # "Points", "Areas", "Lines"
    amenity_display: str,
    location_display: str,
    osm_tag_kv: str,
    location_filename: str,
) -> Optional[GeoDataObject]:
    """
    Create a GeoDataObject for a FeatureCollection of a specific geometry type.

    Uses user-friendly geometry labels instead of technical terms (e.g.,
    "Hospital locations" instead of "Hospitals (Points)").

    Args:
        features: List of GeoJSON Feature dictionaries
        collection_type: Type of collection ("Points", "Areas", "Lines")
        amenity_display: User-friendly amenity name (e.g., "Restaurants")
        location_display: User-friendly location name (e.g., "Paris, France")
        osm_tag_kv: OSM tag key=value (e.g., "amenity=restaurant")
        location_filename: Clean location name for filenames

    Returns:
        GeoDataObject or None if no features
    """
    if not features:
        return None

    feature_collection = {"type": "FeatureCollection", "features": features}

    # Generate filename
    safe_amenity = amenity_display.lower().replace(" ", "_").replace("=", "_").replace(":", "_")
    safe_location = location_filename.lower().replace(" ", "_").replace(",", "").replace("'", "")
    file_name = f"overpass_{safe_amenity}_{collection_type.lower()}_{safe_location}.json"

    try:
        content_bytes = json.dumps(
            feature_collection, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")

        # Validate JSON
        json.loads(content_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.error(f"Error encoding GeoJSON for {file_name}: {e}")
        return None

    data_url, unique_id = store_file(file_name, content_bytes)
    sha256_hex = hashlib.sha256(content_bytes).hexdigest()
    size_bytes = len(content_bytes)

    # Calculate bounding box
    bounding_box_str = _calculate_bbox_string(features)

    # Get user-friendly geometry label
    osm_key = osm_tag_kv.split("=", 1)[0] if "=" in osm_tag_kv else ""
    geo_label, geo_hint = get_geometry_display_label(osm_key, collection_type)

    # Build user-friendly collection name
    collection_name = f"{amenity_display} {geo_label} in {location_display}"
    description = (
        f"{len(features)} {amenity_display.lower()} {geo_label} ({geo_hint}) "
        f"near {location_display}. Data from OpenStreetMap."
    )

    # Extract sample feature names for preview
    sample_names = _extract_sample_names(features, max_samples=5)

    # Generate spatial extent description
    spatial_extent = _describe_spatial_extent(bounding_box_str)

    return GeoDataObject(
        id=unique_id,
        data_source_id="geocodeOverpassCollection",
        data_type=DataType.GEOJSON,
        data_origin=DataOrigin.TOOL,
        data_source="OpenStreetMap contributors",
        data_link=data_url,
        name=collection_name,
        title=collection_name,
        description=description,
        llm_description=description,
        score=0.85,
        bounding_box=bounding_box_str,
        layer_type="GeoJSON",
        properties={
            "feature_count": len(features),
            "query_amenity_key": amenity_display,
            "query_location": location_display,
            "query_osm_tag": osm_tag_kv,
            "geometry_type_collected": collection_type,
            "geometry_label": geo_label,
            "geometry_hint": geo_hint,
            "sample_names": sample_names,
            "spatial_extent": spatial_extent,
        },
        sha256=sha256_hex,
        size=size_bytes,
    )


def _extract_sample_names(features: List[Dict[str, Any]], max_samples: int = 5) -> List[str]:
    """Extract sample feature names from a list of GeoJSON features."""
    names = []
    for feature in features:
        props = feature.get("properties", {})
        name = props.get("name") or props.get("name:en") or props.get("alt_name")
        if name and name not in names:
            names.append(name)
        if len(names) >= max_samples:
            break
    return names


def _describe_spatial_extent(
    bbox_str: Optional[str],
) -> Optional[str]:
    """
    Generate a human-readable description of a bounding box extent.

    Args:
        bbox_str: WKT POLYGON string from _calculate_bbox_string

    Returns:
        A plain-language extent description, or None
    """
    if not bbox_str:
        return None

    try:
        # Parse coordinates from WKT POLYGON
        inner = bbox_str.replace("POLYGON((", "").replace("))", "")
        coords = [c.strip().split() for c in inner.split(",")]
        lons = [float(c[0]) for c in coords]
        lats = [float(c[1]) for c in coords]

        min_lon, max_lon = min(lons), max(lons)
        min_lat, max_lat = min(lats), max(lats)

        # Approximate distance in km (rough, using equirectangular)
        import math

        avg_lat = (min_lat + max_lat) / 2
        lat_dist_km = (max_lat - min_lat) * 111.32
        lon_dist_km = (max_lon - min_lon) * 111.32 * math.cos(math.radians(avg_lat))

        if lat_dist_km < 1 and lon_dist_km < 1:
            return (
                f"covers a small area (about {max(lat_dist_km, lon_dist_km) * 1000:.0f} m across)"
            )
        elif lat_dist_km < 10 and lon_dist_km < 10:
            return f"covers about {lon_dist_km:.1f} km x {lat_dist_km:.1f} km"
        else:
            return f"covers about {lon_dist_km:.0f} km x {lat_dist_km:.0f} km"
    except (ValueError, IndexError):
        return None


def _calculate_bbox_string(features: List[Dict[str, Any]]) -> Optional[str]:
    """Calculate a WKT POLYGON bounding box string from GeoJSON features."""
    all_lons = []
    all_lats = []

    for feature in features:
        if not feature.get("geometry"):
            continue

        geom_type = feature["geometry"]["type"]
        coords = feature["geometry"]["coordinates"]

        if geom_type == "Point":
            all_lons.append(coords[0])
            all_lats.append(coords[1])
        elif geom_type == "LineString":
            all_lons.extend([c[0] for c in coords])
            all_lats.extend([c[1] for c in coords])
        elif geom_type == "Polygon":
            poly_coords = coords[0]  # Outer ring
            all_lons.extend([c[0] for c in poly_coords])
            all_lats.extend([c[1] for c in poly_coords])

    if not all_lons or not all_lats:
        return None

    min_lon, max_lon = min(all_lons), max(all_lons)
    min_lat, max_lat = min(all_lats), max(all_lats)

    # Add buffer for point clusters
    if (max_lon - min_lon < 0.001) and (max_lat - min_lat < 0.001):
        buffer = 0.001
        min_lon -= buffer
        max_lon += buffer
        min_lat -= buffer
        max_lat += buffer

    return (
        f"POLYGON(({max_lon} {min_lat},"
        f"{max_lon} {max_lat},"
        f"{min_lon} {max_lat},"
        f"{min_lon} {min_lat},"
        f"{max_lon} {min_lat}))"
    )


def is_highway_query(osm_tag_key: str) -> bool:
    """Check if the query is for highway features."""
    return osm_tag_key == "highway"


def is_linear_feature_query(osm_tag_key: str, osm_tag_value: str = "*") -> bool:
    """Check if the query is for linear feature types (highway, railway, waterway, etc.).

    For aeroway, distinguishes between linear sub-features (runway, taxiway) and
    point/area features (aerodrome, helipad, terminal, …) which should be queried
    like amenities (nodes included) rather than like highways (ways only).
    """
    if osm_tag_key == "aeroway":
        from services.tools.constants import AEROWAY_POINT_VALUES

        # Wildcard or actual linear values → treat as linear
        if osm_tag_value == "*":
            return True
        return osm_tag_value not in AEROWAY_POINT_VALUES
    return osm_tag_key in ("highway", "railway", "waterway", "power")
