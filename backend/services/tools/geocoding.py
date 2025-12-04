import hashlib
import json
from typing import Any, Dict, List, Optional, Union

import requests
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from typing_extensions import Annotated

from models.geodata import DataOrigin, DataType, GeoDataObject
from models.states import GeoDataAgentState
from services.storage.file_management import store_file

from .constants import AMENITY_MAPPING

headers_nalamap = {
    "User-Agent": "NaLaMap, github.com/nalamap, next generation geospatial analysis using agents"
}


def get_geometry_preferences(osm_key: str) -> Dict[str, Any]:
    """
    Get geometry preferences for an OSM key.

    Returns default preferences if key not configured.

    Args:
        osm_key: OSM tag key (e.g., "highway")

    Returns:
        Dictionary with geometry preferences
    """
    from services.tools.constants import OSM_GEOMETRY_PREFERENCES

    default_prefs = {
        "preferred_geometries": ["node", "way", "relation"],
        "exclude_geometries": [],
        "exclude_values": set(),
        "description": "No specific geometry preferences",
    }

    return OSM_GEOMETRY_PREFERENCES.get(osm_key, default_prefs)


def should_include_element_in_query(osm_key: str, osm_value: str, element_type: str) -> bool:
    """
    Determine if an element type should be included in the Overpass query.

    Args:
        osm_key: OSM tag key (e.g., "highway")
        osm_value: OSM tag value (e.g., "*" or "motorway")
        element_type: OSM element type ("node", "way", "relation")

    Returns:
        True if element type should be queried, False otherwise
    """
    from services.tools.constants import OSM_GEOMETRY_PREFERENCES

    # If wildcard query and key has preferences, use them
    if osm_value == "*" and osm_key in OSM_GEOMETRY_PREFERENCES:
        prefs = get_geometry_preferences(osm_key)
        return element_type in prefs["preferred_geometries"]

    # For specific values, check if excluded
    prefs = get_geometry_preferences(osm_key)
    if osm_value in prefs.get("exclude_values", set()):
        return False

    # Default: include all
    return True


def should_include_element_in_results(
    element: Dict[str, Any], osm_key: str, osm_value: str
) -> bool:
    """
    Determine if an element should be included in results after query.
    Provides a second layer of filtering.

    Args:
        element: OSM element from Overpass response
        osm_key: OSM tag key
        osm_value: OSM tag value

    Returns:
        True if element should be included, False otherwise
    """
    prefs = get_geometry_preferences(osm_key)
    element_type = element.get("type")
    element_tags = element.get("tags", {})

    # Check if geometry type is excluded
    if element_type in prefs.get("exclude_geometries", []):
        return False

    # Check if specific tag value is excluded
    element_value = element_tags.get(osm_key)
    if element_value in prefs.get("exclude_values", set()):
        return False

    return True


@tool
def geocode_using_geonames(location: str, maxRows: int = 3) -> str:
    """
    Use for: Basic geocoding of place names (e.g., cities, countries, landmarks).
    Returns coordinates and bounding boxes.
    Strengths:
    * Provides coordinates and a well managed system of hierarchical geographic data
      specific to administrational units, places and landmarks.
    * Is globally consistent and represents better the official administrative units.
    * Has mulit language support.
    * Can be used to quickly retrieve bounding boxes that can feed into other tools
      such as the query_librarian_postgis
    * If a user requires a map with multiple locations such as cities and landmarks
      shown as points and a low zoom level, this datasource provides adequate data
      for the map.

    Limitations:
    * Returns only coordinates and bounding boxes. Is therefore not a good fit if
      user needs to actually see the boundaries of a country or city on the map
    * Has no no street-level support and cannot serve for adress-level geocoding.
    """
    # Later * Can be used to retrieve hierarchical information on an address e.g.
    # country, state, city etc. which can be helpful to get more information on
    # ambiguous geocoding requests.
    # Later: Tool can be used for reverse geocoding e.g. if a user inputs point data
    # and would like to have a summary which points fall within which administrative
    # unit.
    # Later: Add support for advanced queries like hierarchical queries, find nearby
    # places, find country information, time zones, elevation etc.
    from os import getenv

    url: str = (
        f"http://api.geonames.org/searchJSON?q={location}&maxRows={maxRows}"
        f"&username={getenv('GEONAMES_USER', 'nalamap')}"
    )
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        if len(data) > 0:
            places = data["geonames"]
            return json.dumps(places)
        else:
            return "No results found."
    else:
        return "Error calling the GeoNames API."


# Note: Contains GeoJSON & Bounding Box: TODO: sidechannel GeoJSON to not overload our LLMs
@tool
def geocode_using_nominatim(query: str, geojson: bool = False, maxRows: int = 3) -> str:
    """Geocoding user requests using the Open Street Map Nominatim API."""
    # TODO: Add support for OSM tags.
    url: str = (
        f"https://nominatim.openstreetmap.org/search"
        f"?q={query}&format=json&polygon_kml={1 if geojson else 0}"
        f"&addressdetails=1&limit={maxRows}"
    )
    response = requests.get(url, headers=headers_nalamap)
    if response.status_code == 200:
        data = response.json()
        if len(data):
            return json.dumps(data)
        else:
            return "No results found."
    else:
        print(response.json())
        return "Error querying the Nominatim API."


def create_geodata_object_from_geojson(
    nominatim_response: Dict[str, Any],
) -> Optional[GeoDataObject]:
    """Saves the GeoJson response, saves it in storage and create a GeoDataObject from it"""
    if "geojson" not in nominatim_response:
        return None
    place_id: str = str(nominatim_response["place_id"])
    name: str = nominatim_response["name"]

    # Build properties from nominatim response
    properties: Dict[str, Any] = {}
    for prop in [
        "place_id",
        "name",
        "display_name",
        "licence",
        "osm_type",
        "osm_id",
        "lat",
        "lon",
        "class",
        "type",
        "place_rank",
        "importance",
        "addresstype",
        "address",
    ]:
        if prop in nominatim_response:
            properties[prop] = nominatim_response[prop]

    geojson: Dict[str, Any] = {
        "type": "Feature",
        "geometry": nominatim_response["geojson"],
        "properties": properties,
    }

    # Use ensure_ascii=False for proper UTF-8 encoding
    # and separators for compact output
    try:
        content_bytes = json.dumps(geojson, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )

        # Validate the JSON is complete by attempting to parse it
        json.loads(content_bytes.decode("utf-8"))

    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        error_msg = f"Error encoding/validating GeoJSON for " f"{place_id}_{name}.json: {e}"
        print(error_msg)
        return None

    url, unique_id = store_file(f"{place_id}_{name}.json", content_bytes)
    sha256_hex = hashlib.sha256(content_bytes).hexdigest()
    size_bytes = len(content_bytes)
    # Copy selected properties
    properties: Dict[str, Any] = dict()
    for prop in [
        "place_id",
        "licence",
        "osm_type",
        "osm_id",
        "lat",
        "lon",
        "class",
        "type",
        "place_rank",
        "addresstype",
        "address",
    ]:
        if prop in nominatim_response:
            properties[prop] = nominatim_response[prop]

    bbox: Optional[List[str]] = nominatim_response["boundingbox"]
    bounding_box: Optional[str]
    if bbox and len(bbox) == 4:
        lat_min, lat_max, lon_min, lon_max = map(float, bbox)
        bounding_box = (
            f"POLYGON(({lon_max} {lat_min},"
            f"{lon_max} {lat_max},"
            f"{lon_min} {lat_max},"
            f"{lon_min} {lat_min},"
            f"{lon_max} {lat_min}))"
        )
    else:
        bounding_box = None

    geoobject: GeoDataObject = GeoDataObject(
        id=unique_id,
        data_source_id="geocodeNominatim",
        data_type=DataType.GEOJSON,
        data_origin=DataOrigin.TOOL,
        data_source=nominatim_response["licence"],
        data_link=url,
        name=name,
        title=name,
        description=nominatim_response["display_name"],
        llm_description=nominatim_response["display_name"],
        score=nominatim_response["importance"],
        bounding_box=bounding_box,
        layer_type="GeoJSON",
        properties=properties,
        sha256=sha256_hex,
        size=size_bytes,
    )

    return geoobject


@tool
def geocode_using_nominatim_to_geostate(
    state: Annotated[GeoDataAgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    query: str,
    geojson: bool = True,
    maxRows: int = 5,
) -> Union[Dict[str, Any], Command]:
    """Geocode an address using OpenStreetMap Nominatim API. Returns Bounding Box for further
    request and GeoJson of the area to show to the user.
    Use for: Geocoding specific addresses or when detailed data (e.g., place types) is needed.
    Strengths:
    * Provides detailed polygon data as GeoJSON (e.g. polygons of countries, states, cities)
      which can be used for map visualization and further analysis.
    * For forward geocoding: Converts place names or addresses into geographic coordinates.
    * Detailed address data, including house numbers, street names, neighborhoods, and postcodes.
    * Provides the geographical extent (min/max latitude and longitude) for places, including
      cities, countries, and sometimes smaller features like neighborhoods
    * Categorizes results by OSM tags, indicating the type of place (e.g., city, street, building, amenity, shop)
    * Reverse geocoding: Converts geographic coordinates into detailed address information.
    Limitations:
    * Nominatim relies on crowd-sourced OSM data, so accuracy and completeness depend on community contributions.
    * Provides limited metadata. It does not include attributes like population, elevation, time zones, or weather data.
    * does not support broader geographical queries like finding nearby places, hierarchical relationships beyond administrative divisions
    """
    url: str = (
        f"https://nominatim.openstreetmap.org/search"
        f"?q={query}&format=json&polygon_geojson={1 if geojson else 0}"
        f"&addressdetails=0&limit={maxRows}"
    )
    response = requests.get(url, headers=headers_nalamap)
    if response.status_code == 200:
        data = response.json()
        if len(data):
            cleaned_data: List[Dict[str, Any]] = []
            for elem in data:
                if "geojson" in elem:
                    geocoded_object: Optional[GeoDataObject] = create_geodata_object_from_geojson(
                        elem
                    )
                    del elem["geojson"]
                    if geocoded_object:
                        elem["id"] = geocoded_object.id
                        elem["data_source_id"] = geocoded_object.data_source_id
                        if (
                            "geodata_results" not in state
                            or state["geodata_results"] is None
                            or not isinstance(state["geodata_results"], List)
                        ):
                            state["geodata_results"] = [geocoded_object]
                        else:
                            state["geodata_results"].append(geocoded_object)
                cleaned_data.append(dict(elem))
            if geojson:
                # Simplified message for LLM
                num_objects_created = sum(
                    1 for elem in cleaned_data if "id" in elem and "data_source_id" in elem
                )

                actionable_layers_info = []
                if num_objects_created > 0:
                    for elem in cleaned_data:
                        if "id" in elem and "data_source_id" in elem:
                            actionable_layers_info.append(
                                {
                                    "name": elem.get(
                                        "name",
                                        elem.get("display_name", "Unknown Location"),
                                    ),
                                    "id": elem["id"],
                                    "data_source_id": elem[
                                        "data_source_id"
                                    ],  # Should be "geocodeNominatim"
                                }
                            )

                if not actionable_layers_info:
                    tool_message_content = "Successfully geocoded '{query}'. Found {len(cleaned_data)} potential result(s), but no GeoData objects with full geometry were created or stored."
                else:
                    tool_message_content = "Successfully geocoded '{query}'. Found {len(cleaned_data)} potential result(s). {len(actionable_layers_info)} GeoData object(s) with full geometry created and stored in geodata_results. "

                    # Provide structured info for the agent and clear instructions
                    layer_details_for_agent = json.dumps(actionable_layers_info)

                    # Get an example name for the guidance
                    example_name = (
                        actionable_layers_info[0].get("name", "Unknown Location")
                        if actionable_layers_info
                        else "Unknown Location"
                    )

                    user_response_guidance = (
                        "Call 'set_result_list' to make these layer(s) available for the user to select. "
                        + f"In your textual response to the user, confirm the geocoding success and mention the type of locations found (e.g., based on the query or results like '{example_name}'). "
                        + "State that the found layers are now listed (e.g., in a list or panel) and can be selected by the user to be added to the map. "
                        + "Ensure your response clearly indicates the user needs to take an action to add them to the map. "
                        + "Do NOT state or imply that the layers have already been added to the map. "
                        + "Do NOT include direct file paths, sandbox links, or any other internal storage paths in your textual response or as Markdown links."
                    )
                    tool_message_content += f"Actionable layer details: {layer_details_for_agent}. User response guidance: {user_response_guidance}"

                return Command(
                    update={
                        "messages": [
                            *state["messages"],
                            ToolMessage(
                                name="geocode_using_nominatim_to_geostate",
                                content=tool_message_content,
                                tool_call_id=tool_call_id,
                            ),
                        ],
                        # "global_geodata": state["global_geodata"],
                        "geodata_results": state["geodata_results"],
                    }
                )
            else:
                # Simplified message if no GeoJSON was stored
                tool_message_content = f"Successfully geocoded '{query}'. Found {len(cleaned_data)} potential result(s). No GeoJSON objects were stored as per request."
                brief_results = [
                    {
                        "name": elem.get("name", elem.get("display_name", "Unknown")),
                        "osm_id": elem.get("osm_id", "N/A"),
                        "class": elem.get("class", "N/A"),
                        "type": elem.get("type", "N/A"),
                    }
                    for elem in cleaned_data
                ][:3]
                tool_message_content += (
                    f" First few results (name, osm_id, class, type): {json.dumps(brief_results)}"
                )
                return {
                    "message": tool_message_content,
                    "results_summary": brief_results,
                }  # Return summary directly if not updating state
        else:
            return {"message": "No results found."}
    else:
        print(response.json())
        return {"message": "Error querying the Nominatim API."}


# Helper function to convert a single Overpass API element to a GeoJSON Feature dictionary
def convert_osm_element_to_geojson_feature(
    element: Dict[str, Any], osm_tag_value_filter: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Converts a single Overpass API element to a GeoJSON Feature dictionary.
    Returns None if the element cannot be converted or lacks geometry.
    Applies an optional filter to include only elements with a specific tag and value.
    """
    if not element or "type" not in element or "id" not in element:
        return None

    osm_type = element["type"]
    osm_id = str(element["id"])
    properties = element.get("tags", {})

    # Apply tag filter if provided
    if osm_tag_value_filter:
        key, value = osm_tag_value_filter.split("=", 1)
        if not (properties.get(key) == value):
            # If it's a node, it might be a geometry node for a way/relation that *does* have the tag.
            # The Overpass query with "out geom" might return such nodes.
            # We'll let it pass for now and rely on higher-level logic to decide if it's a primary feature.
            # However, for constructing individual features, we are typically interested in those that *have* the tags.
            # This function is now more general. The caller of this function (within the main tool)
            # will decide which elements to process based on the primary query tags.
            pass  # No strict filtering here, caller handles primary feature identification

    # GeoJSON feature ID, can be non-unique if features are from different sources in a collection
    feature_id = f"{osm_type}/{osm_id}"

    geojson_feature: Dict[str, Any] = {
        "type": "Feature",
        "id": feature_id,
        "properties": properties,
        "geometry": None,
    }

    if osm_type == "node" and "lat" in element and "lon" in element:
        geojson_feature["geometry"] = {
            "type": "Point",
            "coordinates": [float(element["lon"]), float(element["lat"])],
        }
    elif osm_type == "way" and "geometry" in element:  # Assumes geometry from "out geom;"
        coords = [[float(pt["lon"]), float(pt["lat"])] for pt in element["geometry"]]
        if (
            len(coords) >= 2
        ):  # Need at least 2 points for LineString, 4 for valid Polygon (3 unique + close)
            if coords[0][0] == coords[-1][0] and coords[0][1] == coords[-1][1] and len(coords) >= 4:
                geojson_feature["geometry"] = {
                    "type": "Polygon",
                    "coordinates": [coords],
                }
            else:
                geojson_feature["geometry"] = {
                    "type": "LineString",
                    "coordinates": coords,
                }
        else:  # Not enough points
            return None
    elif osm_type == "relation":
        # Prefer "out geom;" if available and results in a usable geometry.
        # Overpass with "out geom;" on relations can be complex, sometimes returning members.
        # We'll prioritize "center" for simplicity if "geometry" isn't directly usable as Polygon/LineString.
        if (
            "geometry" in element
            and isinstance(element["geometry"], list)
            and len(element["geometry"]) > 0
        ):
            # Attempt to treat relation geometry like way geometry if it's a list of points
            # This is a simplification; true relation geometry might be MultiPolygon etc.
            coords = [
                [float(pt["lon"]), float(pt["lat"])]
                for pt in element["geometry"]
                if "lon" in pt and "lat" in pt
            ]
            if len(coords) >= 2:
                if (
                    coords[0][0] == coords[-1][0]
                    and coords[0][1] == coords[-1][1]
                    and len(coords) >= 4
                ):
                    geojson_feature["geometry"] = {
                        "type": "Polygon",
                        "coordinates": [coords],
                    }
                else:
                    geojson_feature["geometry"] = {
                        "type": "LineString",
                        "coordinates": coords,
                    }
            # Fall through to center if complex geometry not parsable into simple Polygon/LineString

        if (
            geojson_feature["geometry"] is None
            and "center" in element
            and "lat" in element["center"]
            and "lon" in element["center"]
        ):
            geojson_feature["geometry"] = {
                "type": "Point",
                "coordinates": [
                    float(element["center"]["lon"]),
                    float(element["center"]["lat"]),
                ],
            }
        elif geojson_feature["geometry"] is None:  # No usable geometry for relation
            return None
    else:  # Unknown type or missing geometry info
        return None

    if not geojson_feature["geometry"]:  # Final check
        return None

    return geojson_feature


# Helper function to create a GeoDataObject for a collection of features
def create_collection_geodata_object(
    features: List[Dict[str, Any]],
    collection_type_name: str,  # e.g., "Points", "Areas", "Lines"
    base_query_name: str,  # e.g., "restaurants near Eiffel Tower"
    amenity_key_display: str,  # e.g., "Restaurants"
    # e.g., "Eiffel Tower (using area bounds)" - for user-facing title/description
    location_name_display: str,
    osm_tag_kv_filter: str,  # e.g. "amenity=restaurant"
    location_name_for_filename: str,  # e.g., "Eiffel Tower" - for cleaner filenames
) -> Optional[GeoDataObject]:
    """
    Creates a single GeoDataObject for a FeatureCollection of a specific geometry type.
    Saves the FeatureCollection to a single file.
    """
    if not features:
        return None

    # Create a FeatureCollection
    feature_collection = {"type": "FeatureCollection", "features": features}

    # Generate a unique ID and filename for the collection
    safe_amenity_name = (
        amenity_key_display.lower().replace(" ", "_").replace("=", "_").replace(":", "_")
    )
    # Use location_name_for_filename for a cleaner file path
    safe_location_for_file = (
        location_name_for_filename.lower().replace(" ", "_").replace(",", "").replace("'", "")
    )
    file_name = (
        f"overpass_{safe_amenity_name}_{collection_type_name.lower()}_{safe_location_for_file}.json"
    )

    # Use ensure_ascii=False for proper UTF-8 encoding
    # and separators for compact output
    # This prevents unicode escape sequences and ensures clean JSON
    try:
        content_bytes = json.dumps(
            feature_collection, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")

        # Validate the JSON is complete by attempting to parse it
        json.loads(content_bytes.decode("utf-8"))

    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"Error encoding/validating GeoJSON for {file_name}: {e}")
        return None

    data_url, unique_id = store_file(file_name, content_bytes)
    sha256_hex = hashlib.sha256(content_bytes).hexdigest()
    size_bytes = len(content_bytes)

    # Calculate combined bounding box for the FeatureCollection
    all_lons: List[float] = []
    all_lats: List[float] = []
    for feature in features:
        if feature["geometry"]:
            geom_type = feature["geometry"]["type"]
            coords = feature["geometry"]["coordinates"]
            if geom_type == "Point":
                all_lons.append(coords[0])
                all_lats.append(coords[1])
            elif geom_type == "LineString":
                all_lons.extend([c[0] for c in coords])
                all_lats.extend([c[1] for c in coords])
            elif geom_type == "Polygon":
                # Coords is a list of linear rings, take the first (outer) ring
                poly_coords = coords[0]
                all_lons.extend([c[0] for c in poly_coords])
                all_lats.extend([c[1] for c in poly_coords])
            # TODO: Handle MultiPoint, MultiLineString, MultiPolygon if they occur

    bounding_box_str = None
    if all_lons and all_lats:
        min_lon, max_lon = min(all_lons), max(all_lons)
        min_lat, max_lat = min(all_lats), max(all_lats)

        # Create a small buffer if all features are points and very close, to make bbox visible
        is_all_points = all(f["geometry"]["type"] == "Point" for f in features if f["geometry"])
        if is_all_points and (max_lon - min_lon < 0.001) and (max_lat - min_lat < 0.001):
            buffer = 0.001
            min_lon -= buffer
            max_lon += buffer
            min_lat -= buffer
            max_lat += buffer

        bounding_box_str = (
            f"POLYGON(({max_lon} {min_lat},"
            f"{max_lon} {max_lat},"
            f"{min_lon} {max_lat},"
            f"{min_lon} {min_lat},"
            f"{max_lon} {min_lat}))"
        )

    collection_name = (
        f"{amenity_key_display} ({collection_type_name}) " f"near {location_name_display}"
    )
    description = f"{len(features)} {amenity_key_display.lower()} ({collection_type_name.lower()}) found matching '{osm_tag_kv_filter}' near {location_name_display}. Data from OpenStreetMap."

    # For a collection, top-level properties might be limited or summary.
    # Individual features retain their own properties.
    collection_properties = {
        "feature_count": len(features),
        "query_amenity_key": amenity_key_display,
        "query_location": location_name_display,  # Keep descriptive location here
        "query_osm_tag": osm_tag_kv_filter,
        "geometry_type_collected": collection_type_name,
    }

    geo_object = GeoDataObject(
        id=unique_id,
        data_source_id="geocodeOverpassCollection",  # New data_source_id
        data_type=DataType.GEOJSON,
        data_origin=DataOrigin.TOOL,
        data_source="OpenStreetMap contributors",
        data_link=data_url,
        name=collection_name,
        title=collection_name,
        description=description,
        llm_description=description,
        score=0.85,  # Slightly higher score for a processed collection
        bounding_box=bounding_box_str,
        layer_type="GeoJSON",  # Could be "GeoJSON Points", "GeoJSON Polygons" etc. if FE can use it
        properties=collection_properties,
        sha256=sha256_hex,
        size=size_bytes,
    )
    return geo_object


@tool
def geocode_using_overpass_to_geostate(
    state: Annotated[GeoDataAgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    query: str,
    amenity_key: str,  # e.g. "restaurant", "park", "hospital" - to be mapped to OSM tags
    location_name: str,  # e.g. "Paris", "London", "near the Colosseum", or a country name like "Germany"
    # Default search radius around a point, e.g. 10km. Used if location_name resolves to a point.
    radius_meters: int = 10000,
    # Max results from Overpass. Default is 2500. User can specify a different limit.
    max_results: int = 2500,
    timeout: int = 300,  # Default timeout in seconds
) -> Union[Dict[str, Any], Command]:
    """
    Geocode a location and search for amenities/POIs using the Overpass API.

    Args:
        state: The current agent state containing geodata and messages.
        tool_call_id: The tool call ID for the response.
        query: The user-friendly query/description for the search.
        amenity_key: The OSM feature type to search for. Supports amenities (e.g. "restaurant", "hospital"), infrastructure (e.g. "road", "bridge", "highway"), military facilities (e.g. "military", "barracks"), aviation (e.g. "airport", "aeroway"), natural features (e.g. "waterway", "natural"), buildings, and places. Use generic terms like "road" or "military" to search for all features of that type.
        location_name: The location to search (e.g. "Paris", "London", "Germany").
        radius_meters: Search radius in meters (default: 10000).
        max_results: Maximum number of results to return (default: 2500).
        timeout: Timeout for API requests in seconds (default: 300).

    Returns:
        A Command object to update the agent state or a dictionary with results.
    """
    # 1. Map amenity_key to OSM tag
    # Clean and process the amenity key
    amenity_key_cleaned = amenity_key.lower().replace(" ", "_")
    osm_tag_kv = AMENITY_MAPPING.get(amenity_key_cleaned)

    if not osm_tag_kv:
        return Command(
            update={
                "messages": [
                    *state["messages"],
                    ToolMessage(
                        name="geocode_using_overpass_to_geostate",
                        content=f"Sorry, I don't know how to search for '{amenity_key}'. Please try a common amenity type.",
                        tool_call_id=tool_call_id,
                    ),
                ]
            }
        )

    amenity_key_display = amenity_key_cleaned.replace("_", " ").title()

    # 2. Geocode location_name: Attempt to get an OSM relation ID, then bbox, then point.
    # Request addressdetails=1 to potentially get osm_type and osm_id for relations.
    nominatim_url = f"https://nominatim.openstreetmap.org/search?q={location_name}&format=json&limit=1&addressdetails=1&polygon_geojson=0"

    osm_relation_id: Optional[int] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    bbox_coords: Optional[List[float]] = None
    resolved_location_display_name: str = location_name
    search_mode_description: str = ""

    try:
        nominatim_response_req = requests.get(nominatim_url, headers=headers_nalamap, timeout=20)
        nominatim_response_req.raise_for_status()
        location_data_list = nominatim_response_req.json()

        if not location_data_list:
            return Command(
                update={
                    "messages": [
                        *state["messages"],
                        ToolMessage(
                            name="geocode_using_overpass_to_geostate",
                            content=f"Could not find location: {location_name}",
                            tool_call_id=tool_call_id,
                        ),
                    ]
                }
            )

        location_data = location_data_list[0]
        resolved_location_display_name = location_data.get("display_name", location_name)

        # Prioritize OSM relation ID for area search
        if location_data.get("osm_type") == "relation" and "osm_id" in location_data:
            try:
                osm_relation_id = int(location_data["osm_id"])
                search_mode_description = f"within the boundaries of '{resolved_location_display_name}' (OSM Relation ID: {osm_relation_id})"
            except ValueError:
                osm_relation_id = None  # Failed to parse ID, will fall back

        if osm_relation_id is None:  # Fallback to bounding box if no relation ID or if preferred
            if "boundingbox" in location_data:
                raw_bbox = location_data[
                    "boundingbox"
                ]  # [south_lat, north_lat, west_lon, east_lon]
                if len(raw_bbox) == 4:
                    try:
                        bbox_coords = [
                            float(raw_bbox[0]),
                            float(raw_bbox[2]),
                            float(raw_bbox[1]),
                            float(raw_bbox[3]),
                        ]  # s, w, n, e
                        search_mode_description = (
                            f"within the bounding box of '{resolved_location_display_name}'"
                        )
                    except ValueError:
                        bbox_coords = None

            if bbox_coords is None:  # Fallback to lat/lon if no relation or bbox
                if "lat" in location_data and "lon" in location_data:
                    lat = float(location_data["lat"])
                    lon = float(location_data["lon"])
                    search_mode_description = f"within {radius_meters}m of the center of '{resolved_location_display_name}'"
                else:
                    return Command(
                        update={
                            "messages": [
                                *state["messages"],
                                ToolMessage(
                                    name="geocode_using_overpass_to_geostate",
                                    content=f"Could not determine a usable geographic filter (area, bounding box, or center point) for: {location_name}",
                                    tool_call_id=tool_call_id,
                                ),
                            ]
                        }
                    )

    except requests.exceptions.RequestException as e:
        return Command(
            update={
                "messages": [
                    *state["messages"],
                    ToolMessage(
                        name="geocode_using_overpass_to_geostate",
                        content=f"Error geocoding '{location_name}': {str(e)}",
                        tool_call_id=tool_call_id,
                    ),
                ]
            }
        )
    except (KeyError, IndexError, ValueError) as e:
        print(f"Error processing location data: {e}")
        return Command(
            update={
                "messages": [
                    *state["messages"],
                    ToolMessage(
                        name="geocode_using_overpass_to_geostate",
                        content=f"Could not parse geocoding result for '{location_name}': {str(e)}",
                        tool_call_id=tool_call_id,
                    ),
                ]
            }
        )

    # 3. Construct Overpass API query
    osm_query_key, osm_query_value = osm_tag_kv.split("=", 1)

    # Helper function to format tag filter for Overpass query
    def format_tag_filter(key: str, value: str) -> str:
        """Format OSM tag filter, handling wildcard queries."""
        if value == "*":
            # Wildcard query - match any value for the key
            return f'["{key}"]'
        else:
            # Specific value query
            return f'["{key}"="{value}"]'

    tag_filter = format_tag_filter(osm_query_key, osm_query_value)
    overpass_query_parts: List[str] = [f"[out:json][timeout:{timeout}];"]

    if osm_relation_id is not None:
        # Area-based search using relation ID
        # Add 3600000000 to the OSM relation ID to make it an area ID for Overpass
        overpass_area_id = osm_relation_id + 3600000000
        overpass_query_parts.append(
            f"area({overpass_area_id})->.search_area;"
        )  # Correct way to define area from relation ID
        overpass_query_parts.append("(")
        # Use geometry preferences to determine which element types to query
        if should_include_element_in_query(osm_query_key, osm_query_value, "node"):
            overpass_query_parts.append(f"  node{tag_filter}(area.search_area);")
        if should_include_element_in_query(osm_query_key, osm_query_value, "way"):
            overpass_query_parts.append(f"  way{tag_filter}(area.search_area);")
        if should_include_element_in_query(osm_query_key, osm_query_value, "relation"):
            overpass_query_parts.append(f"  relation{tag_filter}(area.search_area);")
        overpass_query_parts.append(");")
    elif bbox_coords:
        # Bounding box search
        s, w, n, e = bbox_coords
        location_filter = f"({s},{w},{n},{e})"
        overpass_query_parts.append("(")
        # Use geometry preferences to determine which element types to query
        if should_include_element_in_query(osm_query_key, osm_query_value, "node"):
            overpass_query_parts.append(f"  node{tag_filter}{location_filter};")
        if should_include_element_in_query(osm_query_key, osm_query_value, "way"):
            overpass_query_parts.append(f"  way{tag_filter}{location_filter};")
        if should_include_element_in_query(osm_query_key, osm_query_value, "relation"):
            overpass_query_parts.append(f"  relation{tag_filter}{location_filter};")
        overpass_query_parts.append(");")
    elif lat is not None and lon is not None:
        # Radius around point search
        location_filter = f"(around:{radius_meters},{lat},{lon})"
        overpass_query_parts.append("(")
        # Use geometry preferences to determine which element types to query
        if should_include_element_in_query(osm_query_key, osm_query_value, "node"):
            overpass_query_parts.append(f"  node{tag_filter}{location_filter};")
        if should_include_element_in_query(osm_query_key, osm_query_value, "way"):
            overpass_query_parts.append(f"  way{tag_filter}{location_filter};")
        if should_include_element_in_query(osm_query_key, osm_query_value, "relation"):
            overpass_query_parts.append(f"  relation{tag_filter}{location_filter};")
        overpass_query_parts.append(");")
    else:
        return Command(
            update={
                "messages": [
                    *state["messages"],
                    ToolMessage(
                        name="geocode_using_overpass_to_geostate",
                        content="Failed to establish a location filter (area, bbox, or radius) for Overpass query.",
                        tool_call_id=tool_call_id,
                    ),
                ]
            }
        )

    overpass_query_parts.append(f"out geom {max_results};")
    overpass_query = "\n".join(overpass_query_parts)

    # 4. Execute Overpass API query
    overpass_api_url = "https://overpass-api.de/api/interpreter"
    try:
        api_response = requests.post(
            overpass_api_url,
            data={"data": overpass_query},
            headers={
                **headers_nalamap,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=timeout + 10,
        )  # API timeout slightly longer
        api_response.raise_for_status()
        overpass_data = api_response.json()
    except requests.exceptions.Timeout:
        return Command(
            update={
                "messages": [
                    *state["messages"],
                    ToolMessage(
                        name="geocode_using_overpass_to_geostate",
                        content=f"Overpass API query for '{amenity_key_display}' {search_mode_description} timed out after {timeout} seconds.",
                        tool_call_id=tool_call_id,
                    ),
                ]
            }
        )
    except requests.exceptions.HTTPError as e:
        error_detail = e.response.text[:500] if e.response else str(e)
        error_message_content = f"Overpass API error for '{amenity_key_display}' {search_mode_description}. Status: {e.response.status_code if e.response else 'N/A'}. Details: {error_detail}"
        if (
            "runtime error: Query timed out" in error_detail
            or "runtime error: load_query" in error_detail
        ):
            error_message_content = f"Overpass API query for '{amenity_key_display}' {search_mode_description} was too complex or timed out. Try a smaller radius or more specific location/area. Details: {error_detail}"
        return Command(
            update={
                "messages": [
                    *state["messages"],
                    ToolMessage(
                        name="geocode_using_overpass_to_geostate",
                        content=error_message_content,
                        tool_call_id=tool_call_id,
                    ),
                ]
            }
        )
    except requests.exceptions.RequestException as e:
        return Command(
            update={
                "messages": [
                    *state["messages"],
                    ToolMessage(
                        name="geocode_using_overpass_to_geostate",
                        content=f"Error connecting to Overpass API: {str(e)}",
                        tool_call_id=tool_call_id,
                    ),
                ]
            }
        )
    except json.JSONDecodeError:
        return Command(
            update={
                "messages": [
                    *state["messages"],
                    ToolMessage(
                        name="geocode_using_overpass_to_geostate",
                        content=f"Error parsing Overpass API response. Response was: {api_response.text[:200]}...",
                        tool_call_id=tool_call_id,
                    ),
                ]
            }
        )

    # 5. Process elements and group by geometry type
    if "elements" not in overpass_data or not overpass_data["elements"]:
        return Command(
            update={
                "messages": [
                    *state["messages"],
                    ToolMessage(
                        name="geocode_using_overpass_to_geostate",
                        content=f"No '{amenity_key_display}' found {search_mode_description}.",
                        tool_call_id=tool_call_id,
                    ),
                ]
            }
        )

    point_features: List[Dict[str, Any]] = []
    polygon_features: List[Dict[str, Any]] = []
    linestring_features: List[Dict[str, Any]] = []

    processed_osm_ids = set()

    for element in overpass_data["elements"]:
        if "type" not in element or "id" not in element:
            continue

        # Apply geometry preferences filtering
        if not should_include_element_in_results(element, osm_query_key, osm_query_value):
            continue

        osm_element_id = f"{element['type']}/{element['id']}"

        # Note: Tag matching is handled later in the processing loop
        # This check is kept for potential future use but currently doesn't filter
        element_tags = element.get("tags", {})

        if osm_element_id in processed_osm_ids:
            continue

        feature_dict = convert_osm_element_to_geojson_feature(element)

        if feature_dict and feature_dict["geometry"]:
            element_tags = feature_dict.get("properties", {})
            # For wildcard queries, check if the key exists; for specific values, check exact match
            if osm_query_value == "*":
                is_primary_tagged_feature = osm_query_key in element_tags
            else:
                is_primary_tagged_feature = element_tags.get(osm_query_key) == osm_query_value

            if element["type"] != "node" and not is_primary_tagged_feature:
                continue

            processed_osm_ids.add(osm_element_id)
            geom_type = feature_dict["geometry"]["type"]
            if geom_type == "Point":
                point_features.append(feature_dict)
            elif geom_type == "Polygon":
                polygon_features.append(feature_dict)
            elif geom_type == "LineString":
                linestring_features.append(feature_dict)

    created_collections: List[GeoDataObject] = []
    actionable_layers_info = []

    if point_features:
        collection_obj = create_collection_geodata_object(
            point_features,
            "Points",
            query,
            amenity_key_display,
            resolved_location_display_name,
            osm_tag_kv,
            location_name,
        )
        if collection_obj:
            created_collections.append(collection_obj)
            actionable_layers_info.append(
                {
                    "name": collection_obj.name,
                    "type": "Points",
                    "count": len(point_features),
                    "id": collection_obj.id,
                    "data_source_id": "geocodeOverpassCollection",
                }
            )

    if polygon_features:
        collection_obj = create_collection_geodata_object(
            polygon_features,
            "Areas",
            query,
            amenity_key_display,
            resolved_location_display_name,
            osm_tag_kv,
            location_name,
        )
        if collection_obj:
            created_collections.append(collection_obj)
            actionable_layers_info.append(
                {
                    "name": collection_obj.name,
                    "type": "Areas",
                    "count": len(polygon_features),
                    "id": collection_obj.id,
                    "data_source_id": "geocodeOverpassCollection",
                }
            )

    if linestring_features:
        collection_obj = create_collection_geodata_object(
            linestring_features,
            "Lines",
            query,
            amenity_key_display,
            resolved_location_display_name,
            osm_tag_kv,
            location_name,
        )
        if collection_obj:
            created_collections.append(collection_obj)
            actionable_layers_info.append(
                {
                    "name": collection_obj.name,
                    "type": "Lines",
                    "count": len(linestring_features),
                    "id": collection_obj.id,
                    "data_source_id": "geocodeOverpassCollection",
                }
            )

    if not created_collections:
        return Command(
            update={
                "messages": [
                    *state["messages"],
                    ToolMessage(
                        name="geocode_using_overpass_to_geostate",
                        content=f"No '{amenity_key_display}' found with parsable geometry {search_mode_description}.",
                        tool_call_id=tool_call_id,
                    ),
                ]
            }
        )

    current_geodata = state.get("geodata_results", [])
    if not isinstance(current_geodata, list):
        current_geodata = []
    current_geodata.extend(created_collections)

    total_features_found = len(point_features) + len(polygon_features) + len(linestring_features)

    if not actionable_layers_info:
        tool_message_content = f"Found {amenity_key_display} {search_mode_description}, but could not form any distinct geometry layers."
    else:
        tool_message_content = f"Found {total_features_found} '{amenity_key_display}' feature(s) {search_mode_description}. Created {len(created_collections)} collection layer(s). "

        if total_features_found >= max_results:
            limit_hit_info = (
                f"The query returned the maximum allowed number of features ({max_results}). "
                "If you need more results, you can ask me to increase this limit. "
                "However, please be aware that a very large number of features can significantly degrade map performance."
            )
            tool_message_content += f"LIMIT_INFO: {limit_hit_info}. "

        layer_details_for_agent = json.dumps(actionable_layers_info)

        # Safely get an example name for the guidance
        example_layer_name = (
            actionable_layers_info[0].get("name", "Unknown Layer")
            if actionable_layers_info
            else "Unknown Layer"
        )

        user_response_guidance = (
            "Call 'set_result_list' to make these layers available for the user to select. "
            + f"In your textual response to the user, mention the type of amenities and location searched (e.g., '{amenity_key_display}' near '{resolved_location_display_name}'). "
            + f"You can cite an example layer name like '{example_layer_name}'. "
            + "State that the found layers are now listed (e.g., in a list or panel) and can be selected by the user to be added to the map. "
            + "Ensure your response clearly indicates the user needs to take an action to add them to the map. "
            + "Do NOT state or imply that the layers have already been added to the map. "
            + "Do NOT include direct file paths, sandbox links, or any other internal storage paths in your textual response or as Markdown links."
        )
        tool_message_content += f"Actionable layer details: {layer_details_for_agent}. User response guidance: {user_response_guidance}"

    return Command(
        update={
            "messages": [
                *state["messages"],
                ToolMessage(
                    name="geocode_using_overpass_to_geostate",
                    content=tool_message_content,
                    tool_call_id=tool_call_id,
                ),
            ],
            # "global_geodata": current_geodata,
            "geodata_results": current_geodata,
        }
    )


"""
Additional notable finds for even more geocoding:
OpenStreetMap Overpass API: bit more mighty
https://wiki.openstreetmap.org/wiki/Overpass_API#Quick_Start_(60_seconds):_for_Developers/Programmers

Combining e.g. Geonames Latitude & Longitude + Admin Level + https://global.mapit.mysociety.org could show us bounding boxes

Geoapify
https://apidocs.geoapify.com/docs/boundaries/

Geoboundaries
https://www.geoboundaries.org/
"""
