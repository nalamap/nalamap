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
    for property in ["place_id", "licence", "osm_type", "osm_id", "lat", "lon",  "class", "type", "place_rank", "addresstype", "address"]:
        if property in nominatim_response:
            properties[property] = nominatim_response[property]
    
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
                cleaned_data.append(elem)
            if geojson:
                #return { "message": f"Retrieved {len(data)} results, added GeoDataObject into the global_state, id and data_source_id were added to the result.", "results": cleaned_data }
                return Command(update={
                    "messages": [
                        *state["messages"], 
                        ToolMessage(f"Retrieved {len(data)} results, added GeoDataObject into the global_state, id and data_source_id were added to the following result: {json.dumps(cleaned_data)}", tool_call_id=tool_call_id )
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
    print(initial_state)
    # print(geocode_using_nominatim_to_geostate.invoke({"state": initial_state, "query": "New York", "geojson": True}))
    print(geocode_using_nominatim_to_geostate.invoke({'args': {"state": initial_state,  'tool_call_id': 'testcallid1234', "query": "New York", "geojson": True}, 'name': 'geocode_nominatim', 'type': 'tool_call', 'id': 'id2',  'tool_call_id': 'testcallid1234'}))
    print(initial_state)