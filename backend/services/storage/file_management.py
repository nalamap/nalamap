import os
import uuid
import gzip
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

# Minimum file size for compression (1MB)
MIN_COMPRESS_SIZE = 1024 * 1024


def _should_compress_for_azure(filename: str, size: int) -> bool:
    """Determine if file should be compressed before Azure upload.

    Args:
        filename: Name of the file
        size: Size of the file in bytes

    Returns:
        True if file should be compressed
    """
    # Only compress GeoJSON files larger than 1MB
    return filename.lower().endswith(".geojson") and size > MIN_COMPRESS_SIZE


def _compress_for_azure(content: bytes) -> bytes:
    """Compress content using gzip.

    Args:
        content: Raw file content

    Returns:
        Compressed content
    """
    return gzip.compress(content, compresslevel=6)


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
    For GeoJSON files >1MB, automatically compresses with gzip to save bandwidth and storage.
    """
    # Generate unique file name
    safe_name = sanitize_filename(name)
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"

    if USE_AZURE:
        from azure.storage.blob import BlobServiceClient, ContentSettings

        blob_svc = BlobServiceClient.from_connection_string(AZ_CONN)
        container = blob_svc.get_container_client(AZ_CONTAINER)

        # Check if we should compress
        should_compress = _should_compress_for_azure(safe_name, len(content))

        if should_compress:
            # Compress the content
            compressed_content = _compress_for_azure(content)
            original_size = len(content)
            compressed_size = len(compressed_content)
            compression_ratio = (1 - compressed_size / original_size) * 100

            print(
                f"Compressed {safe_name}: {original_size} -> {compressed_size} bytes "
                f"({compression_ratio:.1f}% reduction)"
            )

            # Upload with Content-Encoding header so browsers auto-decompress
            container.upload_blob(
                name=unique_name,
                data=compressed_content,
                content_settings=ContentSettings(
                    content_type="application/geo+json", content_encoding="gzip"
                ),
            )
        else:
            # Upload without compression
            container.upload_blob(name=unique_name, data=content)

        # Generate secure SAS URL instead of public URL
        blob_url = f"{container.url}/{unique_name}"
        url = _generate_sas_url(blob_url, unique_name)
    else:
        dest_path = os.path.join(LOCAL_UPLOAD_DIR, unique_name)
        with open(dest_path, "wb") as f:
            f.write(content)
        url = f"{BASE_URL}/api/stream/{unique_name}"
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
        from azure.storage.blob import BlobServiceClient, ContentSettings

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
            # For GeoJSON files >1MB, compress before upload
            # Note: We need to read entire stream into memory for compression
            if _should_compress_for_azure(safe_name, MAX_FILE_SIZE):
                # Read stream content (respecting size limit)
                content = limiter.read()

                # Check actual size
                actual_size = len(content)
                if _should_compress_for_azure(safe_name, actual_size):
                    # Compress
                    compressed_content = _compress_for_azure(content)
                    compression_ratio = (1 - len(compressed_content) / actual_size) * 100

                    print(
                        f"Compressed {safe_name}: {actual_size} -> "
                        f"{len(compressed_content)} bytes ({compression_ratio:.1f}% reduction)"
                    )

                    # Upload compressed with Content-Encoding header
                    blob_client.upload_blob(
                        data=compressed_content,
                        overwrite=True,
                        content_settings=ContentSettings(
                            content_type="application/geo+json", content_encoding="gzip"
                        ),
                    )
                else:
                    # File smaller than threshold, upload without compression
                    blob_client.upload_blob(data=content, overwrite=True)
            else:
                # Non-GeoJSON or small file, stream directly
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
            url = f"{BASE_URL}/api/stream/{unique_name}"
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
