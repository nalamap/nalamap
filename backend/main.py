import logging
import mimetypes
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from api import (
    ai_style,
    auto_styling,
    data_management,
    debug,
    file_streaming,
    mcp,
    nalamap,
    proxy,
    settings,
)

# from sqlalchemy.ext.asyncio import AsyncSession
from core.config import ALLOWED_CORS_ORIGINS, LOCAL_UPLOAD_DIR
from services.deployment_config_loader import load_and_validate_config
from services.startup_preloader import schedule_startup_preload

# Configure logging with environment variable support
# Set LOG_LEVEL=WARNING in production to reduce noise, DEBUG for verbose output
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


tags_metadata = [
    {
        "name": "debug",
        "description": (
            "The debug methods are used for directly interacting with the " "models and tools"
        ),
    },
    {
        "name": "nalamap",
        "description": "NaLaMap API endpoints can be used to interact with the "
        "NaLaMap answer geospatial questions.",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager for startup/shutdown events."""
    # Startup
    logger.info("NaLaMap API starting up...")

    # Load and validate deployment configuration
    config_result = load_and_validate_config()
    if config_result.valid and config_result.config:
        config_name = config_result.config.config_name or "(unnamed)"
        logger.info(f"Deployment configuration loaded: {config_name}")
        if config_result.warnings:
            for warning in config_result.warnings:
                logger.warning(f"Config warning: {warning}")

        # Schedule startup preload for GeoServer backends (runs in background)
        # This preloads backends marked with preload_on_startup=True
        schedule_startup_preload()
    else:
        logger.info("No deployment configuration found, using defaults")

    yield

    # Shutdown
    logger.info("NaLaMap API shutting down...")


app = FastAPI(
    title="NaLaMap API",
    description="API for making geospatial data accessible",
    version="0.1.0",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)

# CORS
if ALLOWED_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    # Fallback: allow all origins but disable credentials to satisfy CORS spec
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Local upload directory and base URL
# Ensure GeoJSON files are served with an explicit media type
mimetypes.add_type("application/geo+json", ".geojson")

os.makedirs(LOCAL_UPLOAD_DIR, exist_ok=True)

# Legacy /uploads/ endpoint using StaticFiles
# NOTE: This may have issues with large files in Azure Container Apps
# Prefer using /api/stream/ for new code (uses async generator)
# We keep this for backward compatibility, but redirect internally where possible
app.mount("/uploads", StaticFiles(directory=LOCAL_UPLOAD_DIR), name="uploads")

# Include API routers
app.include_router(debug.router, prefix="/api")
app.include_router(nalamap.router, prefix="/api")  # Main chat functionality
app.include_router(data_management.router, prefix="/api")
app.include_router(ai_style.router, prefix="/api")  # AI Style button functionality
app.include_router(auto_styling.router, prefix="/api")  # Automatic styling
app.include_router(settings.router, prefix="/api")
app.include_router(file_streaming.router, prefix="/api")  # Streaming files
app.include_router(mcp.router, prefix="/api")  # MCP server endpoint
app.include_router(proxy.router, prefix="/api/proxy")  # CORS proxy for external data


@app.get("/")
async def root():
    return {"message": "NaLaMap API is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "NaLaMap API is running"}


# Exception handlers


@app.exception_handler(status.HTTP_400_BAD_REQUEST)
async def validation_exception_handler_400(request: Request, exc):
    exc_str = f"{exc}".replace("\n", " ").replace("   ", " ")
    logging.error(f"{request}: {exc_str}")
    content = {"status_code": 10400, "message": exc_str, "data": None}
    return JSONResponse(content=content, status_code=status.HTTP_400_BAD_REQUEST)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler_422(request: Request, exc: RequestValidationError):
    exc_str = f"{exc}".replace("\n", " ").replace("   ", " ")
    logging.error(f"{request}: {exc_str}")
    content = {"status_code": 10422, "message": exc_str, "data": None}
    return JSONResponse(content=content, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


@app.exception_handler(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
async def request_entity_too_large_handler(request: Request, exc):
    return JSONResponse(
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        content={"detail": "File size exceeds the 100MB limit. Please upload a smaller file."},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
