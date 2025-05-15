import os
from typing import Tuple
import uuid

from utility.string_methods import clean_allow
from core.config import AZ_CONN, AZ_CONTAINER, BASE_URL, LOCAL_UPLOAD_DIR, USE_AZURE

def store_file(name: str, content: bytes) -> Tuple[str, str]:
    """ Stores the given content in a file based on the name"""
        # Generate unique file name
    unique_name = f"{uuid.uuid4().hex}_{clean_allow(name)}"

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
    return url, unique_name