import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file
# Load .env.local first (for local development), then .env (fallback)
load_dotenv(".env.local", override=True)  # Local development overrides
load_dotenv()  # Load .env if exists (won't override existing vars)
# General config in a central place


# File & Data Management

# Optional Azure Blob storage
USE_AZURE = os.getenv("USE_AZURE_STORAGE", "false").lower() == "true"
AZ_CONN = os.getenv("AZURE_CONN_STRING", "")
AZ_CONTAINER = os.getenv("AZURE_CONTAINER", "")

# Azure SAS token expiry (in hours) - default 24 hours for secure time-limited access
AZURE_SAS_EXPIRY_HOURS = int(os.getenv("AZURE_SAS_EXPIRY_HOURS", "24"))

# Local upload directory and base URL
LOCAL_UPLOAD_DIR = os.getenv("LOCAL_UPLOAD_DIR", "./uploads")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

# CORS configuration
# Comma-separated list of allowed origins; if empty, allow all (not recommended with credentials)
RAW_ALLOWED_ORIGINS = os.getenv("ALLOWED_CORS_ORIGINS", "")
ALLOWED_CORS_ORIGINS = [o.strip() for o in RAW_ALLOWED_ORIGINS.split(",") if o.strip()]

# Cookie Security Configuration
# In Azure Container Apps, nginx handles HTTPS termination, so backend receives HTTP.
# Set COOKIE_SECURE=false in such environments while still using HTTPS externally.
# Default to True for production security.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"
COOKIE_HTTPONLY = os.getenv("COOKIE_HTTPONLY", "true").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")  # "lax", "strict", or "none"

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

# OpenAI embeddings configuration (optional)
# Set USE_OPENAI_EMBEDDINGS=true to enable transformer-based embeddings
USE_OPENAI_EMBEDDINGS = os.getenv("USE_OPENAI_EMBEDDINGS", "false").lower() == "true"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


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
