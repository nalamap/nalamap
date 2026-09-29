import gzip
import logging
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, BinaryIO, Optional, Tuple
from urllib.parse import urlparse

from core.config import (
    AZ_CONN,
    AZ_CONTAINER,
    AZURE_SAS_EXPIRY_HOURS,
    AZURE_STORAGE_ACCOUNT_URL,
    BASE_URL,
    LOCAL_UPLOAD_DIR,
    USE_AZURE,
)
from utility.string_methods import sanitize_filename

logger = logging.getLogger(__name__)

# Lower bound on a user-delegation key lifetime
MIN_KEY = timedelta(hours=1)

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


class StorageSigningError(RuntimeError):
    """Raised when a signed (SAS) blob URL cannot be produced.

    Messages never contain keys, tokens or connection strings.
    """


# Cached user-delegation key: (key, valid_from, valid_until)
_delegation_lock = threading.Lock()
_delegation_cache: Optional[Tuple[Any, datetime, datetime]] = None


def _account_name_from_url(account_url: str) -> str:
    host = urlparse(account_url).hostname or ""
    return host.split(".")[0]


def _get_user_delegation_key() -> Tuple[Any, datetime]:
    """Return (delegation_key, key_expiry), cached and refreshed at half-life."""
    global _delegation_cache
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobServiceClient

    now = datetime.now(timezone.utc)
    with _delegation_lock:
        if _delegation_cache is not None:
            key, start, expiry = _delegation_cache
            if now < start + (expiry - start) / 2:
                return key, expiry
        # Key must outlive the SAS it signs (refresh at half-life) and is capped at 7 days
        lifetime = min(timedelta(days=7), max(timedelta(hours=2 * AZURE_SAS_EXPIRY_HOURS), MIN_KEY))
        start = now - timedelta(minutes=5)  # tolerate clock skew
        expiry = now + lifetime
        client = BlobServiceClient(AZURE_STORAGE_ACCOUNT_URL, credential=DefaultAzureCredential())
        key = client.get_user_delegation_key(start, expiry)
        _delegation_cache = (key, now, expiry)
        return key, expiry


def _generate_sas_url(blob_url: str, blob_name: str) -> str:
    """Generate a time-limited, read-only SAS URL for secure blob access.

    Signs with a user-delegation key when AZURE_STORAGE_ACCOUNT_URL is set, falling back to the
    account key from AZURE_CONN_STRING. Never returns an unsigned URL.

    Raises:
        StorageSigningError: if no SAS could be produced.
    """
    from azure.storage.blob import BlobSasPermissions, generate_blob_sas

    expiry = datetime.now(timezone.utc) + timedelta(hours=AZURE_SAS_EXPIRY_HOURS)
    sas_token = None

    if AZURE_STORAGE_ACCOUNT_URL:
        try:
            key, key_expiry = _get_user_delegation_key()
            sas_token = generate_blob_sas(
                account_name=_account_name_from_url(AZURE_STORAGE_ACCOUNT_URL),
                container_name=AZ_CONTAINER,
                blob_name=blob_name,
                user_delegation_key=key,
                permission=BlobSasPermissions(read=True),
                expiry=min(expiry, key_expiry),
            )
        except Exception as e:
            logger.warning("User-delegation SAS failed (%s); trying account key.", type(e).__name__)
            sas_token = None

    if not sas_token:
        try:
            conn_parts = dict(part.split("=", 1) for part in AZ_CONN.split(";") if "=" in part)
            account_name = conn_parts.get("AccountName")
            account_key = conn_parts.get("AccountKey")
            if account_name and account_key:
                sas_token = generate_blob_sas(
                    account_name=account_name,
                    container_name=AZ_CONTAINER,
                    blob_name=blob_name,
                    account_key=account_key,
                    permission=BlobSasPermissions(read=True),
                    expiry=expiry,
                )
        except Exception as e:
            logger.error("Account-key SAS generation failed (%s).", type(e).__name__)

    if not sas_token:
        logger.error("Could not generate a SAS URL: no usable signing credential.")
        raise StorageSigningError("Unable to generate a signed URL for the stored file.")
    return f"{blob_url}?{sas_token}"


def _get_blob_service_client():
    """Blob service client from the connection string, else from the account URL + identity."""
    from azure.storage.blob import BlobServiceClient

    if AZ_CONN:
        return BlobServiceClient.from_connection_string(AZ_CONN)
    if AZURE_STORAGE_ACCOUNT_URL:
        from azure.identity import DefaultAzureCredential

        return BlobServiceClient(AZURE_STORAGE_ACCOUNT_URL, credential=DefaultAzureCredential())
    raise StorageSigningError("Azure storage is enabled but not configured.")


def store_file(name: str, content: bytes) -> Tuple[str, str]:
    """Stores the given content in a file based on the name.

    Returns a time-limited SAS URL for Azure Blob Storage (more secure than public URLs).
    For GeoJSON files >1MB, automatically compresses with gzip to save bandwidth and storage.
    """
    # Generate unique file name
    safe_name = sanitize_filename(name)
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"

    if USE_AZURE:
        from azure.storage.blob import ContentSettings

        blob_svc = _get_blob_service_client()
        container = blob_svc.get_container_client(AZ_CONTAINER)

        # Check if we should compress
        should_compress = _should_compress_for_azure(safe_name, len(content))

        if should_compress:
            # Compress the content
            compressed_content = _compress_for_azure(content)
            original_size = len(content)
            compressed_size = len(compressed_content)
            compression_ratio = (1 - compressed_size / original_size) * 100

            logger.info(
                "Compressed %s: %d -> %d bytes (%.1f%% reduction)",
                safe_name,
                original_size,
                compressed_size,
                compression_ratio,
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
        try:
            url = _generate_sas_url(blob_url, unique_name)
        except StorageSigningError:
            # Best-effort cleanup: do not leave an upload nobody can be given a URL for
            try:
                container.delete_blob(unique_name)
            except Exception:
                pass
            raise
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
        from azure.storage.blob import ContentSettings

        blob_svc = _get_blob_service_client()
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

                    logger.info(
                        "Compressed %s: %d -> %d bytes (%.1f%% reduction)",
                        safe_name,
                        actual_size,
                        len(compressed_content),
                        compression_ratio,
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
            if isinstance(e, StorageSigningError):
                from fastapi import HTTPException

                raise HTTPException(status_code=503, detail=str(e))
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
