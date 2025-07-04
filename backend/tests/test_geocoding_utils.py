import pytest
from services.tools.geocoding import convert_osm_element_to_geojson_feature


def test_convert_node_to_feature():
    element = {
        "type": "node",
        "id": 1,
        "lat": 10.0,
        "lon": 20.0,
        "tags": {"name": "sample"},
    }
    feature = convert_osm_element_to_geojson_feature(element)
    assert feature == {
        "type": "Feature",
        "id": "node/1",
        "properties": {"name": "sample"},
        "geometry": {"type": "Point", "coordinates": [20.0, 10.0]},
    }


def test_convert_way_polygon_feature():
    element = {
        "type": "way",
        "id": 2,
        "geometry": [
            {"lon": 0, "lat": 0},
            {"lon": 1, "lat": 0},
            {"lon": 1, "lat": 1},
            {"lon": 0, "lat": 0},
        ],
        "tags": {},
    }
    feature = convert_osm_element_to_geojson_feature(element)
    assert feature["geometry"]["type"] == "Polygon"
    assert feature["geometry"]["coordinates"][0][0] == [0.0, 0.0]


def test_filter_is_non_strict():
    element = {
        "type": "node",
        "id": 3,
        "lat": 5,
        "lon": 5,
        "tags": {"amenity": "cafe"},
    }
    feature = convert_osm_element_to_geojson_feature(element, "amenity=restaurant")
    assert feature is not None
