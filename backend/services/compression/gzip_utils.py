"""
Gzip compression utilities for GeoJSON files.

Pre-compresses large GeoJSON files to reduce transfer size and improve performance.
"""
import gzip
import logging
from pathlib import Path
from typing import Optional

from core.config import LOCAL_UPLOAD_DIR

logger = logging.getLogger(__name__)

# Minimum file size for compression (1MB)
MIN_COMPRESSION_SIZE = 1024 * 1024


def should_compress_file(file_path: Path) -> bool:
    """
    Determine if a file should be compressed.

    Args:
        file_path: Path to the file

    Returns:
        True if file should be compressed, False otherwise
    """
    # Check if file is large enough
    if not file_path.exists():
        return False

    file_size = file_path.stat().st_size
    if file_size < MIN_COMPRESSION_SIZE:
        return False

    # Check if it's a GeoJSON file
    if file_path.suffix not in [".geojson", ".json"]:
        return False

    # Check if already compressed
    compressed_path = get_compressed_path(file_path)
    if compressed_path.exists():
        # Check if compressed version is up-to-date
        original_mtime = file_path.stat().st_mtime
        compressed_mtime = compressed_path.stat().st_mtime
        if compressed_mtime >= original_mtime:
            return False

    return True


def get_compressed_path(file_path: Path) -> Path:
    """
    Get the path for the compressed version of a file.

    Args:
        file_path: Path to the original file

    Returns:
        Path to the compressed file (.gz)
    """
    return file_path.with_suffix(file_path.suffix + ".gz")


def compress_file(file_path: Path, compression_level: int = 6) -> Optional[Path]:
    """
    Compress a file using gzip.

    Args:
        file_path: Path to the file to compress
        compression_level: Compression level (1-9, default 6)

    Returns:
        Path to compressed file, or None if compression failed
    """
    try:
        compressed_path = get_compressed_path(file_path)

        logger.info(f"Compressing {file_path.name}...")

        with open(file_path, "rb") as f_in:
            with gzip.open(
                compressed_path, "wb", compresslevel=compression_level
            ) as f_out:
                # Read and write in chunks
                chunk_size = 1024 * 1024  # 1MB chunks
                while True:
                    chunk = f_in.read(chunk_size)
                    if not chunk:
                        break
                    f_out.write(chunk)

        # Log compression ratio
        original_size = file_path.stat().st_size
        compressed_size = compressed_path.stat().st_size
        ratio = (1 - compressed_size / original_size) * 100

        logger.info(
            f"Compressed {file_path.name}: "
            f"{original_size / 1024 / 1024:.2f} MB -> "
            f"{compressed_size / 1024 / 1024:.2f} MB "
            f"({ratio:.1f}% reduction)"
        )

        return compressed_path

    except Exception as e:
        logger.error(f"Failed to compress {file_path.name}: {e}")
        return None


def compress_directory(
    directory: Optional[Path] = None, min_size_mb: float = 1.0
) -> list[Path]:
    """
    Compress all eligible files in a directory.

    Args:
        directory: Directory to compress files in (default: LOCAL_UPLOAD_DIR)
        min_size_mb: Minimum file size in MB for compression

    Returns:
        List of compressed file paths
    """
    if directory is None:
        directory = Path(LOCAL_UPLOAD_DIR)

    min_size_bytes = int(min_size_mb * 1024 * 1024)
    compressed_files = []

    logger.info(f"Scanning {directory} for files to compress...")

    for file_path in directory.glob("**/*.geojson"):
        if file_path.stat().st_size >= min_size_bytes:
            if should_compress_file(file_path):
                compressed_path = compress_file(file_path)
                if compressed_path:
                    compressed_files.append(compressed_path)

    logger.info(f"Compressed {len(compressed_files)} files")

    return compressed_files


def get_file_to_serve(filename: str) -> tuple[Path, bool]:
    """
    Determine which file to serve (original or compressed).

    Args:
        filename: Name of the requested file

    Returns:
        Tuple of (file_path, is_compressed)
    """
    original_path = Path(LOCAL_UPLOAD_DIR) / filename
    compressed_path = get_compressed_path(original_path)

    # If compressed version exists and is up-to-date, use it
    if compressed_path.exists():
        if original_path.exists():
            original_mtime = original_path.stat().st_mtime
            compressed_mtime = compressed_path.stat().st_mtime
            if compressed_mtime >= original_mtime:
                return compressed_path, True
        else:
            # Original doesn't exist but compressed does
            return compressed_path, True

    # Use original file
    return original_path, False
