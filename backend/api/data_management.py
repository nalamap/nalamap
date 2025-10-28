import hashlib
import os
import re
from typing import Any, Dict

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

import core.config as core_config
from core.config import MAX_FILE_SIZE
from services.storage.file_management import store_file_stream


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


SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")


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
async def upload_file(file: UploadFile = File(...)) -> Dict[str, str]:
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
        return {"url": url, "id": unique_name}
    finally:
        await file.close()


# Debug/ops: fetch file metadata (size, sha256) to verify integrity end-to-end
@router.get("/uploads/meta/{file_id:path}")
async def get_upload_meta(file_id: str) -> Dict[str, str]:
    """Return file size and SHA256 for a stored upload by its ID (filename).

    Supports both local storage and Azure Blob Storage backends.
    """
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