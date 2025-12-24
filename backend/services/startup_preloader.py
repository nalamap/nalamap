"""
Startup Preloader Service

Handles preloading of GeoServer backends at server startup.
Backends configured with preload_on_startup=True in the deployment config
will have their layers embedded when the server starts.

The embeddings are stored with a special "global" session scope so they
can be shared across all user sessions.
"""

import asyncio
import logging
from models.deployment_config import DeploymentGeoServerBackend
from models.settings_model import GeoServerBackend
from services.deployment_config_loader import get_preload_backends, load_and_validate_config
from services.tools.geoserver.custom_geoserver import preload_backend_layers_with_state
from services.tools.geoserver.vector_store import set_processing_state

logger = logging.getLogger(__name__)

# Special session ID for globally preloaded embeddings
GLOBAL_PRELOAD_SESSION_ID = "__global_preload__"

# Track preload status
_preload_started = False
_preload_complete = False
_preload_results: dict = {}


def get_global_session_id() -> str:
    """Get the session ID used for globally preloaded embeddings."""
    return GLOBAL_PRELOAD_SESSION_ID


def is_preload_complete() -> bool:
    """Check if startup preloading has completed."""
    return _preload_complete


def get_preload_results() -> dict:
    """Get the results of startup preloading."""
    return _preload_results.copy()


def _normalize_geoserver_url(url: str) -> str:
    """Normalize GeoServer URL by ensuring it has a protocol."""
    url = url.strip()
    if not (url.lower().startswith("http://") or url.lower().startswith("https://")):
        url = f"https://{url}"
    return url


async def preload_backend_async(backend: DeploymentGeoServerBackend) -> dict:
    """Preload a single GeoServer backend asynchronously.

    Args:
        backend: The backend configuration to preload

    Returns:
        Dict with preload result information
    """
    backend_url = _normalize_geoserver_url(backend.url).rstrip("/")
    backend_name = backend.name or backend_url

    logger.info(f"Starting preload for backend: {backend_name} ({backend_url})")

    try:
        # Set initial state
        set_processing_state(GLOBAL_PRELOAD_SESSION_ID, backend_url, "waiting", total=0)

        # Convert to GeoServerBackend for the preload function
        geoserver_backend = GeoServerBackend(
            url=backend.url,
            name=backend.name,
            description=backend.description,
            username=backend.username,
            password=backend.password,
            enabled=backend.enabled,
            allow_insecure=backend.allow_insecure,
        )

        # Run the preload in a thread pool to not block the event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            preload_backend_layers_with_state,
            GLOBAL_PRELOAD_SESSION_ID,
            geoserver_backend,
            backend.search_term,  # Optional filter
        )

        logger.info(f"Completed preload for backend: {backend_name}")

        return {
            "backend_url": backend_url,
            "backend_name": backend_name,
            "success": True,
            "result": result,
            "error": None,
        }

    except Exception as e:
        logger.exception(f"Failed to preload backend {backend_name}: {e}")
        set_processing_state(GLOBAL_PRELOAD_SESSION_ID, backend_url, "error", error=str(e))
        return {
            "backend_url": backend_url,
            "backend_name": backend_name,
            "success": False,
            "result": None,
            "error": str(e),
        }


async def run_startup_preload() -> dict:
    """Run startup preloading for all configured backends.

    This should be called during server startup (lifespan event).

    Returns:
        Dict with overall preload results
    """
    global _preload_started, _preload_complete, _preload_results

    if _preload_started:
        logger.warning("Startup preload already started, skipping duplicate call")
        return _preload_results

    _preload_started = True

    # Load and validate deployment config
    config_result = load_and_validate_config()

    if not config_result.valid:
        logger.warning("Deployment config invalid, skipping startup preload")
        _preload_complete = True
        return {"skipped": True, "reason": "invalid_config"}

    # Get backends that should be preloaded
    preload_backends = get_preload_backends()

    if not preload_backends:
        logger.info("No backends configured for startup preload")
        _preload_complete = True
        return {"skipped": True, "reason": "no_backends"}

    logger.info(f"Starting preload for {len(preload_backends)} backend(s)")

    # Preload all backends concurrently
    results = await asyncio.gather(
        *[preload_backend_async(backend) for backend in preload_backends],
        return_exceptions=True,
    )

    # Process results
    successful = 0
    failed = 0
    backend_results = []

    for result in results:
        if isinstance(result, Exception):
            failed += 1
            backend_results.append({"success": False, "error": str(result)})
        elif isinstance(result, dict):
            if result.get("success"):
                successful += 1
            else:
                failed += 1
            backend_results.append(result)

    _preload_results = {
        "total": len(preload_backends),
        "successful": successful,
        "failed": failed,
        "backends": backend_results,
    }
    _preload_complete = True

    logger.info(
        f"Startup preload complete: {successful}/{len(preload_backends)} successful, "
        f"{failed} failed"
    )

    return _preload_results


def run_startup_preload_sync() -> dict:
    """Synchronous wrapper for startup preload.

    Use this in non-async contexts (e.g., from a background thread).
    """
    loop = None
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(run_startup_preload())
        return result
    finally:
        if loop is not None:
            loop.close()


def schedule_startup_preload():
    """Schedule startup preload to run in a background thread.

    This is useful when called from a synchronous context like FastAPI lifespan.
    """
    import threading

    def _run_preload():
        logger.info("Starting background preload thread")
        try:
            result = run_startup_preload_sync()
            logger.info(f"Background preload complete: {result}")
        except Exception as e:
            logger.exception(f"Background preload failed: {e}")

    thread = threading.Thread(target=_run_preload, daemon=True)
    thread.start()
    logger.info("Scheduled startup preload in background thread")
    return thread


def reset_preload_state():
    """Reset preload state. Useful for testing."""
    global _preload_started, _preload_complete, _preload_results
    _preload_started = False
    _preload_complete = False
    _preload_results = {}
