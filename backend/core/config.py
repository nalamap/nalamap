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

# External OGC API server (for uploads and file serving)
USE_OGCAPI_STORAGE = os.getenv("USE_OGCAPI_STORAGE", "false").lower() == "true"
OGCAPI_BASE_URL = os.getenv("OGCAPI_BASE_URL", "").rstrip("/")
OGCAPI_TIMEOUT_SECONDS = float(os.getenv("OGCAPI_TIMEOUT_SECONDS", "30"))

# CORS configuration
# Comma-separated list of allowed origins; if empty, allow all (not recommended with credentials)
RAW_ALLOWED_ORIGINS = os.getenv("ALLOWED_CORS_ORIGINS", "*")
ALLOWED_CORS_ORIGINS = [o.strip() for o in RAW_ALLOWED_ORIGINS.split(",") if o.strip()]

# Frontend base URL (used for auth redirects / post-login navigation)
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")

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
DATABASE_URL = os.getenv("DATABASE_URL")

# Authentication settings
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
OIDC_PROVIDERS = [p.strip() for p in os.getenv("OIDC_PROVIDERS", "google").split(",") if p.strip()]


def _parse_oidc_provider(name: str) -> dict | None:
    """Load OIDC provider config from environment variables.

    Expected variables:
    - OIDC_<NAME>_ISSUER
    - OIDC_<NAME>_CLIENT_ID
    - OIDC_<NAME>_CLIENT_SECRET
    - OIDC_<NAME>_SCOPES (optional, space-separated; default: \"openid email profile\")
    """

    env_key = name.upper()
    issuer = os.getenv(f"OIDC_{env_key}_ISSUER")
    client_id = os.getenv(f"OIDC_{env_key}_CLIENT_ID")
    client_secret = os.getenv(f"OIDC_{env_key}_CLIENT_SECRET")
    scopes = os.getenv(f"OIDC_{env_key}_SCOPES", "openid email profile")

    if not issuer or not client_id or not client_secret:
        return None

    return {
        "name": name,
        "issuer": issuer.rstrip("/"),
        "client_id": client_id,
        "client_secret": client_secret,
        "scopes": scopes,
    }


def get_oidc_providers() -> list[dict]:
    """Return configured OIDC providers with required fields."""
    providers: list[dict] = []
    for name in OIDC_PROVIDERS:
        provider = _parse_oidc_provider(name)
        if provider:
            providers.append(provider)
    return providers


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

# Embedding provider configuration
# Determines which embedding provider to use for GeoServer vector store
# Options: "hashing" (default), "openai", "azure"
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "hashing").lower()

# OpenAI embeddings configuration (legacy - kept for backward compatibility)
# Set USE_OPENAI_EMBEDDINGS=true to enable OpenAI embeddings
USE_OPENAI_EMBEDDINGS = os.getenv("USE_OPENAI_EMBEDDINGS", "false").lower() == "true"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

# Azure AI embeddings configuration
# Set EMBEDDING_PROVIDER=azure to enable Azure AI embeddings
USE_AZURE_EMBEDDINGS = os.getenv("USE_AZURE_EMBEDDINGS", "false").lower() == "true"
AZURE_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "")
AZURE_EMBEDDING_MODEL = os.getenv(
    "AZURE_EMBEDDING_MODEL", "text-embedding-3-small"
)  # Model name for Azure OpenAI


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


# MCP (Model Context Protocol) Configuration --------------------------------------------

# Enable MCP server to expose NaLaMap tools to external AI assistants
MCP_ENABLED = _env_bool("MCP_ENABLED", default="false")

# MCP server port (if running standalone, not used with FastAPI integration)
MCP_SERVER_PORT = int(os.getenv("MCP_SERVER_PORT", "8001"))

# External MCP servers to connect to (comma-separated URLs)
# Example: "http://localhost:3001/mcp,http://tools.example.com/mcp"
RAW_MCP_EXTERNAL_SERVERS = os.getenv("MCP_EXTERNAL_SERVERS", "")
MCP_EXTERNAL_SERVERS = [url.strip() for url in RAW_MCP_EXTERNAL_SERVERS.split(",") if url.strip()]
