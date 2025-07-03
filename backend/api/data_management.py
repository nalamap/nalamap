from typing import Any, Dict

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from core.config import MAX_FILE_SIZE
from services.storage.file_management import store_file


# Helper function for formatting file size
def format_file_size(bytes_size):
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_size < 1024 or unit == "GB":
            return (
                f"{bytes_size:.2f} {unit}"
                if unit != "B"
                else f"{bytes_size} {unit}"
            )
        bytes_size /= 1024.0


class StyleUpdateRequest(BaseModel):
    layer_id: str
    style: Dict[str, Any]


router = APIRouter()


# Layer styling endpoint
@router.put("/layers/{layer_id}/style")
async def update_layer_style_endpoint(
    layer_id: str, style_data: Dict[str, Any]
) -> Dict[str, str]:
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
    """Uploads a file either to Azure Blob Storage or local disk.

    Returns its public URL and unique ID. File size is limited to 100MB.
    """
    # Check file size before reading content - FastAPI can access content_length from header
    content_length = getattr(file, "size", None)
    if content_length is None:
        # If file.size is not available, we'll check after reading
        content = await file.read()
        content_length = len(content)
        if content_length > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,  # Request Entity Too Large
                detail=(
                    f"File size ({format_file_size(content_length)}) "
                    f"exceeds the limit of 100MB."
                ),
            )
    elif content_length > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,  # Request Entity Too Large
            detail=f"File size ({format_file_size(content_length)}) exceeds the limit of 100MB.",
        )

    # Read the file content if not already read
    if "content" not in locals():
        content = await file.read()

    url, unique_name = store_file(file.filename, content)

    return {"url": url, "id": unique_name}
