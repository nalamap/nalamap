import io
import os
import sys
from pathlib import Path
import importlib

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

    # Import after setting env, and reload to pick up overrides even if previously imported
    if "core.config" in sys.modules:
        importlib.reload(sys.modules["core.config"])  # type: ignore[arg-type]
    if "services.storage.file_management" in sys.modules:
        importlib.reload(sys.modules["services.storage.file_management"])  # type: ignore[arg-type]

    from core.config import LOCAL_UPLOAD_DIR  # noqa: E402
    from api.data_management import router as upload_router  # noqa: E402

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
    assert "File" in body.get("detail", "")
