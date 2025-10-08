import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import auto_styling


@pytest.fixture
def auto_styling_client():
    app = FastAPI()
    app.include_router(auto_styling.router)
    return TestClient(app)


def make_layer_payload(**overrides):
    payload = {
        "id": "layer-1",
        "data_source_id": "source-1",
        "data_type": "GeoJson",
        "data_origin": "uploaded",
        "data_source": "Test Source",
        "data_link": "http://example.com/data.geojson",
        "name": "Rivers of Africa",
        "title": "Rivers of Africa",
        "description": "Major rivers dataset",
        "layer_type": "GeoJSON",
        "visible": True,
        "style": {
            "stroke_color": "#3388f",
            "fill_color": "#3388f",
            "stroke_weight": 2,
            "fill_opacity": 0.3,
        },
    }
    payload.update(overrides)
    return payload


def test_auto_style_layers_returns_message_when_no_layers(auto_styling_client):
    response = auto_styling_client.post("/auto-style", json={"layers": []})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["message"] == "No layers provided for styling"
    assert data["styled_layers"] == []


def test_auto_style_layers_returns_error_for_invalid_input(auto_styling_client):
    response = auto_styling_client.post("/auto-style", json={"layers": [{"foo": "bar"}]})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["message"] == "No valid layers found for styling"
    assert data["styled_layers"] == []


def test_auto_style_layers_invokes_agent_and_returns_updated_layers(
    auto_styling_client, monkeypatch
):
    updated_colors = {"stroke_color": "#123456", "fill_color": "#654321"}

    class DummyAgent:
        def __init__(self):
            self.invocations = []

        def invoke(self, state, debug=False):
            self.invocations.append((state, debug))
            # mutate first layer style to simulate agent styling
            styled_layer = state["geodata_layers"][0]
            styled_layer.style.stroke_color = updated_colors["stroke_color"]
            styled_layer.style.fill_color = updated_colors["fill_color"]
            return {"geodata_layers": state["geodata_layers"]}

    dummy_agent = DummyAgent()
    monkeypatch.setattr(auto_styling, "create_geo_agent", lambda: dummy_agent)

    payload = {"layers": [make_layer_payload()]}
    response = auto_styling_client.post("/auto-style", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["message"] == "Successfully applied automatic AI styling to 1 layer(s)"
    assert len(data["styled_layers"]) == 1
    styled_layer = data["styled_layers"][0]
    assert styled_layer["style"]["stroke_color"] == updated_colors["stroke_color"]
    assert styled_layer["style"]["fill_color"] == updated_colors["fill_color"]
    assert dummy_agent.invocations, "Agent was not invoked"


def test_auto_style_layers_returns_original_for_pre_styled_layer(auto_styling_client, monkeypatch):
    class DummyAgent:
        def invoke(self, state, debug=False):
            raise AssertionError("Agent should not be invoked for pre-styled layers")

    monkeypatch.setattr(auto_styling, "create_geo_agent", lambda: DummyAgent())

    custom_style = {
        "stroke_color": "#000000",
        "fill_color": "#ff9900",
        "stroke_weight": 2,
        "fill_opacity": 0.5,
    }
    layer_payload = make_layer_payload(style=custom_style)

    response = auto_styling_client.post("/auto-style", json={"layers": [layer_payload]})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["message"] == "No layers need automatic styling - all already have custom styling"
    returned_style = data["styled_layers"][0]["style"]
    for key, value in custom_style.items():
        assert returned_style[key] == value
