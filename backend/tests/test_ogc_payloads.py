import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

import core.config as core_config  # noqa: E402
from api.ogc_payloads import (  # noqa: E402
    inject_ogc_vector_tile_threshold,
    normalize_ogc_geodata_payloads,
)


def test_inject_ogc_vector_tile_threshold_adds_threshold_to_ogc_layers():
    payload = inject_ogc_vector_tile_threshold(
        {
            "data_link": "http://localhost:8081/v1/collections/test_collection/items",
            "payload": {
                "properties": {
                    "ogc_collection_id": "test_collection",
                }
            },
        }
    )

    assert payload["payload"]["properties"]["ogc_vector_tile_feature_threshold"] == 2000


def test_inject_ogc_vector_tile_threshold_preserves_existing_threshold():
    payload = inject_ogc_vector_tile_threshold(
        {
            "data_link": "http://localhost:8081/v1/collections/test_collection/items",
            "payload": {
                "properties": {
                    "ogc_collection_id": "test_collection",
                    "ogc_vector_tile_feature_threshold": 1234,
                }
            },
        }
    )

    assert payload["payload"]["properties"]["ogc_vector_tile_feature_threshold"] == 1234


def test_inject_ogc_vector_tile_threshold_rewrites_internal_ogc_urls(monkeypatch):
    monkeypatch.setattr(core_config, "OGCAPI_BASE_URL", "http://ogcapi:8000/v1")
    monkeypatch.setattr(core_config, "OGCAPI_PUBLIC_BASE_URL", "http://localhost:8081/v1")

    payload = inject_ogc_vector_tile_threshold(
        {
            "data_link": "http://ogcapi:8000/v1/collections/test_collection/items",
            "payload": {
                "properties": {
                    "ogc_collection_id": "test_collection",
                    "ogc_items_url": "http://ogcapi:8000/v1/collections/test_collection/items",
                    "ogc_tiles_url": (
                        "http://ogcapi:8000/v1/collections/test_collection/tiles/{z}/{x}/{y}.mvt"
                    ),
                    "ogc_tiles_metadata_url": (
                        "http://ogcapi:8000/v1/collections/test_collection/tiles"
                    ),
                }
            },
        }
    )

    assert payload["data_link"] == "http://localhost:8081/v1/collections/test_collection/items"
    assert (
        payload["payload"]["properties"]["ogc_items_url"]
        == "http://localhost:8081/v1/collections/test_collection/items"
    )
    assert (
        payload["payload"]["properties"]["ogc_tiles_url"]
        == "http://localhost:8081/v1/collections/test_collection/tiles/{z}/{x}/{y}.mvt"
    )
    assert (
        payload["payload"]["properties"]["ogc_tiles_metadata_url"]
        == "http://localhost:8081/v1/collections/test_collection/tiles"
    )


def test_normalize_ogc_geodata_payloads_rewrites_and_adds_threshold(monkeypatch):
    monkeypatch.setattr(core_config, "OGCAPI_BASE_URL", "http://ogcapi:8000/v1")
    monkeypatch.setattr(core_config, "OGCAPI_PUBLIC_BASE_URL", "http://localhost:8081/v1")
    monkeypatch.setattr(core_config, "OGCAPI_VECTOR_TILE_FEATURE_THRESHOLD", 3456)

    payloads = normalize_ogc_geodata_payloads(
        [
            {
                "id": "layer-1",
                "data_link": "http://ogcapi:8000/v1/collections/test_collection/items",
                "payload": {
                    "properties": {
                        "ogc_collection_id": "test_collection",
                    }
                },
            }
        ]
    )

    assert payloads[0]["data_link"] == "http://localhost:8081/v1/collections/test_collection/items"
    assert payloads[0]["payload"]["properties"]["ogc_vector_tile_feature_threshold"] == 3456
