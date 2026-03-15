import logging
import time
from dataclasses import dataclass
from typing import Callable, List, Optional

import requests

logger = logging.getLogger(__name__)

TAGINFO_BASE_URL = "https://taginfo.openstreetmap.org/api/4"


class TagInfoFetchError(Exception):
    """Raised when all retries to fetch from TagInfo API are exhausted."""

    pass


@dataclass
class TagInfoEntry:
    """A single OSM tag with metadata from TagInfo."""

    key: str
    value: str
    count_all: int = 0
    count_nodes: int = 0
    count_ways: int = 0
    count_relations: int = 0
    description: str = ""  # English wiki description


def fetch_popular_tags(
    min_count: int = 100,
    max_tags: int = 15000,
    fetch_descriptions: bool = False,
    description_limit: int = 5000,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    request_delay: float = 0.1,
) -> List[TagInfoEntry]:
    """Fetch popular (wiki-documented) tags from the TagInfo API.

    Args:
        min_count: Minimum usage count to include a tag.
        max_tags: Maximum number of tags to fetch.
        fetch_descriptions: Whether to fetch English wiki descriptions (expensive).
        description_limit: Only fetch descriptions for top N tags by count.
        progress_callback: Optional callback(fetched, total) for progress reporting.
        request_delay: Delay in seconds between API requests (rate limiting).

    Returns:
        List of TagInfoEntry objects with descriptions where available.
    """
    raw_tags = _fetch_paginated(
        "/tags/popular",
        params={"sortname": "tag", "sortorder": "asc"},
        max_items=max_tags,
        request_delay=request_delay,
    )

    entries: List[TagInfoEntry] = []
    for raw in raw_tags:
        count = raw.get("count_all", 0)
        if count < min_count:
            continue
        entry = TagInfoEntry(
            key=raw.get("key", ""),
            value=raw.get("value", ""),
            count_all=count,
            count_nodes=raw.get("count_nodes", 0),
            count_ways=raw.get("count_ways", 0),
            count_relations=raw.get("count_relations", 0),
        )
        entries.append(entry)

    # Sort by count descending so description_limit applies to most-used tags
    entries.sort(key=lambda e: e.count_all, reverse=True)

    if fetch_descriptions:
        total = min(len(entries), description_limit)
        for i, entry in enumerate(entries[:total]):
            entry.description = _fetch_wiki_description(
                entry.key, entry.value, request_delay=request_delay
            )
            if progress_callback:
                progress_callback(i + 1, total)

    return entries


def _fetch_paginated(
    endpoint: str,
    params: dict,
    max_items: int,
    request_delay: float = 0.1,
) -> List[dict]:
    """Fetch paginated results from a TagInfo API endpoint.

    Handles pagination (page/rp parameters), retries (3x exponential backoff),
    and rate limiting (request_delay between pages).
    """
    results: List[dict] = []
    page = 1
    page_size = min(999, max_items)
    url = f"{TAGINFO_BASE_URL}{endpoint}"

    while len(results) < max_items:
        page_params = dict(params)
        page_params["page"] = page
        page_params["rp"] = page_size

        data = _request_with_retry(url, page_params)
        if data is None:
            break

        items = data.get("data", [])
        if not items:
            break

        results.extend(items)

        total = data.get("total", 0)
        if len(results) >= total or len(results) >= max_items:
            break

        page += 1
        time.sleep(request_delay)

    return results[:max_items]


def _request_with_retry(url: str, params: dict, max_retries: int = 3) -> Optional[dict]:
    """Make a GET request with exponential backoff retry logic.

    Returns parsed JSON dict on success, None if all retries are exhausted.
    Raises TagInfoFetchError if the API is consistently unavailable.
    """
    delay = 1.0
    last_error: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=30)

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", delay))
                logger.warning("Rate limited by TagInfo API, waiting %ss", retry_after)
                time.sleep(retry_after)
                continue

            response.raise_for_status()

            try:
                return response.json()
            except ValueError as e:
                logger.error("Invalid JSON from TagInfo API at %s: %s", url, e)
                return None

        except requests.RequestException as e:
            last_error = e
            logger.warning(
                "TagInfo API request failed (attempt %d/%d): %s",
                attempt + 1,
                max_retries,
                e,
            )
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2

    raise TagInfoFetchError(f"TagInfo API unavailable after {max_retries} attempts: {last_error}")


def _fetch_wiki_description(key: str, value: str, request_delay: float = 0.0) -> str:
    """Fetch English wiki description for a specific tag.

    Returns empty string if no wiki page exists or request fails.
    """
    url = f"{TAGINFO_BASE_URL}/tag/wiki_pages"
    params = {"key": key, "value": value}

    try:
        data = _request_with_retry(url, params)
        if data is None:
            return ""

        for page in data.get("data", []):
            if page.get("lang") == "en":
                description = page.get("description", "")
                if description:
                    if request_delay:
                        time.sleep(request_delay)
                    return description

    except TagInfoFetchError as e:
        logger.warning("Could not fetch wiki description for %s=%s: %s", key, value, e)

    return ""
