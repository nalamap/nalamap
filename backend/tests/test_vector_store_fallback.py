import math

import pytest

from models.geodata import DataOrigin, DataType, GeoDataObject
from services.tools.geoserver import vector_store as vs


def make_layer(layer_id: str, title: str, description: str) -> GeoDataObject:
    return GeoDataObject(
        id=layer_id,
        data_source_id="catalog",
        data_type=DataType.LAYER,
        data_origin=DataOrigin.TOOL,
        data_source="GeoServer",
        data_link=f"https://example.com/geoserver/{layer_id}",
        name=f"example:{layer_id}",
        title=title,
        description=description,
        layer_type="WMS",
    )


@pytest.fixture(autouse=True)
def enable_fallback(monkeypatch):
    vs.reset_vector_store_for_tests()
    monkeypatch.setattr(vs, "_use_fallback_store", True, raising=False)
    monkeypatch.setattr(vs, "_fallback_documents", [], raising=False)
    yield
    vs.reset_vector_store_for_tests()


def test_store_and_list_layers_in_fallback_mode():
    layers = [
        make_layer("1", "Coastal Rivers", "Rivers flowing through coastal plains."),
        make_layer("2", "Mountain Streams", "High elevation snow melt streams."),
    ]
    stored = vs.store_layers("session-x", "https://example.com/geoserver", "Example", layers)
    assert stored == len(layers)

    listed = vs.list_layers("session-x", ["https://example.com/geoserver"], limit=5)
    assert [layer.id for layer in listed] == ["2", "1"]

    assert vs.has_layers("session-x", ["https://example.com/geoserver"])


def test_similarity_search_prefers_matching_layers():
    backend_url = "https://example.com/geoserver"
    vs.store_layers(
        "session-y",
        backend_url,
        "Example",
        [
            make_layer("1", "Coastal Rivers", "Rivers flowing through coastal plains."),
            make_layer("2", "Mountain Streams", "High elevation snow melt streams."),
        ],
    )

    results = vs.similarity_search("session-y", [backend_url], "coastal river plains", limit=1)
    assert len(results) == 1
    top_layer, distance = results[0]
    assert top_layer.id == "1"
    assert 0.0 <= top_layer.score <= 1.0
    assert math.isclose(1.0 - distance, top_layer.score, rel_tol=1e-6)


def test_delete_layers_clears_fallback_documents():
    backend_url = "https://example.com/geoserver"
    vs.store_layers(
        "session-z",
        backend_url,
        "Example",
        [make_layer("1", "Wetlands", "Extensive wetland coverage.")],
    )

    assert vs.has_layers("session-z", [backend_url])
    vs.delete_layers("session-z", [backend_url])
    assert not vs.has_layers("session-z", [backend_url])
    assert vs.list_layers("session-z", [backend_url], limit=5) == []
