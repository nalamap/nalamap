import os

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
# (EPSG:3857 or common aliases) TileMatrixSet. Default: True for safety so
# the frontend map (assumed WebMercator) does not attempt to render
# incompatible projections.
FILTER_NON_WEBMERCATOR_WMTS = _env_bool("NALAMAP_FILTER_NON_WEBMERCATOR_WMTS", default="true")


def get_filter_non_webmercator_wmts() -> bool:
    """Return current setting for WMTS WebMercator filtering.

    Exposed as a function so tests can override the environment at runtime
    and re-query the value without needing to reload this module.
    """
    return _env_bool("NALAMAP_FILTER_NON_WEBMERCATOR_WMTS", default="true")
