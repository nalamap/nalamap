
from fastapi import APIRouter, UploadFile, File
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


router = APIRouter()

# Upload endpoint
@router.post("/upload")
async def upload_file(file: UploadFile = File(...)) -> Dict[str, str]:
    """
    Uploads a file either to Azure Blob Storage or local disk and returns its public URL and unique ID.
    """
    # Generate unique file name
    unique_name = f"{uuid.uuid4().hex}_{file.filename}"
    content = await file.read()

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