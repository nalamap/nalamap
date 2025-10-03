from typing import Any, Dict

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from core.config import MAX_FILE_SIZE
from services.storage.file_management import store_file_stream
from core.config import LOCAL_UPLOAD_DIR
import os
import hashlib


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
@router.get("/uploads/meta/{file_id}")
async def get_upload_meta(file_id: str) -> Dict[str, str]:
    """Return file size and SHA256 for a stored upload by its ID (filename)."""
    path = os.path.join(LOCAL_UPLOAD_DIR, file_id)
    if not os.path.exists(path) or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File not found")

    sha256 = hashlib.sha256()
    size = 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            size += len(chunk)
            sha256.update(chunk)

    return {"id": file_id, "size": str(size), "sha256": sha256.hexdigest()}
