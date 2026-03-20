import importlib
import io
import json
import os
import sys
import asyncio
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

# Ensure backend package is importable
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))


def build_minimal_app(tmp_path: Path) -> TestClient:
    """Create a minimal FastAPI app mounting only the upload router and static files."""
    uploads = tmp_path / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    os.environ["LOCAL_UPLOAD_DIR"] = str(uploads)
    os.environ["USE_OGCAPI_STORAGE"] = "false"
    os.environ["USE_AZURE_STORAGE"] = "false"

    # Import after setting env, and reload to pick up overrides even if previously imported
    if "core.config" in sys.modules:
        importlib.reload(sys.modules["core.config"])  # type: ignore[arg-type]
    if "services.storage.file_management" in sys.modules:
        importlib.reload(sys.modules["services.storage.file_management"])  # type: ignore[arg-type]
    if "api.data_management" in sys.modules:
        importlib.reload(sys.modules["api.data_management"])  # type: ignore[arg-type]

    from api.data_management import router as upload_router  # noqa: E402
    from core.config import LOCAL_UPLOAD_DIR  # noqa: E402

    app = FastAPI()
    os.makedirs(LOCAL_UPLOAD_DIR, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=LOCAL_UPLOAD_DIR), name="uploads")
    app.include_router(upload_router, prefix="/api")
    return TestClient(app)


@pytest.fixture
def client(tmp_path):
    return build_minimal_app(tmp_path)


def test_small_file_upload_success(client, tmp_path):
    data = {"file": ("hello.txt", io.BytesIO(b"hello world"), "text/plain")}
    resp = client.post("/api/upload", files=data)
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert "url" in payload and "id" in payload
    # Verify file exists in the uploads dir
    # Use the reloaded config path rather than raw env to avoid stale constants
    from core.config import LOCAL_UPLOAD_DIR as CFG_UPLOADS  # type: ignore

    uploads_dir = Path(CFG_UPLOADS).resolve()
    stored = uploads_dir / payload["id"]
    assert stored.exists()
    assert stored.read_bytes() == b"hello world"


def test_upload_preserves_extension(client):
    json_payload = b'{"type":"FeatureCollection","features":[]}'
    data = {"file": ("My.Place.GeoJSON", io.BytesIO(json_payload), "application/geo+json")}
    resp = client.post("/api/upload", files=data)
    assert resp.status_code == 200, resp.text
    payload = resp.json()

    from core.config import LOCAL_UPLOAD_DIR as CFG_UPLOADS  # type: ignore

    stored = Path(CFG_UPLOADS) / payload["id"]
    assert stored.exists()
    assert stored.suffix == ".geojson"
    assert stored.read_bytes() == json_payload


def test_oversize_upload_rejected(tmp_path, monkeypatch):
    # Build app
    client = build_minimal_app(tmp_path)
    # Monkeypatch MAX_FILE_SIZE to a very small value for this test
    import core.config as cfg

    monkeypatch.setattr(cfg, "MAX_FILE_SIZE", 5, raising=False)

    data = {"file": ("big.bin", io.BytesIO(b"0123456789"), "application/octet-stream")}
    resp = client.post("/api/upload", files=data)
    assert resp.status_code == 413
    body = resp.json()
    assert body["detail"] == "File size (10 B) exceeds the limit of 5 B."


def test_get_upload_meta_allows_nested_path(client):
    from core.config import LOCAL_UPLOAD_DIR as CFG_UPLOADS  # type: ignore

    uploads_dir = Path(CFG_UPLOADS)
    nested = uploads_dir / "nested"
    nested.mkdir(parents=True, exist_ok=True)
    file_path = nested / "data.txt"
    file_path.write_bytes(b"abc")

    encoded = quote("nested/data.txt", safe="")
    resp = client.get(f"/api/uploads/meta/{encoded}")
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["id"] == "nested/data.txt"
    assert payload["size"] == "3"


def test_get_upload_meta_rejects_traversal(client, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("classified")

    resp = client.get("/api/uploads/meta/..%2Fsecret.txt")
    assert resp.status_code == 400
    body = resp.json()
    assert "invalid" in body.get("detail", "").lower()


def test_get_upload_meta_missing_file(client):
    resp = client.get("/api/uploads/meta/missing.txt")
    assert resp.status_code == 404


def test_get_upload_meta_rejects_absolute_path(client):
    # Leading slash encoded as %2F
    resp = client.get("/api/uploads/meta/%2Fetc%2Fpasswd")
    assert resp.status_code == 400


def test_get_upload_meta_rejects_hidden_segment(client):
    resp = client.get("/api/uploads/meta/nested/.hidden")
    assert resp.status_code == 400


def test_register_geojson_collection_returns_collection_id(monkeypatch):
    import api.data_management as data_management

    monkeypatch.setattr(data_management.core_config, "USE_OGCAPI_STORAGE", True, raising=False)
    monkeypatch.setattr(
        data_management.core_config, "OGCAPI_BASE_URL", "http://ogcapi:8000/v1", raising=False
    )
    monkeypatch.setattr(data_management.core_config, "OGCAPI_TIMEOUT_SECONDS", 5, raising=False)

    class MockResponse:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {"status": "ok", "collection_id": "points_simple_upload"}

    def fake_post(url, data=None, files=None, timeout=None):
        assert url.endswith("/uploads/vector")
        assert data["new_collection_title"] == "points_simple"
        assert "new_collection_id" in data
        assert files["file"][0] == "points_simple.geojson"
        return MockResponse()

    monkeypatch.setattr(data_management.requests, "post", fake_post)

    class UploadStub:
        def __init__(self):
            self.file = io.BytesIO(b'{"type":"FeatureCollection","features":[]}')

    registration = data_management._register_geojson_collection(
        UploadStub(), "points_simple.geojson"
    )
    assert registration == {
        "collection_id": "points_simple_upload",
        "inserted": None,
        "created_collection": False,
    }


def test_register_geojson_collection_flattens_nested_feature_properties(monkeypatch):
    import api.data_management as data_management

    monkeypatch.setattr(data_management.core_config, "USE_OGCAPI_STORAGE", True, raising=False)
    monkeypatch.setattr(
        data_management.core_config, "OGCAPI_BASE_URL", "http://ogcapi:8000/v1", raising=False
    )
    monkeypatch.setattr(data_management.core_config, "OGCAPI_TIMEOUT_SECONDS", 5, raising=False)

    captured_payload = {}

    class MockResponse:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {"status": "ok", "collection_id": "points_simple_upload"}

    def fake_post(url, data=None, files=None, timeout=None):
        upload_stream = files["file"][1]
        upload_stream.seek(0)
        captured_payload["geojson"] = json.loads(upload_stream.read())
        return MockResponse()

    monkeypatch.setattr(data_management.requests, "post", fake_post)

    class UploadStub:
        def __init__(self):
            self.file = io.BytesIO(
                b"""{
                    "type":"FeatureCollection",
                    "features":[
                        {"type":"Feature",
                        "geometry":{"type":"Point",
                        "coordinates":[1,2]},
                        "properties":
                            {
                                "properties":
                                {
                                    "id":1,
                                    "name":"a"
                                }
                            }
                            }
                        ]
                    }"""
            )

    registration = data_management._register_geojson_collection(
        UploadStub(), "points_simple.geojson"
    )
    assert registration == {
        "collection_id": "points_simple_upload",
        "inserted": None,
        "created_collection": False,
    }
    feature_props = captured_payload["geojson"]["features"][0]["properties"]
    assert feature_props == {"id": 1, "name": "a"}


def test_register_geojson_collection_works_when_storage_flag_disabled(monkeypatch):
    import api.data_management as data_management

    monkeypatch.setattr(data_management.core_config, "USE_OGCAPI_STORAGE", False, raising=False)
    monkeypatch.setattr(
        data_management.core_config, "OGCAPI_BASE_URL", "http://ogcapi:8000/v1", raising=False
    )
    monkeypatch.setattr(data_management.core_config, "OGCAPI_TIMEOUT_SECONDS", 5, raising=False)

    class MockResponse:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {"status": "ok", "collection_id": "points_simple_upload"}

    monkeypatch.setattr(data_management.requests, "post", lambda *args, **kwargs: MockResponse())

    class UploadStub:
        def __init__(self):
            self.file = io.BytesIO(b'{"type":"FeatureCollection","features":[]}')

    registration = data_management._register_geojson_collection(
        UploadStub(), "points_simple.geojson"
    )
    assert registration == {
        "collection_id": "points_simple_upload",
        "inserted": None,
        "created_collection": False,
    }


def test_collection_items_url_uses_file_url_host():
    import api.data_management as data_management

    file_url = "http://localhost:8081/v1/uploads/files/abc123_points_simple.geojson"
    items_url = data_management._collection_items_url(file_url, "points_simple_upload")
    assert items_url == "http://localhost:8081/v1/collections/points_simple_upload/items"


def test_collection_tiles_url_uses_file_url_host():
    import api.data_management as data_management

    file_url = "http://localhost:8081/v1/uploads/files/abc123_points_simple.geojson"
    tiles_url = data_management._collection_tiles_url(file_url, "points_simple_upload")
    assert (
        tiles_url
        == "http://localhost:8081/v1/collections/points_simple_upload/tiles/{z}/{x}/{y}.mvt"
    )


def test_collection_items_url_rewrites_internal_ogc_host(monkeypatch):
    import api.data_management as data_management

    monkeypatch.setattr(data_management.core_config, "OGCAPI_BASE_URL", "http://localhost:8081/v1")
    monkeypatch.setattr(
        data_management.core_config, "OGCAPI_PUBLIC_BASE_URL", "http://localhost:8081/v1"
    )
    file_url = "http://ogcapi:8000/v1/uploads/files/abc123_points_simple.geojson"
    items_url = data_management._collection_items_url(file_url, "points_simple_upload")
    assert items_url == "http://localhost:8081/v1/collections/points_simple_upload/items"


def test_collection_items_url_uses_public_base_url_when_runtime_is_internal(monkeypatch):
    import api.data_management as data_management

    monkeypatch.setattr(data_management.core_config, "OGCAPI_BASE_URL", "http://ogcapi:8000/v1")
    monkeypatch.setattr(
        data_management.core_config, "OGCAPI_PUBLIC_BASE_URL", "http://localhost:8081/v1"
    )
    file_url = "http://ogcapi:8000/v1/uploads/files/abc123_points_simple.geojson"
    items_url = data_management._collection_items_url(file_url, "points_simple_upload")
    assert items_url == "http://localhost:8081/v1/collections/points_simple_upload/items"


def test_upload_response_exposes_items_and_tiles_for_ogc_collections(monkeypatch):
    import api.data_management as data_management

    monkeypatch.setattr(
        data_management,
        "store_file_stream",
        lambda name, stream: (
            "http://localhost:8081/v1/uploads/files/abc123_points_simple.geojson",
            "abc123_points_simple.geojson",
        ),
    )
    monkeypatch.setattr(
        data_management,
        "_register_geojson_collection",
        lambda file, filename: {
            "collection_id": "points_simple_upload",
            "inserted": 6000,
            "created_collection": True,
        },
    )

    class UploadStub:
        filename = "points_simple.geojson"
        size = None

        def __init__(self):
            self.file = io.BytesIO(b'{"type":"FeatureCollection","features":[]}')

        async def close(self):
            self.file.close()

    upload = UploadStub()
    payload = asyncio.run(data_management.upload_file(upload))
    assert payload["ogc_collection_id"] == "points_simple_upload"
    assert payload["items_url"].endswith("/collections/points_simple_upload/items")
    assert payload["tiles_url"].endswith("/collections/points_simple_upload/tiles/{z}/{x}/{y}.mvt")
    assert payload["tiles_metadata_url"].endswith("/collections/points_simple_upload/tiles")
    assert payload["ogc_feature_count"] == 6000
    assert payload["ogc_recommended_render_mode"] == "tiles"
    assert payload["ogc_render_mode"] == "auto"


def test_register_geojson_collection_remaps_localhost_in_container(monkeypatch):
    import api.data_management as data_management

    monkeypatch.setattr(data_management.core_config, "OGCAPI_BASE_URL", "http://localhost:8081/v1")
    monkeypatch.setattr(data_management.core_config, "OGCAPI_TIMEOUT_SECONDS", 5, raising=False)
    monkeypatch.setattr(data_management, "_is_container_runtime", lambda: True)

    class MockResponse:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {"status": "ok", "collection_id": "points_simple_upload"}

    def fake_post(url, data=None, files=None, timeout=None):
        assert url == "http://ogcapi:8000/v1/uploads/vector"
        return MockResponse()

    monkeypatch.setattr(data_management.requests, "post", fake_post)

    class UploadStub:
        def __init__(self):
            self.file = io.BytesIO(b'{"type":"FeatureCollection","features":[]}')

    registration = data_management._register_geojson_collection(
        UploadStub(), "points_simple.geojson"
    )
    assert registration == {
        "collection_id": "points_simple_upload",
        "inserted": None,
        "created_collection": False,
    }


def test_store_file_rewrites_internal_ogc_url_to_public(monkeypatch):
    import services.storage.file_management as file_management

    monkeypatch.setattr(file_management, "USE_OGCAPI_STORAGE", True)
    monkeypatch.setattr(file_management, "OGCAPI_BASE_URL", "http://ogcapi:8000/v1")
    monkeypatch.setattr(file_management, "OGCAPI_PUBLIC_BASE_URL", "http://localhost:8081/v1")
    monkeypatch.setattr(file_management, "OGCAPI_TIMEOUT_SECONDS", 5)

    class MockResponse:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {
                "id": "abc123_points_simple.geojson",
                "url": "http://ogcapi:8000/v1/uploads/files/abc123_points_simple.geojson",
            }

    monkeypatch.setattr(file_management.requests, "post", lambda *args, **kwargs: MockResponse())
    url, file_id = file_management.store_file(
        "points_simple.geojson", b'{"type":"FeatureCollection"}'
    )
    assert file_id == "abc123_points_simple.geojson"
    assert url == "http://localhost:8081/v1/uploads/files/abc123_points_simple.geojson"


def test_store_file_stream_rewrites_internal_ogc_url_to_public(monkeypatch):
    import services.storage.file_management as file_management

    monkeypatch.setattr(file_management, "USE_OGCAPI_STORAGE", True)
    monkeypatch.setattr(file_management, "OGCAPI_BASE_URL", "http://ogcapi:8000/v1")
    monkeypatch.setattr(file_management, "OGCAPI_PUBLIC_BASE_URL", "http://localhost:8081/v1")
    monkeypatch.setattr(file_management, "OGCAPI_TIMEOUT_SECONDS", 5)

    class MockResponse:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {
                "id": "def456_points_simple.geojson",
                "url": "http://ogcapi:8000/v1/uploads/files/def456_points_simple.geojson",
            }

    monkeypatch.setattr(file_management.requests, "post", lambda *args, **kwargs: MockResponse())
    url, file_id = file_management.store_file_stream(
        "points_simple.geojson", io.BytesIO(b'{"type":"FeatureCollection"}')
    )
    assert file_id == "def456_points_simple.geojson"
    assert url == "http://localhost:8081/v1/uploads/files/def456_points_simple.geojson"
