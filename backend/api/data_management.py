import hashlib
import io
import json
import logging
import os
import re
import uuid
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote, urlparse, urlunparse

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

import core.config as core_config
from core.config import MAX_FILE_SIZE
from services.storage.file_management import store_file_stream
import requests


# Helper function for formatting file size
def format_file_size(bytes_size):
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_size < 1024 or unit == "GB":
            return f"{bytes_size:.2f} {unit}" if unit != "B" else f"{bytes_size} {unit}"
        bytes_size /= 1024.0


class StyleUpdateRequest(BaseModel):
    layer_id: str
    style: Dict[str, Any]


router = APIRouter()
logger = logging.getLogger(__name__)


SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")
SAFE_COLLECTION_ID = re.compile(r"^[A-Za-z0-9._-]+$")


def _resolve_upload_path(file_id: str) -> str:
    """Safely resolve upload file path within uploads directory.

    Returns the validated absolute path as a string to satisfy CodeQL analysis.
    """
    if not file_id or not file_id.strip():
        raise HTTPException(status_code=400, detail="Invalid file identifier")

    # Normalize and validate segments before joining
    normalized = os.path.normpath(file_id)

    # Reject absolute paths and parent directory traversal
    if os.path.isabs(normalized) or normalized.startswith(".."):
        raise HTTPException(status_code=400, detail="Invalid file identifier")

    # Additional segment validation
    segments = normalized.split(os.sep)
    for part in segments:
        if part in {"..", ""} or part.startswith(".") or not SAFE_SEGMENT.match(part):
            raise HTTPException(status_code=400, detail="Invalid file identifier")

    # Build full path and normalize
    uploads_root = os.path.abspath(core_config.LOCAL_UPLOAD_DIR)
    fullpath = os.path.normpath(os.path.join(uploads_root, normalized))

    # Verify the normalized path is within uploads_root (CodeQL-approved pattern)
    if not fullpath.startswith(uploads_root + os.sep):
        raise HTTPException(status_code=400, detail="Invalid file identifier")

    # Check file exists and is a file
    if not os.path.exists(fullpath) or not os.path.isfile(fullpath):
        raise HTTPException(status_code=404, detail="File not found")

    return fullpath


def _is_geojson_filename(filename: str) -> bool:
    return filename.lower().endswith(".geojson")


def _is_container_runtime() -> bool:
    return os.path.exists("/.dockerenv")


def _configured_ogcapi_base_url() -> str:
    return (core_config.OGCAPI_BASE_URL or "").rstrip("/")


def _public_ogcapi_base_url() -> str:
    return (core_config.OGCAPI_PUBLIC_BASE_URL or core_config.OGCAPI_BASE_URL or "").rstrip("/")


def _runtime_ogcapi_base_url() -> str:
    base = _configured_ogcapi_base_url()
    if not base:
        return base
    parsed = urlparse(base)
    hostname = (parsed.hostname or "").lower()
    if hostname not in {"localhost", "127.0.0.1", "::1"} or not _is_container_runtime():
        return base

    remapped = parsed._replace(
        scheme=parsed.scheme or "http",
        netloc="ogcapi:8000",
    )
    return urlunparse(remapped).rstrip("/")


def _rewrite_ogcapi_url_to_public(url: str) -> str:
    if not isinstance(url, str) or not url.strip():
        return url
    public_base = _public_ogcapi_base_url()
    runtime_base = _runtime_ogcapi_base_url()
    if not public_base:
        return url

    public_parsed = urlparse(public_base)
    runtime_parsed = urlparse(runtime_base) if runtime_base else None
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return url

    hostname = (parsed.hostname or "").lower()
    runtime_hostname = (runtime_parsed.hostname or "").lower() if runtime_parsed else ""
    if hostname not in {"ogcapi", runtime_hostname} and parsed.netloc != (
        runtime_parsed.netloc if runtime_parsed else ""
    ):
        return url

    new_path = parsed.path or ""
    public_prefix = (public_parsed.path or "").rstrip("/")
    if public_prefix and not new_path.startswith(public_prefix + "/") and new_path != public_prefix:
        if not new_path.startswith("/"):
            new_path = "/" + new_path
        new_path = f"{public_prefix}{new_path}"

    rewritten = parsed._replace(
        scheme=public_parsed.scheme or parsed.scheme,
        netloc=public_parsed.netloc or parsed.netloc,
        path=new_path,
    )
    return urlunparse(rewritten)


def _build_collection_id(filename: str) -> str:
    stem = os.path.splitext(os.path.basename(filename))[0]
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-.")
    if not safe_stem:
        safe_stem = "upload"
    safe_stem = safe_stem[:40]
    candidate = f"upload_{safe_stem}_{uuid.uuid4().hex[:8]}"
    if SAFE_COLLECTION_ID.match(candidate):
        return candidate
    return f"upload_{uuid.uuid4().hex[:12]}"


def _normalize_geojson_feature_properties_for_ogc(stream: Any) -> Tuple[Any, bool]:
    """Normalize known malformed GeoJSON property nesting before OGC registration.

    If a feature has the shape {"properties": {"properties": {...}}}, flatten it to
    {"properties": {...}}. Other structures are left untouched.
    """
    try:
        stream.seek(0)
        raw = stream.read()
    except Exception:
        return stream, False

    if isinstance(raw, str):
        raw_bytes = raw.encode("utf-8")
    else:
        raw_bytes = raw or b""

    if not raw_bytes:
        return io.BytesIO(raw_bytes), False

    try:
        payload = json.loads(raw_bytes)
    except Exception:
        return io.BytesIO(raw_bytes), False

    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
        return io.BytesIO(raw_bytes), False

    features = payload.get("features")
    if not isinstance(features, list):
        return io.BytesIO(raw_bytes), False

    changed = False
    for feature in features:
        if not isinstance(feature, dict):
            continue
        props = feature.get("properties")
        if not isinstance(props, dict):
            continue
        nested_props = props.get("properties")
        if set(props.keys()) == {"properties"} and isinstance(nested_props, dict):
            feature["properties"] = nested_props
            changed = True

    if not changed:
        return io.BytesIO(raw_bytes), False

    normalized_bytes = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return io.BytesIO(normalized_bytes), True


def _register_geojson_collection(
    file: UploadFile, filename: str
) -> Dict[str, Any] | None:
    runtime_base_url = _runtime_ogcapi_base_url()
    if not (runtime_base_url and _is_geojson_filename(filename)):
        return None

    stream = getattr(file, "file", None)
    if stream is None:
        return None

    try:
        stream.seek(0)
        collection_id = _build_collection_id(filename)
        collection_title = os.path.splitext(os.path.basename(filename))[0] or collection_id
        upload_stream, normalized = _normalize_geojson_feature_properties_for_ogc(stream)
        response = requests.post(
            f"{runtime_base_url}/uploads/vector",
            data={
                "new_collection_id": collection_id,
                "new_collection_title": collection_title,
            },
            files={"file": (filename, upload_stream, "application/geo+json")},
            timeout=core_config.OGCAPI_TIMEOUT_SECONDS,
        )
        if normalized:
            logger.info(
                """Normalized nested GeoJSON feature properties
                        for %s before OGC upload""",
                filename,
            )
    except Exception as exc:
        logger.warning("OGC collection registration failed for %s: %s", filename, exc)
        return None
    finally:
        try:
            stream.seek(0)
        except Exception:
            pass

    if response.status_code >= 400:
        logger.warning(
            "OGC collection registration rejected for %s: %s %s",
            filename,
            response.status_code,
            response.text,
        )
        return None

    try:
        payload = response.json()
    except ValueError:
        logger.warning("OGC collection registration returned invalid JSON for %s", filename)
        return None

    if not isinstance(payload, dict):
        return None

    value = payload.get("collection_id")
    if not isinstance(value, str) or not value.strip():
        return None

    inserted_raw = payload.get("inserted")
    inserted: Optional[int] = None
    if isinstance(inserted_raw, int):
        inserted = inserted_raw
    elif isinstance(inserted_raw, str):
        try:
            inserted = int(inserted_raw)
        except ValueError:
            inserted = None

    return {
        "collection_id": value.strip(),
        "inserted": inserted,
        "created_collection": bool(payload.get("created_collection")),
    }


def _collection_base_url(file_url: str) -> str:
    public_file_url = _rewrite_ogcapi_url_to_public(file_url)
    parsed = urlparse(public_file_url)
    marker = "/uploads/files/"
    marker_index = (parsed.path or "").find(marker)
    if marker_index >= 0:
        base_path = (parsed.path or "")[:marker_index] or "/"
        base = parsed._replace(path=base_path, params="", query="", fragment="")
        return urlunparse(base).rstrip("/")

    runtime_base_url = _runtime_ogcapi_base_url()
    return _rewrite_ogcapi_url_to_public(runtime_base_url)


def _collection_items_url(file_url: str, collection_id: str) -> str:
    base_url = _collection_base_url(file_url)
    return f"{base_url}/collections/{quote(collection_id, safe='')}/items"


def _collection_tiles_url(file_url: str, collection_id: str) -> str:
    base_url = _collection_base_url(file_url)
    return (
        f"{base_url}/collections/{quote(collection_id, safe='')}/tiles/"
        "{z}/{x}/{y}.mvt"
    )


def _collection_tiles_metadata_url(file_url: str, collection_id: str) -> str:
    base_url = _collection_base_url(file_url)
    return f"{base_url}/collections/{quote(collection_id, safe='')}/tiles"


def _recommended_ogc_render_mode(feature_count: Optional[int]) -> str:
    if (
        feature_count is not None
        and feature_count >= core_config.OGCAPI_VECTOR_TILE_FEATURE_THRESHOLD
    ):
        return "tiles"
    return "items"


# Layer styling endpoint
@router.put("/layers/{layer_id}/style")
async def update_layer_style_endpoint(layer_id: str, style_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Update the styling of a specific layer.
    """
    # In a real implementation, you would update the layer style in your database
    # For now, we'll just return a success message
    return {
        "message": f"Layer {layer_id} style updated successfully",
        "layer_id": layer_id,
    }


# Upload endpoint
@router.post("/upload")
async def upload_file(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Uploads a file to Azure Blob Storage or local disk, streaming the payload.

    Returns its public URL and unique ID. File size is limited to 100MB.
    """
    try:
        # Prefer server-provided size (if multipart header contains it) for a fast pre-check
        content_length = getattr(file, "size", None)
        if content_length is not None and content_length > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"File size ({format_file_size(content_length)}) exceeds the limit of 100MB."
                ),
            )

        # Stream to storage without loading into memory
        # UploadFile.file is a SpooledTemporaryFile (BinaryIO)
        safe_name = file.filename or "upload.bin"
        url, unique_name = store_file_stream(safe_name, file.file)
        response: Dict[str, Any] = {"url": url, "id": unique_name}
        registration = _register_geojson_collection(file, safe_name)
        if registration:
            collection_id = registration["collection_id"]
            items_url = _collection_items_url(url, collection_id)
            tiles_url = _collection_tiles_url(url, collection_id)
            tiles_metadata_url = _collection_tiles_metadata_url(url, collection_id)
            feature_count = registration.get("inserted")

            response["ogc_collection_id"] = collection_id
            response["file_url"] = _rewrite_ogcapi_url_to_public(url)
            response["url"] = items_url
            response["items_url"] = items_url
            response["tiles_url"] = tiles_url
            response["tiles_metadata_url"] = tiles_metadata_url
            response["ogc_feature_count"] = feature_count
            response["ogc_recommended_render_mode"] = _recommended_ogc_render_mode(
                feature_count
            )
            response["ogc_render_mode"] = "auto"
        return response
    finally:
        await file.close()


# Debug/ops: fetch file metadata (size, sha256) to verify integrity end-to-end
@router.get("/uploads/meta/{file_id:path}")
async def get_upload_meta(file_id: str) -> Dict[str, Any]:
    """Return file size and SHA256 for a stored upload by its ID (filename).

    Supports both local storage and Azure Blob Storage backends.
    """
    if core_config.USE_OGCAPI_STORAGE and core_config.OGCAPI_BASE_URL:
        runtime_base_url = _runtime_ogcapi_base_url()
        try:
            resp = requests.get(
                f"{runtime_base_url}/uploads/meta/{file_id}",
                timeout=core_config.OGCAPI_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=502, detail=f"OGC API meta request failed: {exc}"
            ) from exc
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"OGC API meta request failed: {resp.text}",
            )
        payload = resp.json()
        payload.setdefault("storage", "ogcapi")
        return payload

    # Check if we're using Azure Blob Storage
    if core_config.USE_AZURE and core_config.AZ_CONN:
        try:
            from azure.storage.blob import BlobServiceClient

            # Sanitize filename to prevent path traversal
            safe_file_id = file_id.split("/")[-1]  # Get just the filename

            blob_svc = BlobServiceClient.from_connection_string(core_config.AZ_CONN)
            container_client = blob_svc.get_container_client(core_config.AZ_CONTAINER)
            blob_client = container_client.get_blob_client(safe_file_id)

            # Download blob and compute hash
            sha256 = hashlib.sha256()
            size = 0

            stream = blob_client.download_blob()
            for chunk in stream.chunks():
                size += len(chunk)
                sha256.update(chunk)

            return {
                "id": file_id,
                "size": str(size),
                "sha256": sha256.hexdigest(),
                "storage": "azure",
            }
        except Exception as e:
            raise HTTPException(
                status_code=404, detail=f"File not found in Azure Blob Storage: {str(e)}"
            )
    else:
        # Local storage fallback
        fullpath = _resolve_upload_path(file_id)

        sha256 = hashlib.sha256()
        size = 0
        with open(fullpath, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                size += len(chunk)
                sha256.update(chunk)

        return {
            "id": file_id,
            "size": str(size),
            "sha256": sha256.hexdigest(),
            "storage": "local",
        }
