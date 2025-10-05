"""
Streaming file endpoint for efficient serving of large GeoJSON files.

This endpoint provides:
- Chunked streaming transfer for large files
- Proper content-type handling for GeoJSON
- Range request support
- Gzip compression support for large files
- Better memory efficiency than StaticFiles for large files
"""
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Request
from fastapi.responses import StreamingResponse

from core.config import LOCAL_UPLOAD_DIR
from services.compression.gzip_utils import (
    get_file_to_serve,
    compress_file,
    should_compress_file,
)

router = APIRouter(tags=["file-streaming"])

logger = logging.getLogger(__name__)

# Chunk size for streaming (1MB)
CHUNK_SIZE = 1024 * 1024


def get_file_path(filename: str) -> Path:
    """
    Validate and get the full file path.

    Args:
        filename: Name of the file to serve

    Returns:
        Path object for the file

    Raises:
        HTTPException: If file doesn't exist or path is invalid
    """
    # Prevent directory traversal
    if ".." in filename or filename.startswith("/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename",
        )

    file_path = Path(LOCAL_UPLOAD_DIR) / filename
    file_path = file_path.resolve()

    # Ensure the file is within the upload directory
    upload_dir_resolved = Path(LOCAL_UPLOAD_DIR).resolve()
    try:
        file_path.relative_to(upload_dir_resolved)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path",
        )

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not a file",
        )

    return file_path


def file_iterator(file_path: Path, start: int = 0, end: Optional[int] = None):
    """
    Generator to yield file chunks.

    Args:
        file_path: Path to the file
        start: Start byte position
        end: End byte position (None for end of file)

    Yields:
        Chunks of file data
    """
    with open(file_path, "rb") as f:
        f.seek(start)
        remaining = end - start + 1 if end else None

        while True:
            chunk_size = CHUNK_SIZE
            if remaining is not None:
                chunk_size = min(chunk_size, remaining)

            chunk = f.read(chunk_size)
            if not chunk:
                break

            yield chunk

            if remaining is not None:
                remaining -= len(chunk)
                if remaining <= 0:
                    break


def get_content_type(filename: str) -> str:
    """
    Determine content type based on file extension.

    Args:
        filename: Name of the file

    Returns:
        MIME type string
    """
    if filename.endswith(".geojson"):
        return "application/geo+json"
    elif filename.endswith(".json"):
        return "application/json"
    elif filename.endswith(".gz"):
        return "application/gzip"
    else:
        return "application/octet-stream"


@router.get("/stream/{filename:path}")
async def stream_file(filename: str, request: Request):
    """
    Stream a file with support for range requests and gzip compression.

    This endpoint efficiently streams large files using chunked transfer,
    reducing memory usage compared to loading entire files into memory.
    For large files (>1MB), serves pre-compressed .gz version if available.

    Args:
        filename: Path to the file relative to upload directory
        request: FastAPI request object (for range and accept-encoding headers)

    Returns:
        StreamingResponse with file content (optionally compressed)

    Raises:
        HTTPException: If file doesn't exist or is invalid
    """
    file_path = get_file_path(filename)

    # Check if client accepts gzip encoding
    accept_encoding = request.headers.get("accept-encoding", "")
    client_accepts_gzip = "gzip" in accept_encoding.lower()

    # Determine which file to serve (original or compressed)
    serve_path, is_compressed = get_file_to_serve(filename)

    # If not compressed but should be, compress it now
    if not is_compressed and client_accepts_gzip and should_compress_file(file_path):
        logger.info(f"Pre-compressing {filename} on first request...")
        compressed = compress_file(file_path)
        if compressed:
            serve_path = compressed
            is_compressed = True

    # Get file size
    file_size = serve_path.stat().st_size

    # Build response headers
    headers = {
        "Content-Type": get_content_type(filename),
        "Accept-Ranges": "bytes",
        "Cache-Control": "public, max-age=3600",
    }

    if is_compressed:
        headers["Content-Encoding"] = "gzip"
        # Use original filename in content-disposition
        headers["Content-Disposition"] = f'inline; filename="{filename}"'

    # Check for range request (not supported with compression)
    range_header = request.headers.get("range")

    if range_header and not is_compressed:
        # Parse range header (e.g., "bytes=0-1023")
        try:
            range_str = range_header.replace("bytes=", "")
            start, end = range_str.split("-")
            start = int(start) if start else 0
            end = int(end) if end else file_size - 1

            # Validate range
            if start >= file_size or end >= file_size or start > end:
                raise HTTPException(
                    status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
                    detail="Invalid range",
                    headers={"Content-Range": f"bytes */{file_size}"},
                )

            content_length = end - start + 1

            logger.info(
                f"Streaming file {filename} with range: "
                f"bytes {start}-{end}/{file_size}"
            )

            return StreamingResponse(
                file_iterator(serve_path, start, end),
                status_code=status.HTTP_206_PARTIAL_CONTENT,
                headers={
                    **headers,
                    "Content-Length": str(content_length),
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                },
            )
        except ValueError as e:
            logger.error(f"Invalid range header: {range_header}, error: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid range header",
            )
    else:
        # Full file stream
        compression_note = " (gzip)" if is_compressed else ""
        logger.info(
            f"Streaming full file {filename} ({file_size} bytes){compression_note}"
        )

        return StreamingResponse(
            file_iterator(serve_path),
            status_code=status.HTTP_200_OK,
            headers={
                **headers,
                "Content-Length": str(file_size),
            },
        )


@router.head("/stream/{filename:path}")
async def head_file(filename: str):
    """
    Get file metadata without downloading content.

    Args:
        filename: Path to the file relative to upload directory

    Returns:
        Response with headers only

    Raises:
        HTTPException: If file doesn't exist or is invalid
    """
    file_path = get_file_path(filename)
    file_size = file_path.stat().st_size
    mtime = file_path.stat().st_mtime

    return StreamingResponse(
        iter([]),  # Empty iterator for HEAD request
        headers={
            "Content-Type": get_content_type(filename),
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
            "Last-Modified": f"{mtime}",
            "Cache-Control": "public, max-age=3600",
        },
    )
