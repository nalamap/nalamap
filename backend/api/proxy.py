"""
CORS Proxy API

Provides a proxy endpoint for fetching external GeoJSON/WFS data to bypass
CORS restrictions. This is necessary when external GeoServers don't have
proper CORS headers configured.

Security Considerations:
- Only JSON/GeoJSON responses are proxied
- Response size is limited
- Only GET requests are supported
- URL scheme must be http or https
"""

import logging
from typing import Optional
from urllib.parse import urlparse

import requests
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# Maximum response size (10MB)
MAX_PROXY_RESPONSE_SIZE = 10 * 1024 * 1024

# Allowed schemes
ALLOWED_SCHEMES = {"http", "https"}

# Request timeout in seconds
REQUEST_TIMEOUT = 60


def validate_url(url: str) -> None:
    """Validate the URL for proxying.

    Args:
        url: The URL to validate

    Raises:
        HTTPException: If the URL is invalid or not allowed
    """
    try:
        parsed = urlparse(url)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid URL format")

    if not parsed.scheme or parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise HTTPException(
            status_code=400,
            detail=f"URL scheme must be http or https, got: {parsed.scheme or 'none'}",
        )

    if not parsed.netloc:
        raise HTTPException(status_code=400, detail="URL must include a host")

    # Block localhost/private network access to prevent SSRF
    host = parsed.hostname or ""
    if host.lower() in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        raise HTTPException(
            status_code=400, detail="Proxying to localhost is not allowed"
        )

    # Block private IP ranges (basic check)
    if host.startswith("10.") or host.startswith("192.168."):
        raise HTTPException(
            status_code=400, detail="Proxying to private networks is not allowed"
        )


@router.get("/geojson")
async def proxy_geojson(
    url: str = Query(..., description="The URL to fetch GeoJSON/WFS data from"),
    srsName: Optional[str] = Query(
        None, description="Optional SRS name to add to WFS requests"
    ),
) -> JSONResponse:
    """Proxy endpoint for fetching GeoJSON/WFS data from external sources.

    This endpoint fetches GeoJSON or WFS GetFeature responses from external
    servers to bypass CORS restrictions. The response is validated to ensure
    it contains valid JSON data.

    Args:
        url: The URL to fetch data from (required)
        srsName: Optional SRS name to add to WFS requests (e.g., EPSG:4326)

    Returns:
        JSONResponse with the fetched GeoJSON data
    """
    # Validate the URL
    validate_url(url)

    # Build the request URL, optionally adding srsName for WFS
    request_url = url
    if srsName:
        separator = "&" if "?" in url else "?"
        request_url = f"{url}{separator}srsName={srsName}"

    logger.info(f"Proxying GeoJSON request to: {request_url}")

    try:
        response = requests.get(
            request_url,
            headers={
                "Accept": "application/json, application/geo+json, */*;q=0.1",
                "User-Agent": "NaLaMap-Proxy/1.0 (github.com/nalamap)",
            },
            timeout=REQUEST_TIMEOUT,
            stream=True,
        )
        response.raise_for_status()

        # Check content length if available
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > MAX_PROXY_RESPONSE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"Response too large: {content_length} bytes "
                    f"(max: {MAX_PROXY_RESPONSE_SIZE})"
                ),
            )

        # Read the response content with size limit
        content = b""
        for chunk in response.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > MAX_PROXY_RESPONSE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"Response exceeded maximum size of {MAX_PROXY_RESPONSE_SIZE} bytes",
                )

        # Parse as JSON
        try:
            json_data = response.json() if not content else __import__("json").loads(
                content.decode("utf-8")
            )
        except Exception as e:
            logger.error(f"Failed to parse response as JSON: {e}")
            raise HTTPException(
                status_code=502, detail="External server returned invalid JSON"
            )

        # Return the JSON response with CORS headers handled by FastAPI middleware
        return JSONResponse(
            content=json_data,
            headers={
                "X-Proxied-From": request_url,
                "Cache-Control": "public, max-age=300",  # Cache for 5 minutes
            },
        )

    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching from: {request_url}")
        raise HTTPException(
            status_code=504, detail="Request to external server timed out"
        )
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error fetching from {request_url}: {e}")
        raise HTTPException(
            status_code=502, detail="Could not connect to external server"
        )
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response else 502
        logger.error(f"HTTP error fetching from {request_url}: {e}")
        raise HTTPException(
            status_code=status_code,
            detail=f"External server returned error: {status_code}",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error proxying request to {request_url}: {e}")
        raise HTTPException(
            status_code=500, detail="Internal error while proxying request"
        )
