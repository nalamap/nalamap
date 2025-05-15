from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import Dict

from core.config import MAX_FILE_SIZE
from services.storage.file_management import store_file



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
    
    url, unique_name = store_file(file.filename, content) 

    return {"url": url, "id": unique_name}