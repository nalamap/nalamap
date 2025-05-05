from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import Dict
import os
import uuid

# TODO: Move configs to /core/config.py 

# Optional Azure Blob storage
USE_AZURE = os.getenv("USE_AZURE_STORAGE", "false").lower() == "true"
AZ_CONN = os.getenv("AZURE_CONN_STRING", "")
AZ_CONTAINER = os.getenv("AZURE_CONTAINER", "")
# Local upload directory and base URL
LOCAL_UPLOAD_DIR = os.getenv("LOCAL_UPLOAD_DIR", "./uploads")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

# File size limit (100MB)
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB in bytes

# Helper function for formatting file size
def format_file_size(bytes_size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024 or unit == 'GB':
            return f"{bytes_size:.2f} {unit}" if unit != 'B' else f"{bytes_size} {unit}"
        bytes_size /= 1024.0

router = APIRouter()

# Upload endpoint
@router.post("/upload")
async def upload_file(file: UploadFile = File(...)) -> Dict[str, str]:
    """
    Uploads a file either to Azure Blob Storage or local disk and returns its public URL and unique ID.
    File size is limited to 100MB.
    """
    # Check file size before reading content - FastAPI can access content_length from header
    content_length = getattr(file, 'size', None)
    if content_length is None:
        # If file.size is not available, we'll check after reading
        content = await file.read()
        content_length = len(content)
        if content_length > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,  # Request Entity Too Large
                detail=f"File size ({format_file_size(content_length)}) exceeds the limit of 100MB."
            )
    elif content_length > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,  # Request Entity Too Large
            detail=f"File size ({format_file_size(content_length)}) exceeds the limit of 100MB."
        )
        
    # Read the file content if not already read
    if 'content' not in locals():
        content = await file.read()
    
    # Generate unique file name
    unique_name = f"{uuid.uuid4().hex}_{file.filename}"

    if USE_AZURE:
        from azure.storage.blob import BlobServiceClient
        blob_svc = BlobServiceClient.from_connection_string(AZ_CONN)
        container = blob_svc.get_container_client(AZ_CONTAINER)
        container.upload_blob(name=unique_name, data=content)
        url = f"{container.url}/{unique_name}"
    else:
        dest_path = os.path.join(LOCAL_UPLOAD_DIR, unique_name)
        with open(dest_path, "wb") as f:
            f.write(content)
        url = f"{BASE_URL}/uploads/{unique_name}"

    return {"url": url, "id": unique_name}