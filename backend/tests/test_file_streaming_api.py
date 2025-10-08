import json

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api import file_streaming
from services.compression import gzip_utils


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    monkeypatch.setattr(file_streaming, "LOCAL_UPLOAD_DIR", str(uploads))
    monkeypatch.setattr(gzip_utils, "LOCAL_UPLOAD_DIR", str(uploads))
    return uploads


@pytest.fixture
def file_streaming_client(upload_dir):
    app = FastAPI()
    app.include_router(file_streaming.router)
    return TestClient(app)


def test_get_file_path_returns_resolved_path(upload_dir):
    geojson = upload_dir / "data.geojson"
    geojson.write_text("{}", encoding="utf-8")

    resolved = file_streaming.get_file_path("data.geojson")
    assert resolved == geojson.resolve()


def test_get_file_path_rejects_missing_or_directory(upload_dir):
    with pytest.raises(HTTPException) as exc:
        file_streaming.get_file_path("missing.geojson")
    assert exc.value.status_code == 404

    subdir = upload_dir / "nested"
    subdir.mkdir()
    with pytest.raises(HTTPException) as exc:
        file_streaming.get_file_path("nested")
    assert exc.value.status_code == 400


def test_stream_file_serves_full_content(file_streaming_client, upload_dir):
    payload = {"type": "FeatureCollection", "features": []}
    geojson = upload_dir / "sample.geojson"
    geojson.write_text(json.dumps(payload), encoding="utf-8")

    response = file_streaming_client.get("/stream/sample.geojson")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/geo+json"
    assert response.content == geojson.read_bytes()


def test_stream_file_supports_range_requests(file_streaming_client, upload_dir):
    contents = b"0123456789abcdef"
    geojson = upload_dir / "range.geojson"
    geojson.write_bytes(contents)

    response = file_streaming_client.get("/stream/range.geojson", headers={"Range": "bytes=2-5"})
    assert response.status_code == 206
    assert response.headers["Content-Range"] == f"bytes 2-5/{len(contents)}"
    assert response.content == contents[2:6]


def test_head_file_returns_metadata(file_streaming_client, upload_dir):
    geojson = upload_dir / "metadata.geojson"
    geojson.write_text('{\n  "type": "FeatureCollection"\n}', encoding="utf-8")

    response = file_streaming_client.head("/stream/metadata.geojson")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/geo+json"
    assert response.headers["Content-Length"] == str(geojson.stat().st_size)
    assert response.headers["Accept-Ranges"] == "bytes"
