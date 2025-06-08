# tests/test_chat_integration.py

import os
import json
import pytest
from types import SimpleNamespace
from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage
import requests
from core.config import BASE_URL, LOCAL_UPLOAD_DIR
from services.ai import llm_config
from main import app  # wherever your FastAPI instance lives

# ensure LOCAL_UPLOAD_DIR exists for test
os.makedirs(LOCAL_UPLOAD_DIR, exist_ok=True)

@pytest.fixture
def client():
    return TestClient(app)

#@pytest.fixture
#def stub_llm(monkeypatch):
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
#@pytest.fixture
#def stub_requests(monkeypatch):
#    """
#    Returns a helper that lets your test specify ANY GeoJSON (and status code)
#    to be returned by requests.get().
#
#    Usage in a test:
#
#        sample = { ... any GeoJSON dict ... }
#        stub_requests(sample)
#    """
#    def _stub(sample_geojson: dict, status_code: int = 200):
#        fake_resp = SimpleNamespace(
#            status_code=status_code,
#            json=lambda: sample_geojson
#        )
#        # stub requests.get(url, timeout=...) → fake_resp
#        monkeypatch.setattr(requests, "get", lambda url, timeout=10: fake_resp)
#    return _stub

def test_buffer_endpoint_creates_buffered_result(client):
    # Prepare payload
    payload = {
        'messages': [{ "type": "human", "content": "buffer the points by 100 meters of layer1" }],   
        "options": {},
        "query": "buffer the points by 100 meters",
        "geodata_last_results": [],
        "geodata_layers": [
            {
                "id": "layer1",
                "data_source_id": "test",
                "data_type": "GeoJson",
                "data_origin": "TOOL",
                "data_source": "test",
                "data_link": "http://localhost:8000/upload/points_simple.geojson",
                "name": "pt",
                "title": "pt",
                "description": "",
                "llm_description": "",
                "score": 0,
                "bounding_box": None,
                "layer_type": "GeoJSON",
                "properties": {}
            }
        ]
    }

    # Call the API
    resp = client.post("/api/chat", json=payload)
    assert resp.status_code == 200, resp.text

    body = resp.json()
    # Check that one buffered layer was returned
    assert "geodata_results" in body
    results = body["geodata_results"]
    assert isinstance(results, list) and len(results) == 1

    # The returned GeoDataObject should point to our LOCAL_UPLOAD_DIR via BASE_URL
    link = results[0]["data_link"]
    assert link.startswith(BASE_URL)

    # And the file should actually exist on disk
    filename = link.split("/")[-1]
    saved_path = os.path.join(LOCAL_UPLOAD_DIR, filename)
    assert os.path.isfile(saved_path)

    # Verify that the saved GeoJSON is a polygon (buffer of a point)
    with open(saved_path) as f:
        gj = json.load(f)
    assert gj["type"] == "FeatureCollection"
    assert len(gj["features"]) >= 1
    geom = gj["features"][0]["geometry"]
    assert geom["type"] == "Polygon"
