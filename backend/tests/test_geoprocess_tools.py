# tests/test_chat_integration.py

import json
import os
from types import SimpleNamespace

import geopandas as gpd
import pytest
import requests
from fastapi.testclient import TestClient
from shapely.geometry import shape

from core.config import BASE_URL, LOCAL_UPLOAD_DIR
from main import app  # wherever your FastAPI instance lives

# ensure LOCAL_UPLOAD_DIR exists for test
os.makedirs(LOCAL_UPLOAD_DIR, exist_ok=True)


@pytest.fixture
def client():
    return TestClient(app)


# @pytest.fixture
# def stub_llm(monkeypatch):
#    """
#    Returns a helper that lets your test specify ANY LLM JSON response.
#    Usage in a test:
#
#        # In your test body:
#        stub_llm('{"steps":[{"operation":"union","params":{}}]}')
#    """
#    def _stub(response_text: str):
#        class FakeLLM:
#            def generate(self, _messages_batch):
#                fake = SimpleNamespace(text=response_text)
#                return SimpleNamespace(generations=[[fake]])
#        monkeypatch.setattr(llm_config, "get_llm", lambda: FakeLLM())
#    return _stub
#


@pytest.fixture(autouse=True)
def stub_requests(monkeypatch):
    """
    Returns a helper that lets your test specify ANY number of GeoJSONs
    to be returned by requests.get(), keyed by a substring of the URL.
    Usage in a test:
        # pass a dict mapping URL‐keys to GeoJSON dicts
        stub_requests({
            "aoi.geojson": aoi_geojson,
            "greenland.geojson": greenland_geojson,
        })
    """

    def _stub(mapping: dict[str, dict], status_code: int = 200):
        def fake_get(url, timeout=10):
            for key, sample in mapping.items():
                if key in url:
                    return SimpleNamespace(
                        status_code=status_code, json=lambda sample=sample: sample
                    )
            raise RuntimeError("No stub defined for URL: {url!r}")

        monkeypatch.setattr(requests, "get", fake_get)

    return _stub


# def test_buffer_endpoint_creates_buffered_result(client):
#    # Prepare payload
#    payload = {
#        "messages": [
#            {
#                "type": "human",
#                "content": "buffer the points by 100 meters of layer with id=layer1",
#            }
#        ],
#        "options": {},
#        "query": "buffer the points by 100 meters of layer with id=layer1",
#        "geodata_last_results": [],
#        "geodata_layers": [
#            {
#                "id": "layer1",
#                "data_source_id": "test",
#                "data_type": "GeoJson",
#                "data_origin": "TOOL",
#                "data_source": "test",
#                "data_link": "http://localhost:8000/upload/points_simple.geojson",
#                "name": "pt",
#                "title": "pt",
#                "description": "",
#                "llm_description": "",
#                "score": 0,
#                "bounding_box": None,
#                "layer_type": "GeoJSON",
#                "properties": {},
#            }
#        ],
#    }
#
#    # Call the API
#    resp = client.post("/api/chat", json=payload)
#    assert resp.status_code == 200, resp.text
#
#    body = resp.json()
#    # Check that one buffered layer was returned
#    assert "geodata_results" in body
#    results = body["geodata_results"]
#    assert isinstance(results, list) and len(results) == 1
#
#    # The returned GeoDataObject should point to our LOCAL_UPLOAD_DIR via BASE_URL
#    link = results[0]["data_link"]
#    assert link.startswith(BASE_URL)
#
#    # And the file should actually exist on disk
#    filename = link.split("/")[-1]
#    saved_path = os.path.join(LOCAL_UPLOAD_DIR, filename)
#    assert os.path.isfile(saved_path)
#
#    # Verify that the saved GeoJSON is a polygon (buffer of a point)
#    with open(saved_path) as f:
#        gj = json.load(f)
#    assert gj["type"] == "FeatureCollection"
#    assert len(gj["features"]) >= 1
#    geom = gj["features"][0]["geometry"]
#    assert geom["type"] == "Polygon"


def test_chat_buffer_line_expected_result(client, stub_requests):
    line = {
        "type": "FeatureCollection",
        "name": "line",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
        },
        "features": [
            {
                "type": "Feature",
                "properties": {"id": 1, "name": "Unter den Linden Boulevard"},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [13.3778, 52.5163],
                        [13.39, 52.517],
                        [13.4, 52.518],
                    ],
                },
            }
        ],
    }

    output_line = {
        "type": "FeatureCollection",
        "name": "line_buffer_500m",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
        },
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": 1,
                    "name": "Unter den Linden Boulevard 500m Buffer",
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [13.389424328846832, 52.519712249946679],
                            [13.399271653204945, 52.520696921764923],
                            [13.399709585028491, 52.520727375039968],
                            [13.40015031370697, 52.520731563006969],
                            [13.400589594782282, 52.520709445341005],
                            [13.401023197737533, 52.520661235007864],
                            [13.401446946739235, 52.52058739621453],
                            [13.401856760852858, 52.520488639941938],
                            [13.402248693344458, 52.520365917102659],
                            [13.402618969689891, 52.520220409389466],
                            [13.402964023925538, 52.520053517902447],
                            [13.403280532990477, 52.519866849664083],
                            [13.403565448729399, 52.519662202151686],
                            [13.403816027247984, 52.519441545995974],
                            [13.404029855338118, 52.519207006011875],
                            [13.404204873718401, 52.518960840744072],
                            [13.404339396866161, 52.518705420723734],
                            [13.404432129249942, 52.518443205645802],
                            [13.4044821778062, 52.518176720686114],
                            [13.404489060539975, 52.51790853218634],
                            [13.40445271116678, 52.517641222940838],
                            [13.40437347975095, 52.517377367323249],
                            [13.40425212933433, 52.517119506492229],
                            [13.40408982858777, 52.516870123915588],
                            [13.403888140556184, 52.516631621448155],
                            [13.403649007605566, 52.516406296194361],
                            [13.403374732716957, 52.516196318378285],
                            [13.403067957307465, 52.516003710434873],
                            [13.402731635791991, 52.51583032752378],
                            [13.402369007130572, 52.515677839653918],
                            [13.401983563635456, 52.515547715591325],
                            [13.401579017338204, 52.515441208705433],
                            [13.401159264240807, 52.515359344890705],
                            [13.400728346795052, 52.5153029126799],
                            [13.390728346795052, 52.514302851294701],
                            [13.390421630915364, 52.514278743766518],
                            [13.378221630915364, 52.513578700413305],
                            [13.377781293178932, 52.513566654071688],
                            [13.377341135599414, 52.513580932160338],
                            [13.376905397134914, 52.513621397147915],
                            [13.376478274185047, 52.513687659262921],
                            [13.376063880177304, 52.51377908025006],
                            [13.375666205952514, 52.513894779521486],
                            [13.375289081330852, 52.514033642643177],
                            [13.374936138228584, 52.514194332074787],
                            [13.374610775680717, 52.514375300059029],
                            [13.374316127106454, 52.514574803536291],
                            [13.374055030132633, 52.514790920940385],
                            [13.373829999265846, 52.515021570713529],
                            [13.37364320167635, 52.515264531361595],
                            [13.373496436327049, 52.515517462856536],
                            [13.373391116648484, 52.51577792917908],
                            [13.373328256926737, 52.516043421784815],
                            [13.373308462535288, 52.516311383767061],
                            [13.373331924104948, 52.516579234483928],
                            [13.373398415687976, 52.51684439441209],
                            [13.373507296934079, 52.517104309988085],
                            [13.373657519257341, 52.517356478197691],
                            [13.373847635934661, 52.517598470677008],
                            [13.374075816038513, 52.517827957092933],
                            [13.374339862069759, 52.51804272757839],
                            [13.374637231120781, 52.518240714006438],
                            [13.374965059365053, 52.518420009898534],
                            [13.375320189637373, 52.518578888775849],
                            [13.37569920183909, 52.51871582077699],
                            [13.37609844587551, 52.518829487382625],
                            [13.376514076808313, 52.518918794105417],
                            [13.376942091884407, 52.518982881023504],
                            [13.377378369084637, 52.519021131056192],
                            [13.389424328846832, 52.519712249946679],
                        ]
                    ],
                },
            }
        ],
    }
    stub_requests({"line.geojson": line})

    payload = {
        "messages": [
            {
                "type": "human",
                "content": "buffer the line by 500 meters of geodata_layers with id=layer2",
            }
        ],
        "options": {},
        "query": "buffer the line by 500 meters of geodata_layers with id=layer2",
        "geodata_last_results": [],
        "geodata_layers": [
            {
                "id": "layer2",
                "data_source_id": "test",
                "data_type": "GeoJson",
                "data_origin": "TOOL",
                "data_source": "test",
                "data_link": "http://localhost:8000/upload/line.geojson",
                "name": "pt",
                "title": "pt",
                "description": "",
                "llm_description": "",
                "score": 0,
                "bounding_box": None,
                "layer_type": "GeoJSON",
                "properties": {},
            }
        ],
    }

    resp = client.post("/api/chat", json=payload)
    assert resp.status_code == 200

    body = resp.json()
    print(body)
    # Check that one buffered layer was returned
    assert "geodata_results" in body
    results = body["geodata_results"]
    assert isinstance(results, list) and len(results) == 1
    # The returned GeoDataObject should point to our LOCAL_UPLOAD_DIR via BASE_URL
    result_link = results[0]["data_link"]
    assert result_link.startswith(BASE_URL)
    filename = result_link.split("/")[-1]
    saved_path = os.path.join(LOCAL_UPLOAD_DIR, filename)
    assert os.path.isfile(saved_path)

    with open(saved_path) as f:
        result_gj = json.load(f)

    # 3) build Shapely geometries for actual and expected
    actual = shape(result_gj["features"][0]["geometry"])

    # your expected geometry dict (output_line) should be in scope here:
    expected = shape(output_line["features"][0]["geometry"])

    # 4) wrap them in GeoSeries
    actual_series = gpd.GeoSeries([actual], crs="EPSG:4326")
    expected_series = gpd.GeoSeries([expected], crs="EPSG:4326")
    print(actual_series)
    print(expected_series)
    # 5a) using almost_equals with decimal precision:
    #    returns a boolean Series; assert all True
    assert actual_series.geom_equals_exact(expected_series, tolerance=0.0015).all()


def test_chat_overlay_intersection_expected_area(client, stub_requests):
    pathaoi = os.path.join(os.path.dirname(__file__), "testdata", "aoi.json")
    with open(pathaoi) as f:
        aoi = json.load(f)

    pathgreenland = os.path.join(os.path.dirname(__file__), "testdata", "greenland.json")
    with open(pathgreenland) as f:
        greenland = json.load(f)

    path_inter_greenland = os.path.join(
        os.path.dirname(__file__), "testdata", "intersection_greenland_aoi.json"
    )
    with open(path_inter_greenland) as f:
        intersection = json.load(f)

    stub_requests(
        {
            "aoi.geojson": aoi,
            "greenland.geojson": greenland,
        }
    )

    payload = {
        "messages": [
            {
                "type": "human",
                "content": "do the operation overlay with how=intersection and crs=EPSG:3413 on both layers with id=layer3 and id=layer4, both layers are already available in your state",
            }
        ],
        "options": {},
        "query": "do the operation overlay with intersection and EPSG:3413 on both layers with id=layer3 and id=layer4, both layers are already available in your state",
        "geodata_last_results": [],
        "geodata_layers": [
            {
                "id": "layer3",
                "data_source_id": "test",
                "data_type": "GeoJson",
                "data_origin": "TOOL",
                "data_source": "test",
                "data_link": "http://localhost:8000/upload/greenland.geojson",
                "name": "greenland",
                "title": "greenland",
                "description": "",
                "llm_description": "",
                "score": 0,
                "bounding_box": None,
                "layer_type": "GeoJSON",
                "properties": {},
            },
            {
                "id": "layer4",
                "data_source_id": "test",
                "data_type": "GeoJson",
                "data_origin": "TOOL",
                "data_source": "test",
                "data_link": "http://localhost:8000/upload/aoi.geojson",
                "name": "aoi",
                "title": "aoi",
                "description": "",
                "llm_description": "",
                "score": 0,
                "bounding_box": None,
                "layer_type": "GeoJSON",
                "properties": {},
            },
        ],
    }

    resp = client.post("/api/chat", json=payload)
    assert resp.status_code == 200

    body = resp.json()
    # Check that one buffered layer was returned
    assert "geodata_results" in body
    results = body["geodata_results"]
    # The returned GeoDataObject should point to our LOCAL_UPLOAD_DIR via BASE_URL
    result_link = results[0]["data_link"]
    print(results)
    assert result_link.startswith(BASE_URL)
    filename = result_link.split("/")[-1]
    saved_path = os.path.join(LOCAL_UPLOAD_DIR, filename)
    assert os.path.isfile(saved_path)

    with open(saved_path) as f:
        result_gj = json.load(f)

    # 3) build Shapely geometries for actual and expected
    actual = shape(result_gj["features"][0]["geometry"])
    actual_gdf = gpd.GeoDataFrame.from_features(result_gj)
    actual_gdf.set_crs("EPSG:4326", inplace=True)
    actual_gdf.to_crs("EPSG:3413", inplace=True)
    # your expected geometry dict (output_line) should be in scope here:
    expected = shape(intersection["features"][0]["geometry"])

    # 4) wrap them in GeoSeries
    actual_series = gpd.GeoSeries([actual], crs="EPSG:4326")
    actual_series.to_crs("EPSG:3413")
    area_actual = actual_gdf.area.iloc[0]
    area_actual_sq_km = area_actual / 1000000
    print(area_actual_sq_km)
    expected_series = gpd.GeoSeries([expected], crs="EPSG:4326")
    # 5a) using almost_equals with decimal precision:
    #    returns a boolean Series; assert all True
    assert actual_series.geom_equals_exact(expected_series, tolerance=100).all()
