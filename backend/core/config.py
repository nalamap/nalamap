import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
# General config in a central place


# File & Data Management

# Optional Azure Blob storage
USE_AZURE = os.getenv("USE_AZURE_STORAGE", "false").lower() == "true"
AZ_CONN = os.getenv("AZURE_CONN_STRING", "")
AZ_CONTAINER = os.getenv("AZURE_CONTAINER", "")

# Local upload directory and base URL
LOCAL_UPLOAD_DIR = os.getenv("LOCAL_UPLOAD_DIR", "./uploads")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

# File size limit (100MB)
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB in bytes


# Database

# Database connection URL
DATABASE_URL = os.getenv("DATABASE_AZURE_URL")

# ----------------------------------------------------------------------------
# Mapping / Geospatial Service Flags
# ----------------------------------------------------------------------------


def _env_bool(name: str, default: str = "false") -> bool:
    """Parse a boolean-like environment variable.

    Accepts a broad set of truthy values to be user-friendly.
    """
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on", "y"}


# Whether to hide (filter out) WMTS layers that do not offer a WebMercator
# (EPSG:3857 or common aliases) TileMatrixSet.
# Default: True to align with production mapping assumptions (WebMercator frontend).
FILTER_NON_WEBMERCATOR_WMTS = _env_bool("NALAMAP_FILTER_NON_WEBMERCATOR_WMTS", default="true")


def get_filter_non_webmercator_wmts() -> bool:
    """Return current setting for WMTS WebMercator filtering.

    Exposed as a function so tests can override the environment at runtime
    and re-query the value without needing to reload this module.
    """
    return _env_bool("NALAMAP_FILTER_NON_WEBMERCATOR_WMTS", default="true")


# GeoServer vector store configuration -------------------------------------------------


GEOSERVER_VECTOR_DB_ENV = "NALAMAP_GEOSERVER_VECTOR_DB"
GEOSERVER_EMBEDDING_FACTORY_ENV = "NALAMAP_GEOSERVER_EMBEDDING_FACTORY"
DEFAULT_GEOSERVER_VECTOR_DB_PATH = Path("data/geoserver_vectors.db")


def get_geoserver_vector_db_path() -> Path:
    """Return the configured GeoServer vector database path."""

    custom = os.getenv(GEOSERVER_VECTOR_DB_ENV)
    if custom:
        return Path(custom)
    return DEFAULT_GEOSERVER_VECTOR_DB_PATH


def get_geoserver_embedding_factory_path() -> Optional[str]:
    """Return the dotted path to a custom GeoServer embedding factory, if set."""

    value = os.getenv(GEOSERVER_EMBEDDING_FACTORY_ENV)
    return value or None
