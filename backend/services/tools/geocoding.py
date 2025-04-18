from os import getenv
from langchain_core.tools import tool
import requests
import json

headers_geoweaver = {
    "User-Agent": "GeoWeaver, github.com/geoweaveai, next generation geospatial analysis using agents"
}


# Note: GeoNames only returns longitude / latitude - might not be best fit for our geojson/bounding box case
@tool
def geocode_using_geonames(location: str, maxRows: int = 3) -> str:
    """
    Geocode a location to get the responding bounding box using the GeoNames API. 
    """
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
    """Geocode an address using OpenStreetMap Nominatim API ."""
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
    print(geocode_using_nominatim.invoke({"query": "Frankfurt", "geojson": True}))
    print(geocode_using_geonames.invoke({"query": "Frankfurt"}))