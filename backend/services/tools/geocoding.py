from io import BytesIO, StringIO
from os import getenv
from langchain_core.tools import tool
import requests
import json
from langgraph.types import Command

from typing_extensions import Annotated
from typing import Any, Dict, List, Optional, Union
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import InjectedState
from services.storage.file_management import store_file
from models.states import GeoDataAgentState, get_medium_debug_state, get_minimal_debug_state
from models.geodata import DataOrigin, DataType, GeoDataObject



headers_geoweaver = {
    "User-Agent": "GeoWeaver, github.com/geoweaveai, next generation geospatial analysis using agents"
}


# Note: GeoNames only returns longitude / latitude - might not be best fit for our geojson/bounding box case
@tool
def geocode_using_geonames(location: str, maxRows: int = 3) -> str:
    """
    Use for: Basic geocoding of place names (e.g., cities, countries, landmarks). Returns coordinates and bounding boxes.  
    Strengths: 
    * Provides coordinates and a well managed system of hierarchical geographic data specific to administrational units, places and landmarks.
    * Is globally consistent and represents better the official administrative units. 
    * Has mulit language support.
    * Can be used to quickly retrieve bounding boxes that can feed into other tools such as the query_librarian_postgis
    * If a user requires a map with multiple locations such as cities and landmarks shown as pointsand a low zoom level, this datasource provides adequate data for the map. 
     
    Limitations:
    * Returns only coordinates and bounding boxes. Is therefore not a good fit if user needs to actually see the boundaries of a country or city on the map
    * Has no no street-level support and cannot serve for adress-level geocoding. 
    """
    # Later * Can be used to retrieve hierarchical information on an adress e.g. country, state, city etc. which can be helpful to get more informmation on ambigous geocoding requests.
  # Later: Tool can be used for reverse geocoding e.g. if a user inputs point data and would like to have a sumamry which points fall within which administrative unit. 
    # Later: Add support for advanced querries like hierarchical querries, find nearby places, find country information, time zones, elevation etc. 
    url: str = f"http://api.geonames.org/searchJSON?q={location}&maxRows={maxRows}&username={getenv('GEONAMES_USER', 'geoweaver')}"
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
    """ Geocoding user requests using the Open Street Map Nominatim API.
    """
    # TODO: Add support for OSM tags. 
    url: str = (
        f"https://nominatim.openstreetmap.org/search?q={query}&format=json&polygon_kml={1 if geojson else 0}&addressdetails=1&limit={maxRows}"
    )
    response = requests.get(url, headers=headers_geoweaver)
    if response.status_code == 200:
        data = response.json()
        if len(data):
            return json.dumps(data)
        else:
            return "No results found."
    else:
        print(response.json())
        return "Error querying the Nominatim API."

def create_geodata_object_from_geojson(nominatim_response: Dict[str, Any]) -> Optional[GeoDataObject]:
    """Saves the GeoJson response, saves it in storage and create a GeoDataObject from it """
    if not "geojson" in nominatim_response:
        return None
    place_id: str = str(nominatim_response["place_id"])
    name: str = nominatim_response["name"]
    geojson: Dict[str, Any] = { "type": "Feature", "geometry": nominatim_response["geojson"]}

    url, unique_id = store_file(f"{place_id}_{name}.json", json.dumps(geojson).encode())
    # Copy selected properties
    properties: Dict[str, Any] = dict()
    for prop in ["place_id", "licence", "osm_type", "osm_id", "lat", "lon",  "class", "type", "place_rank", "addresstype", "address"]:
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
            properties=properties
        )
    
    return geoobject
    


@tool
def geocode_using_nominatim_to_geostate(state: Annotated[GeoDataAgentState, InjectedState], tool_call_id: Annotated[str, InjectedToolCallId],  query: str, geojson: bool = True, maxRows: int = 5) -> Union[Dict[str, Any], Command]:
    """Geocode an address using OpenStreetMap Nominatim API. Returns Bounding Box for further request and GeoJson of the area to show to the user. 
    Use for:  Geocoding specific addresses or when detailed data (e.g., place types) is needed. 
    Strengths: 
    * Provides detailed polygon data as GeoJSON (e.g. polygons of countries, states, cities) which can be used for map visualization and further analysis. 
    * For forward geocoding: Converts place names or addresses into geographic coordinates.
    * Detailed address data, including house numbers, street names, neighborhoods, and postcodes.
    * Provides the geographical extent (min/max latitude and longitude) for places, including cities, countries, and sometimes smaller features like neighborhoods
    * Categorizes results by OSM tags, indicating the type of place (e.g., city, street, building, amenity, shop)
    * Reverse geocoding: Converts geographic coordinates into detailed address information.
    Limitations:
    * Nominatim relies on crowd-sourced OSM data, so accuracy and completeness depend on community contributions.
    * Provides limited metadata. It does not include attributes like population, elevation, time zones, or weather data.
    * does not support broader geographical queries like finding nearby places, hierarchical relationships beyond administrative divisions
    """
    url: str = (
        f"https://nominatim.openstreetmap.org/search?q={query}&format=json&polygon_geojson={1 if geojson else 0}&addressdetails=0&limit={maxRows}"
    )
    response = requests.get(url, headers=headers_geoweaver)
    if response.status_code == 200:
        data = response.json()
        if len(data):
            cleaned_data: List[Dict[str, Any]] = []
            for elem in data:
                if "geojson" in elem:
                    geocoded_object: Optional[GeoDataObject] = create_geodata_object_from_geojson(elem)
                    del elem["geojson"]
                    if geocoded_object:
                        elem["id"] = geocoded_object.id
                        elem["data_source_id"] = geocoded_object.data_source_id
                        if "global_geodata" not in state or state["global_geodata"] is None or not isinstance(state["global_geodata"], List):
                            state["global_geodata"] = [geocoded_object]
                        else:
                            state["global_geodata"].append(geocoded_object)
                cleaned_data.append(dict(elem))
            if geojson:
                #return { "message": f"Retrieved {len(data)} results, added GeoDataObject into the global_state, id and data_source_id were added to the result.", "results": cleaned_data }
                return Command(update={
                    "messages": [
                        *state["messages"], 
                        ToolMessage(name="geocode_using_nominatim_to_geostate", content=f"Retrieved {len(data)} results, added GeoDataObject into the global_state, id and data_source_id were added to the following result: {json.dumps(cleaned_data)}", tool_call_id=tool_call_id )
                        ] , 
                    "global_geodata": state["global_geodata"]
                })
            else: 
                return { "message": f"Retrieved {len(data)} results.", "results": cleaned_data }
        else:
            return { "message": "No results found." }
    else:
        print(response.json())
        return { "message": "Error querying the Nominatim API." }


# Amenity mapping for Overpass API
AMENITY_MAPPING = {
    "restaurant": "amenity=restaurant",
    "restaurants": "amenity=restaurant",
    "park": "leisure=park",
    "parks": "leisure=park",
    "school": "amenity=school",
    "schools": "amenity=school",
    "hospital": "amenity=hospital",
    "hospitals": "amenity=hospital",
    "cafe": "amenity=cafe",
    "cafes": "amenity=cafe",
    "bar": "amenity=bar",
    "bars": "amenity=bar",
    "pub": "amenity=pub",
    "pubs": "amenity=pub",
    "hotel": "tourism=hotel",
    "hotels": "tourism=hotel",
    "bank": "amenity=bank",
    "banks": "amenity=bank",
    "supermarket": "shop=supermarket",
    "supermarkets": "shop=supermarket",
    "pharmacy": "amenity=pharmacy",
    "pharmacies": "amenity=pharmacy",
    "cinema": "amenity=cinema",
    "cinemas": "amenity=cinema",
    "library": "amenity=library",
    "libraries": "amenity=library",
    "police": "amenity=police",
    "fire_station": "amenity=fire_station",
    "post_office": "amenity=post_office",
    "place_of_worship": "amenity=place_of_worship",
    "bus_stop": "highway=bus_stop",
    "train_station": "railway=station",
    "airport": "aeroway=aerodrome",
    "fuel": "amenity=fuel", # Gas station
    "parking": "amenity=parking",
    "atm": "amenity=atm",
    "fast_food": "amenity=fast_food",
    "doctors": "amenity=doctors",
    "dentist": "amenity=dentist",
    "veterinary": "amenity=veterinary",
    "theatre": "amenity=theatre",
    "nightclub": "amenity=nightclub",
    "community_centre": "amenity=community_centre",
    "social_facility": "amenity=social_facility",
    "marketplace": "amenity=marketplace",
    "public_building": "amenity=public_building",
    "recycling": "amenity=recycling",
    "toilets": "amenity=toilets",
    "bench": "amenity=bench",
    "drinking_water": "amenity=drinking_water",
    "fountain": "amenity=fountain",
    "shelter": "amenity=shelter",
    "telephone": "amenity=telephone",
    "waste_basket": "amenity=waste_basket",
    "waste_disposal": "amenity=waste_disposal",
    # Leisure tags
    "playground": "leisure=playground",
    "sports_centre": "leisure=sports_centre",
    "stadium": "leisure=stadium",
    "pitch": "leisure=pitch", # Sports pitch
    "track": "leisure=track", # Sports track
    "swimming_pool": "leisure=swimming_pool",
    "golf_course": "leisure=golf_course",
    "ice_rink": "leisure=ice_rink",
    "fitness_centre": "leisure=fitness_centre",
    "garden": "leisure=garden",
    "dog_park": "leisure=dog_park",
    "nature_reserve": "leisure=nature_reserve",
    "picnic_site": "leisure=picnic_site",
    "beach_resort": "leisure=beach_resort",
    "marina": "leisure=marina",
    "water_park": "leisure=water_park",
    "fishing": "leisure=fishing",
    "common": "leisure=common", # Village green
    # Shop tags
    "bakery": "shop=bakery",
    "butcher": "shop=butcher",
    "clothes": "shop=clothes",
    "convenience": "shop=convenience",
    "department_store": "shop=department_store",
    "electronics": "shop=electronics",
    "florist": "shop=florist",
    "furniture": "shop=furniture",
    "gift": "shop=gift",
    "hairdresser": "shop=hairdresser",
    "hardware": "shop=hardware",
    "jewelry": "shop=jewelry",
    "kiosk": "shop=kiosk",
    "laundry": "shop=laundry",
    "mall": "shop=mall", # Shopping mall
    "optician": "shop=optician",
    "pet": "shop=pet", # Pet store
    "shoes": "shop=shoes",
    "sports": "shop=sports", # Sports shop
    "stationery": "shop=stationery",
    "travel_agency": "shop=travel_agency",
    "book": "shop=books",
    "books": "shop=books",
    "music": "shop=music",
    "toys": "shop=toys",
    "car_repair": "shop=car_repair",
    "car_parts": "shop=car_parts",
    "bicycle": "shop=bicycle", # Bicycle shop
    # Tourism tags
    "museum": "tourism=museum",
    "gallery": "tourism=gallery",
    "zoo": "tourism=zoo",
    "theme_park": "tourism=theme_park",
    "attraction": "tourism=attraction",
    "viewpoint": "tourism=viewpoint",
    "information": "tourism=information", # Tourist information
    "artwork": "tourism=artwork",
    "guest_house": "tourism=guest_house",
    "motel": "tourism=motel",
    "hostel": "tourism=hostel",
    "chalet": "tourism=chalet",
    "camp_site": "tourism=camp_site",
    "caravan_site": "tourism=caravan_site",
    "picnic_table": "tourism=picnic_site" # Though picnic_site is leisure, a table itself could be tourism
}

def create_geodata_object_from_overpass(feature: Dict[str, Any], query_name: str, amenity_tag_value: str) -> Optional[GeoDataObject]:
    """Creates a GeoDataObject from an Overpass API feature"""
    if not feature or "type" not in feature or "id" not in feature:
        return None

    osm_type = feature["type"]
    osm_id = str(feature["id"]) # Ensure ID is a string

    properties = feature.get("tags", {}) # Overpass returns tags directly under element, not in properties
    
    name = properties.get("name", query_name) # Use query_name if no specific name tag
    if not name and amenity_tag_value:
        name = f"{amenity_tag_value.replace('=',': ').replace('_',' ').title()} ({osm_type})"


    # Construct GeoJSON structure
    geojson_feature = {
        "type": "Feature",
        "id": f"{osm_type}/{osm_id}", # GeoJSON feature ID
        "properties": properties,
        "geometry": None # Will be filled based on type
    }

    if osm_type == "node" and "lat" in feature and "lon" in feature:
        geojson_feature["geometry"] = {
            "type": "Point",
            "coordinates": [float(feature["lon"]), float(feature["lat"])]
        }
    elif osm_type == "way" and "geometry" in feature: # Assumes geometry is pre-calculated (e.g. by "out geom;")
        # Overpass 'out geom;' provides simplified way geometries (list of lat/lon objects)
        coords = [[float(pt["lon"]), float(pt["lat"])] for pt in feature["geometry"]]
        if len(coords) > 0:
            # Check if it's a closed way (polygon)
            if coords[0][0] == coords[-1][0] and coords[0][1] == coords[-1][1] and len(coords) > 3: # First and last points are the same
                 geojson_feature["geometry"] = {
                    "type": "Polygon",
                    "coordinates": [coords] # GeoJSON Polygon needs a list of linear rings
                }
            elif len(coords) > 1: # Must have at least two points for a LineString
                geojson_feature["geometry"] = {
                    "type": "LineString",
                    "coordinates": coords
                }
            else: # Not enough points for a valid geometry
                 return None 
        else: # No coordinates
            return None

    elif osm_type == "relation":
        # For relations, geometry is more complex and might not be directly available without further processing
        # or specific Overpass query constructs (like `out geom;`).
        # We'll skip relations if no simple geometry is present.
        # A more robust solution would involve parsing members if `out geom;` was used for relations.
        # For now, we'll only create objects for relations if they have a center point from `out center;`
        if "center" in feature and "lat" in feature["center"] and "lon" in feature["center"]:
             geojson_feature["geometry"] = {
                "type": "Point",
                "coordinates": [float(feature["center"]["lon"]), float(feature["center"]["lat"])]
            }
        else: # No usable geometry for relation
            return None
    else: # Unknown type or missing geometry
        return None

    if not geojson_feature["geometry"]:
        return None

    # Store the GeoJSON
    file_name_prefix = amenity_tag_value.split('=')[1] if amenity_tag_value else osm_type
    
    url, unique_id = store_file(f"overpass_{file_name_prefix}_{osm_id}.json", json.dumps(geojson_feature).encode())
    
    # Create description from tags
    tags_description = ", ".join([f"{k}: {v}" for k, v in properties.items() if v])
    description = f"OSM {osm_type} {osm_id}"
    if tags_description:
        description += f": {tags_description}"
    
    # Calculate bounding box for the GeoJSON feature
    bounding_box_str = None
    if geojson_feature["geometry"]:
        geom_type = geojson_feature["geometry"]["type"]
        coords = geojson_feature["geometry"]["coordinates"]
        
        all_lons: List[float] = []
        all_lats: List[float] = []

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

        if all_lons and all_lats:
            min_lon, max_lon = min(all_lons), max(all_lons)
            min_lat, max_lat = min(all_lats), max(all_lats)
            
            # Create a small buffer for points to make them visible
            if geom_type == "Point":
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
            
    geoobject = GeoDataObject(
        id=unique_id,
        data_source_id="geocodeOverpass",
        data_type=DataType.GEOJSON,
        data_origin=DataOrigin.TOOL,
        data_source="OpenStreetMap contributors",
        data_link=url,
        name=str(name), # Ensure name is a string
        title=str(name), # Ensure title is a string
        description=description,
        llm_description=description, # Can be improved by LLM later
        score=0.8,  # Default score, can be adjusted based on tags or importance
        bounding_box=bounding_box_str,
        layer_type="GeoJSON", # Could be more specific (Point, Polygon, LineString)
        properties=properties
    )
    
    return geoobject


@tool
def geocode_using_overpass_to_geostate(
    state: Annotated[GeoDataAgentState, InjectedState], 
    tool_call_id: Annotated[str, InjectedToolCallId], 
    query: str, 
    amenity_key: str, # e.g. "restaurant", "park", "hospital" - to be mapped to OSM tags
    location_name: str, # e.g. "Paris", "London", "near the Colosseum"
    radius_meters: int = 10000, # Default search radius around a point, e.g. 10km
    max_results: int = 20, # Max results from Overpass
    timeout: int = 30  # Default timeout in seconds
) -> Union[Dict[str, Any], Command]:
    """
    Search for specific amenities (e.g., restaurants, parks, schools) near a given location using OpenStreetMap's Overpass API.

    This tool first geocodes the 'location_name' to get coordinates. Then, it searches for the specified 'amenity_key'
    within a 'radius_meters' around that location. Results are returned as GeoJSON and added to the map.

    Use for: Finding amenities like "restaurants in Paris", "hospitals near the Colosseum", "parks in London".
    
    Strengths:
    * Powerful querying for specific amenity types using OSM tags.
    * Returns detailed attribute information from OpenStreetMap.
    * Integrates with existing geocoding to resolve location names.
    * Returns GeoJSON data that can be displayed on the map.
    
    Parameters:
    * query: The original user query (e.g., "Show me all restaurants in Paris").
    * amenity_key: The type of amenity to search for, extracted from the user query (e.g., "restaurant", "park"). This will be mapped to OSM tags.
    * location_name: The name of the location to search within or near (e.g., "Paris", "Colosseum"). This will be geocoded.
    * radius_meters: The search radius in meters around the geocoded location point. Default is 10000 meters (10 km).
    * max_results: Maximum number of results to request from Overpass API (default: 20).
    * timeout: Query timeout in seconds for Overpass API (default: 30).
    
    Limitations:
    * Accuracy depends on the geocoding of 'location_name' and OSM data quality.
    * Complex or very broad queries might be slow or time out.
    * Currently uses a simple radius search around a geocoded point. For searching within a named area (e.g. "all parks in Berlin city"), a bounding box approach might be better but requires the geocoding tool to return a bbox reliably.
    """
    
    # 1. Map amenity_key to OSM tag
    osm_tag_kv = AMENITY_MAPPING.get(amenity_key.lower().replace(" ", "_"))
    if not osm_tag_kv:
        return Command(update={
            "messages": [
                *state["messages"],
                ToolMessage(name="geocode_using_overpass_to_geostate", content=f"Sorry, I don't know how to search for '{amenity_key}'. Please try a common amenity type.", tool_call_id=tool_call_id)
            ]
        })
    
    # 2. Geocode location_name to get coordinates
    # For simplicity, we'll use the existing nominatim tool directly here.
    # A more robust solution might involve calling it as part of the agent flow or having a dedicated geocoding function.
    nominatim_url = f"https://nominatim.openstreetmap.org/search?q={location_name}&format=json&limit=1"
    try:
        nominatim_response = requests.get(nominatim_url, headers=headers_geoweaver, timeout=10)
        nominatim_response.raise_for_status()
        location_data = nominatim_response.json()
        if not location_data:
            return Command(update={
                "messages": [
                    *state["messages"],
                    ToolMessage(name="geocode_using_overpass_to_geostate", content=f"Could not find location: {location_name}", tool_call_id=tool_call_id)
                ]
            })
        
        lat = float(location_data[0]["lat"])
        lon = float(location_data[0]["lon"])
        resolved_location_display_name = location_data[0].get("display_name", location_name)

    except requests.exceptions.RequestException as e:
        return Command(update={
            "messages": [
                *state["messages"],
                ToolMessage(name="geocode_using_overpass_to_geostate", content=f"Error geocoding '{location_name}': {str(e)}", tool_call_id=tool_call_id)
            ]
        })
    except (KeyError, IndexError, ValueError):
        return Command(update={
            "messages": [
                *state["messages"],
                ToolMessage(name="geocode_using_overpass_to_geostate", content=f"Could not parse geocoding result for: {location_name}", tool_call_id=tool_call_id)
            ]
        })

    # 3. Construct Overpass API query
    # Example: [amenity=restaurant]
    key, value = osm_tag_kv.split('=')
    
    # Query for nodes, ways, and relations within the radius around the geocoded point.
    # "out geom;" is used to get coordinates for ways.
    # "out center;" for relations provides a center point if full geometry is too complex.
    overpass_query = f"""
    [out:json][timeout:{timeout}];
    (
      node["{key}"="{value}"](around:{radius_meters},{lat},{lon});
      way["{key}"="{value}"](around:{radius_meters},{lat},{lon});
      relation["{key}"="{value}"](around:{radius_meters},{lat},{lon});
    );
    out geom {max_results}; 
    """ 
    # Note: Using 'out geom;' can be heavy. For ways, it returns geometry. For relations, it's complex.
    # 'out center;' is a lighter alternative for relations if only a point marker is needed.
    # For production, consider 'out body; >; out skel qt;' then reconstruct GeoJSON, or simplify queries.
    # The current 'out geom' will fetch geometries for nodes and ways, and attempt for relations.

    # 4. Execute Overpass API query
    overpass_api_url = "https://overpass-api.de/api/interpreter"
    try:
        api_response = requests.post(
            overpass_api_url,
            data={"data": overpass_query},
            headers={**headers_geoweaver, "Content-Type": "application/x-www-form-urlencoded"},
            timeout=timeout + 5 # Allow slightly more timeout for the request itself
        )
        api_response.raise_for_status()
        overpass_data = api_response.json()
    except requests.exceptions.Timeout:
        return Command(update={
            "messages": [
                *state["messages"],
                ToolMessage(name="geocode_using_overpass_to_geostate", content=f"Overpass API query for '{amenity_key}' near '{resolved_location_display_name}' timed out after {timeout} seconds.", tool_call_id=tool_call_id)
            ]
        })
    except requests.exceptions.HTTPError as e:
        error_detail = e.response.text[:500] if e.response else str(e)
        # Check for specific Overpass error messages if possible
        if "runtime error: Query timed out" in error_detail or "runtime error: load_query" in error_detail :
             error_message_content = f"Overpass API query for '{amenity_key}' near '{resolved_location_display_name}' was too complex or timed out. Try a smaller radius or more specific location. Details: {error_detail}"
        else:
            error_message_content = f"Overpass API error for '{amenity_key}' near '{resolved_location_display_name}'. Status: {e.response.status_code if e.response else 'N/A'}. Details: {error_detail}"
        
        return Command(update={
            "messages": [
                *state["messages"],
                ToolMessage(name="geocode_using_overpass_to_geostate", content=error_message_content, tool_call_id=tool_call_id)
            ]
        })
    except requests.exceptions.RequestException as e:
        return Command(update={
            "messages": [
                *state["messages"],
                ToolMessage(name="geocode_using_overpass_to_geostate", content=f"Error connecting to Overpass API: {str(e)}", tool_call_id=tool_call_id)
            ]
        })
    except json.JSONDecodeError:
        return Command(update={
            "messages": [
                *state["messages"],
                ToolMessage(name="geocode_using_overpass_to_geostate", content=f"Error parsing Overpass API response. Response was: {api_response.text[:200]}...", tool_call_id=tool_call_id)
            ]
        })

    # 5. Convert API response to GeoJSON and add to state
    if "elements" not in overpass_data or not overpass_data["elements"]:
        return Command(update={
            "messages": [
                *state["messages"],
                ToolMessage(name="geocode_using_overpass_to_geostate", content=f"No '{amenity_key}' found near '{resolved_location_display_name}' (within {radius_meters}m).", tool_call_id=tool_call_id)
            ]
        })

    created_geo_objects: List[GeoDataObject] = []
    processed_ids = set() # To avoid duplicates if elements are referenced multiple times

    for element in overpass_data["elements"]:
        # Ensure we have type and id for the element
        if "type" not in element or "id" not in element:
            continue
        
        element_unique_id = f"{element['type']}/{element['id']}"
        if element_unique_id in processed_ids:
            continue
        
        # We are interested in elements that directly match the tag, not just their components unless 'out geom' brings them.
        # For 'out geom', nodes that are part of ways/relations might appear without the primary tags.
        # We only want to create GeoDataObjects for the primary features (nodes, ways, relations with the amenity tag).
        if not (element.get("tags") and element["tags"].get(key) == value) and element['type'] != 'node':
            # If it's a node, it might be part of a way and its geometry is needed.
            # However, we only create a GeoDataObject if it's a primary feature.
            # The create_geodata_object_from_overpass will handle geometry creation.
            # For now, let's be strict: only convert if tags match, or if it's a node that's part of a way from 'out geom'
            # This logic is simplified; 'out geom' might require more sophisticated parsing to reconstruct ways/relations
            # from their constituent nodes.
             pass # Let create_geodata_object_from_overpass handle it, it might be a geometry node

        geo_object = create_geodata_object_from_overpass(element, query_name=f"{amenity_key} near {location_name}", amenity_tag_value=osm_tag_kv)
        if geo_object:
            created_geo_objects.append(geo_object)
            processed_ids.add(element_unique_id)
            if len(created_geo_objects) >= max_results: # Respect max_results for created objects
                break 
                
    if not created_geo_objects:
         return Command(update={
            "messages": [
                *state["messages"],
                ToolMessage(name="geocode_using_overpass_to_geostate", content=f"No '{amenity_key}' found with parsable geometry near '{resolved_location_display_name}' (within {radius_meters}m).", tool_call_id=tool_call_id)
            ]
        })

    current_geodata = state.get("global_geodata", [])
    if not isinstance(current_geodata, list): # Ensure it's a list
        current_geodata = []
    current_geodata.extend(created_geo_objects)

    # 6. Return success message
    summary_results = [{"name": obj.name, "osm_id": obj.properties.get("id", f"{obj.properties.get('type')}/{obj.properties.get('id')}") if obj.properties else "N/A", "id": obj.id} for obj in created_geo_objects]

    return Command(update={
        "messages": [
            *state["messages"],
            ToolMessage(
                name="geocode_using_overpass_to_geostate", 
                content=f"Found {len(created_geo_objects)} '{amenity_key}' near '{resolved_location_display_name}'. Added to map. Results: {json.dumps(summary_results)}",
                tool_call_id=tool_call_id
            )
        ],
        "global_geodata": current_geodata
    })


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

if __name__ == "__main__":
    initial_state: GeoDataAgentState = get_minimal_debug_state(True)
    #print(geocode_using_nominatim.invoke({"query": "Frankfurt", "geojson": True}))
    #print(geocode_using_geonames.invoke({"query": "Frankfurt"}))
    #print(initial_state)
    # print(geocode_using_nominatim_to_geostate.invoke({"state": initial_state, "query": "New York", "geojson": True}))
    # print(geocode_using_nominatim_to_geostate.invoke({'args': {"state": initial_state,  'tool_call_id': 'testcallid1234', "query": "New York", "geojson": True}, 'name': 'geocode_nominatim', 'type': 'tool_call', 'id': 'id2',  'tool_call_id': 'testcallid1234'}))
    
    # Test the Overpass API geocoder with amenities
    print("\n--- Testing Overpass API Geocoder ---")
    overpass_test_state = get_minimal_debug_state(True)
    
    # Test 1: Restaurants in Eiffel Tower (should find some)
    print("\nTest 1: Restaurants near Eiffel Tower")
    tool_call_id_test1 = "overpass_test_eiffel_restaurants"
    args_test1 = {
        "state": overpass_test_state,
        "tool_call_id": tool_call_id_test1,
        "query": "restaurants near Eiffel Tower",
        "amenity_key": "restaurants",
        "location_name": "Eiffel Tower Paris",
        "radius_meters": 1000, # 1 km radius
        "max_results": 5 
    }
    result1 = geocode_using_overpass_to_geostate.invoke(args_test1)
    print(f"Result for Test 1: {result1['messages'][-1].content if isinstance(result1, Command) else result1}")
    if isinstance(result1, Command) and result1.update.get("global_geodata"):
        print(f"GeoData objects created: {len(result1.update['global_geodata'])}")
        # for obj in result1.update['global_geodata']:
        #     print(f"  - {obj.name} (ID: {obj.id}, OSM ID: {obj.properties.get('id') if obj.properties else 'N/A'})")


    # Test 2: Unknown amenity (should return a "don't know how to search" message)
    print("\nTest 2: Flobberworms in London")
    tool_call_id_test2 = "overpass_test_unknown_amenity"
    overpass_test_state_2 = get_minimal_debug_state(True) # Fresh state
    args_test2 = {
        "state": overpass_test_state_2,
        "tool_call_id": tool_call_id_test2,
        "query": "Flobberworms in London",
        "amenity_key": "Flobberworms",
        "location_name": "London",
    }
    result2 = geocode_using_overpass_to_geostate.invoke(args_test2)
    print(f"Result for Test 2: {result2['messages'][-1].content if isinstance(result2, Command) else result2}")

    # Test 3: Invalid location (should return "Could not find location")
    print("\nTest 3: Cafes in Narnia")
    tool_call_id_test3 = "overpass_test_invalid_location"
    overpass_test_state_3 = get_minimal_debug_state(True) # Fresh state
    args_test3 = {
        "state": overpass_test_state_3,
        "tool_call_id": tool_call_id_test3,
        "query": "Cafes in Narnia",
        "amenity_key": "cafe",
        "location_name": "Narnia" 
    }
    result3 = geocode_using_overpass_to_geostate.invoke(args_test3)
    print(f"Result for Test 3: {result3['messages'][-1].content if isinstance(result3, Command) else result3}")

    # Test 4: Hospitals in a specific city (Berlin)
    print("\nTest 4: Hospitals in Berlin")
    tool_call_id_test4 = "overpass_test_hospitals_berlin"
    overpass_test_state_4 = get_minimal_debug_state(True) # Fresh state
    args_test4 = {
        "state": overpass_test_state_4,
        "tool_call_id": tool_call_id_test4,
        "query": "hospitals in Berlin",
        "amenity_key": "hospital",
        "location_name": "Berlin, Germany",
        "radius_meters": 20000, # 20 km radius for a city
        "max_results": 10
    }
    result4 = geocode_using_overpass_to_geostate.invoke(args_test4)
    print(f"Result for Test 4: {result4['messages'][-1].content if isinstance(result4, Command) else result4}")
    if isinstance(result4, Command) and result4.update.get("global_geodata"):
         print(f"GeoData objects created for Berlin hospitals: {len(result4.update['global_geodata'])}")


    # Test 5: Query that might timeout or be too broad if radius is huge
    # print("\nTest 5: Parks in Germany (large area, might timeout or be too complex with default settings)")
    # tool_call_id_test5 = "overpass_test_parks_germany"
    # overpass_test_state_5 = get_minimal_debug_state(True)
    # args_test5 = {
    #     "state": overpass_test_state_5,
    #     "tool_call_id": tool_call_id_test5,
    #     "query": "parks in Germany",
    #     "amenity_key": "park",
    #     "location_name": "Germany", # Geocodes to center of Germany
    #     "radius_meters": 500000, # Very large radius: 500 km
    #     "max_results": 5,
    #     "timeout": 20 # Shorter timeout to test error handling
    # }
    # result5 = geocode_using_overpass_to_geostate.invoke(args_test5)
    # print(f"Result for Test 5: {result5['messages'][-1].content if isinstance(result5, Command) else result5}")
    
    # Test 6: Amenity key not in mapping, but a common word
    print("\nTest 6: Find 'shop' near Buckingham Palace")
    tool_call_id_test6 = "overpass_test_shop_buckingham"
    overpass_test_state_6 = get_minimal_debug_state(True)
    args_test6 = {
        "state": overpass_test_state_6,
        "tool_call_id": tool_call_id_test6,
        "query": "shops near Buckingham Palace",
        "amenity_key": "shop", # This key itself isn't in AMENITY_MAPPING directly for a specific tag like "shop=yes"
        "location_name": "Buckingham Palace, London",
        "radius_meters": 1000,
        "max_results": 3
    }
    result6 = geocode_using_overpass_to_geostate.invoke(args_test6)
    print(f"Result for Test 6: {result6['messages'][-1].content if isinstance(result6, Command) else result6}")
    # Expected: "Sorry, I don't know how to search for 'shop'." because "shop" itself is not a specific mapping.
    # Users should specify "supermarket", "clothes", etc. or the LLM should map "shops" to a broader query if desired.

    # Test 7: More specific shop type
    print("\nTest 7: Find 'book stores' near British Museum")
    tool_call_id_test7 = "overpass_test_bookstore_bm"
    overpass_test_state_7 = get_minimal_debug_state(True)
    args_test7 = {
        "state": overpass_test_state_7,
        "tool_call_id": tool_call_id_test7,
        "query": "book stores near British Museum",
        "amenity_key": "books", 
        "location_name": "British Museum, London",
        "radius_meters": 1000,
        "max_results": 3
    }
    result7 = geocode_using_overpass_to_geostate.invoke(args_test7)
    print(f"Result for Test 7: {result7['messages'][-1].content if isinstance(result7, Command) else result7}")
    if isinstance(result7, Command) and result7.update.get("global_geodata"):
         print(f"GeoData objects created for bookstores: {len(result7.update['global_geodata'])}")
