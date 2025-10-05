import os
import uuid
from datetime import datetime, timedelta
from typing import Tuple, BinaryIO

from core.config import (
    AZ_CONN,
    AZ_CONTAINER,
    AZURE_SAS_EXPIRY_HOURS,
    BASE_URL,
    LOCAL_UPLOAD_DIR,
    USE_AZURE,
)
from utility.string_methods import sanitize_filename


def _generate_sas_url(blob_url: str, blob_name: str) -> str:
    """Generate a time-limited SAS URL for secure blob access.

    Falls back to public URL if SAS generation fails.

    Args:
        blob_url: The base blob URL
        blob_name: The blob name/path

    Returns:
        SAS URL with time-limited access token
    """
    try:
        from azure.storage.blob import generate_blob_sas, BlobSasPermissions

        # Parse connection string to extract account credentials
        conn_parts = dict(part.split("=", 1) for part in AZ_CONN.split(";") if "=" in part)
        account_name = conn_parts.get("AccountName")
        account_key = conn_parts.get("AccountKey")

        if not account_name or not account_key:
            # Fallback to public URL if credentials not available
            return blob_url

        # Generate SAS token with read permission
        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=AZ_CONTAINER,
            blob_name=blob_name,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(hours=AZURE_SAS_EXPIRY_HOURS),
        )

        # Construct SAS URL
        return f"{blob_url}?{sas_token}"
    except Exception as e:
        # Log error and fall back to public URL
        print(f"Warning: Failed to generate SAS URL: {e}. Using public URL.")
        return blob_url


def store_file(name: str, content: bytes) -> Tuple[str, str]:
    """Stores the given content in a file based on the name.

    Returns a time-limited SAS URL for Azure Blob Storage (more secure than public URLs).
    """
    # Generate unique file name
    safe_name = sanitize_filename(name)
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"

    if USE_AZURE:
        from azure.storage.blob import BlobServiceClient

        blob_svc = BlobServiceClient.from_connection_string(AZ_CONN)
        container = blob_svc.get_container_client(AZ_CONTAINER)
        container.upload_blob(name=unique_name, data=content)

        # Generate secure SAS URL instead of public URL
        blob_url = f"{container.url}/{unique_name}"
        url = _generate_sas_url(blob_url, unique_name)
    else:
        dest_path = os.path.join(LOCAL_UPLOAD_DIR, unique_name)
        with open(dest_path, "wb") as f:
            f.write(content)
        url = f"{BASE_URL}/uploads/{unique_name}"
    return url, unique_name


def store_file_stream(name: str, stream: BinaryIO) -> Tuple[str, str]:
    """Store file by streaming from a file-like object without loading into memory.

    Respects MAX_FILE_SIZE from config. Streams directly to local disk or Azure Blob Storage.
    """
    from core.config import MAX_FILE_SIZE

    # Generate unique sanitized name
    safe_name = sanitize_filename(name)
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"

    # Ensure directory exists for local storage
    if not USE_AZURE:
        os.makedirs(LOCAL_UPLOAD_DIR, exist_ok=True)

    total = 0
    chunk_size = 1024 * 1024  # 1 MiB chunks

    if USE_AZURE:
        from azure.storage.blob import BlobServiceClient

        blob_svc = BlobServiceClient.from_connection_string(AZ_CONN)
        container = blob_svc.get_container_client(AZ_CONTAINER)
        blob_client = container.get_blob_client(unique_name)

        class SizeLimitedReader:
            def __init__(self, base_stream: BinaryIO, limit: int):
                self._s = base_stream
                self._limit = limit
                self._read = 0

            def read(self, n: int = -1) -> bytes:
                # Read in sub-chunks to enforce limit earlier when n=-1
                data = self._s.read(n)
                if not data:
                    return data
                self._read += len(data)
                if self._read > self._limit:
                    raise RuntimeError("MAX_FILE_SIZE_EXCEEDED")
                return data

        limiter = SizeLimitedReader(stream, MAX_FILE_SIZE)
        try:
            # Stream to Azure; SDK will pull from stream in chunks
            blob_client.upload_blob(data=limiter, overwrite=True)

            # Generate secure SAS URL instead of public URL
            blob_url = f"{container.url}/{unique_name}"
            url = _generate_sas_url(blob_url, unique_name)
            return url, unique_name
        except Exception as e:
            # Best-effort cleanup of partial blob
            try:
                blob_client.delete_blob()
            except Exception:
                pass
            if str(e) == "MAX_FILE_SIZE_EXCEEDED":
                from fastapi import HTTPException

                raise HTTPException(status_code=413, detail="File exceeds the 100MB limit.")
            raise
    else:
        dest_path = os.path.join(LOCAL_UPLOAD_DIR, unique_name)
        try:
            with open(dest_path, "wb") as out:
                while True:
                    data = stream.read(chunk_size)
                    if not data:
                        break
                    total += len(data)
                    if total > MAX_FILE_SIZE:
                        raise RuntimeError("MAX_FILE_SIZE_EXCEEDED")
                    out.write(data)
            url = f"{BASE_URL}/uploads/{unique_name}"
            return url, unique_name
        except Exception as e:
            # Remove partial file
            try:
                if os.path.exists(dest_path):
                    os.remove(dest_path)
            except Exception:
                pass
            if str(e) == "MAX_FILE_SIZE_EXCEEDED":
                from fastapi import HTTPException

                raise HTTPException(status_code=413, detail="File exceeds the 100MB limit.")
            raise
