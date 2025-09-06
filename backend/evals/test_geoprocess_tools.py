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
    """
    Provide a TestClient for the FastAPI app, allowing HTTP requests to the test server.

    Returns:
        fastapi.testclient.TestClient: Client configured for the application.
    """
    return TestClient(app)


@pytest.fixture(autouse=True)
def stub_requests(monkeypatch):
    """
    Automatically stub out requests.get() calls to return predefined GeoJSON samples.

    The returned helper `_stub` accepts a mapping from URL substring keys to GeoJSON dicts.
    When the application code calls requests.get(url), if a substring match is found, the stub
    returns a SimpleNamespace with the configured status_code and .json() method.
    Intercepts the requests.get calls() where key names are found and provides own geojson.

    Yields:
        function: A helper to configure URL->GeoJSON stubs for each test case.
    """

    def _stub(mapping: dict[str, dict], status_code: int = 200):
        def fake_get(url, timeout=10):
            for key, sample in mapping.items():
                if key in url:
                    return SimpleNamespace(
                        status_code=status_code,
                        json=lambda sample=sample: sample,
                    )
            raise RuntimeError(f"No stub defined for URL: {url!r}")

        monkeypatch.setattr(requests, "get", fake_get)

    return _stub


# Load test cases definitions from testdata/testcases.json
TESTDATA_DIR = os.path.join(os.path.dirname(__file__), "testdata")
with open(os.path.join(TESTDATA_DIR, "testcases.json")) as f:
    TESTCASES = json.load(f)


@pytest.mark.parametrize("case", TESTCASES, ids=lambda c: c.get("name", "case"))
def test_chat_geoprocess_expected_result(client, stub_requests, case):
    """
    Parametrized integration test for various geoprocessing operations.

    For each test case, this function:
      1. Stubs external GeoJSON inputs based on `case["input_geojsons"]` mapping.
      2. Sends the provided `case["payload"]` to the /api/chat endpoint.
      3. Asserts a successful 200 response and presence of `geodata_results`.
      4. Verifies the output file is saved under LOCAL_UPLOAD_DIR and BASE_URL prefix.
      5. Loads the actual output GeoJSON and the expected GeoJSON.
      6. Compares the primary feature geometry using Shapely/GeoPandas
         with a tolerance defined in `case.get("geom_tolerance")`.

    Case dictionary keys:
      - "input_geojsons": dict mapping URL-key substrings to filenames in tests/testdata
      - "payload": JSON body to POST to the endpoint
      - "expected_output_geojson": filename of expected output GeoJSON in tests/testdata
      - "geom_tolerance": (optional) tolerance for exact geometry matching

    Args:
        client (TestClient): Fixture for making API requests.
        stub_requests (callable): Fixture to stub external HTTP requests.
        case (dict): Test case configuration.
    """
    # 1) Prepare stub mapping of input GeoJSONs
    mapping = {}
    for key, filename in case["input_geojsons"].items():
        path = os.path.join(TESTDATA_DIR, filename)
        with open(path) as gf:
            mapping[key] = json.load(gf)
    stub_requests(mapping)

    # 2) Call the API with the provided payload
    resp = client.post("/api/chat", json=case["payload"])
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # 3) Ensure we got geodata_results
    assert "geodata_results" in body, "No geodata_results returned"
    results = body["geodata_results"]
    assert isinstance(results, list) and results, "Empty geodata_results"

    # 4) Check that output file exists
    link = results[0]["data_link"]
    assert link.startswith(BASE_URL)
    filename = link.split("/")[-1]
    saved_path = os.path.join(LOCAL_UPLOAD_DIR, filename)
    assert os.path.isfile(saved_path), f"Output file not found: {saved_path}"

    # 5) Load actual and expected geometries
    with open(saved_path) as sf:
        result_gj = json.load(sf)
    actual_geom = shape(result_gj["features"][0]["geometry"])

    expected_filename = case["expected_output_geojson"]
    with open(os.path.join(TESTDATA_DIR, expected_filename)) as ef:
        expected_gj = json.load(ef)
    expected_geom = shape(expected_gj["features"][0]["geometry"])

    # 6) Compare geometries with specified tolerance
    actual_series = gpd.GeoSeries([actual_geom], crs="EPSG:4326")
    expected_series = gpd.GeoSeries([expected_geom], crs="EPSG:4326")
    tolerance = case.get("geom_tolerance", 0)
    assert actual_series.geom_equals_exact(
        expected_series, tolerance=tolerance
    ).all(), f"Geometries do not match within tolerance {tolerance}"
