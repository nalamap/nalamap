import pytest
from unittest.mock import MagicMock, patch

from services.tools.geocoding.taginfo_fetcher import (
    TagInfoEntry,
    TagInfoFetchError,
    _fetch_paginated,
    _fetch_wiki_description,
    fetch_popular_tags,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(data: list, total: int = None, status_code: int = 200) -> MagicMock:
    """Build a mock requests.Response."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.raise_for_status = MagicMock()
    if status_code >= 400:
        from requests.exceptions import HTTPError

        mock.raise_for_status.side_effect = HTTPError(response=mock)
    mock.json.return_value = {"data": data, "total": total if total is not None else len(data)}
    return mock


def _make_tag(key="amenity", value="cafe", count_all=500) -> dict:
    return {
        "key": key,
        "value": value,
        "count_all": count_all,
        "count_nodes": count_all // 2,
        "count_ways": count_all // 4,
        "count_relations": 0,
    }


# ---------------------------------------------------------------------------
# fetch_popular_tags tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_fetch_popular_tags_returns_tag_entries():
    """Mock the API and verify TagInfoEntry objects are returned."""
    tags = [_make_tag("amenity", "cafe", 1000), _make_tag("shop", "bakery", 800)]
    with patch("services.tools.geocoding.taginfo_fetcher.requests.get") as mock_get:
        mock_get.return_value = _make_response(tags)

        result = fetch_popular_tags(min_count=100, max_tags=100, request_delay=0)

    assert len(result) == 2
    assert all(isinstance(e, TagInfoEntry) for e in result)
    keys = {e.key for e in result}
    assert "amenity" in keys
    assert "shop" in keys


@pytest.mark.unit
def test_fetch_popular_tags_filters_by_min_count():
    """Tags below min_count should be excluded."""
    tags = [
        _make_tag("amenity", "cafe", 1000),
        _make_tag("shop", "tiny", 50),  # below threshold
    ]
    with patch("services.tools.geocoding.taginfo_fetcher.requests.get") as mock_get:
        mock_get.return_value = _make_response(tags)

        result = fetch_popular_tags(min_count=100, max_tags=100, request_delay=0)

    assert len(result) == 1
    assert result[0].key == "amenity"


@pytest.mark.unit
def test_fetch_popular_tags_handles_api_error():
    """Should raise TagInfoFetchError after all retries are exhausted."""
    import requests as req

    with patch("services.tools.geocoding.taginfo_fetcher.requests.get") as mock_get:
        with patch("services.tools.geocoding.taginfo_fetcher.time.sleep"):
            mock_get.side_effect = req.RequestException("connection refused")

            with pytest.raises(TagInfoFetchError):
                fetch_popular_tags(request_delay=0)


@pytest.mark.unit
def test_fetch_popular_tags_reports_progress():
    """progress_callback should be called with (fetched, total) for each description."""
    tags = [
        _make_tag("amenity", "cafe", 1000),
        _make_tag("shop", "bakery", 800),
    ]
    wiki_response = MagicMock()
    wiki_response.status_code = 200
    wiki_response.raise_for_status = MagicMock()
    wiki_response.json.return_value = {"data": [{"lang": "en", "description": "A cafe."}]}

    progress_calls = []

    def progress(fetched, total):
        progress_calls.append((fetched, total))

    with patch("services.tools.geocoding.taginfo_fetcher.requests.get") as mock_get:
        # First call returns the popular tags; subsequent calls return wiki pages
        mock_get.side_effect = [_make_response(tags), wiki_response, wiki_response]

        fetch_popular_tags(
            min_count=100,
            max_tags=100,
            fetch_descriptions=True,
            description_limit=10,
            progress_callback=progress,
            request_delay=0,
        )

    assert len(progress_calls) == 2
    assert progress_calls[0] == (1, 2)
    assert progress_calls[1] == (2, 2)


@pytest.mark.unit
def test_fetch_wiki_description_returns_empty_on_missing():
    """Tags without wiki pages should return empty string."""
    with patch("services.tools.geocoding.taginfo_fetcher.requests.get") as mock_get:
        mock_get.return_value = _make_response([], total=0)

        result = _fetch_wiki_description("foo", "bar")

    assert result == ""


@pytest.mark.unit
def test_fetch_wiki_description_returns_english_description():
    """Should extract and return the English description from wiki pages."""
    wiki_data = [
        {"lang": "de", "description": "Ein Cafe."},
        {"lang": "en", "description": "A place serving coffee."},
    ]
    with patch("services.tools.geocoding.taginfo_fetcher.requests.get") as mock_get:
        mock_get.return_value = _make_response(wiki_data)

        result = _fetch_wiki_description("amenity", "cafe")

    assert result == "A place serving coffee."


@pytest.mark.unit
def test_pagination_handles_multiple_pages():
    """Should fetch all pages until max_items reached."""
    page1 = [_make_tag("amenity", f"v{i}", 500) for i in range(5)]
    page2 = [_make_tag("shop", f"v{i}", 500) for i in range(5)]

    resp1 = _make_response(page1, total=10)
    resp2 = _make_response(page2, total=10)

    with patch("services.tools.geocoding.taginfo_fetcher.requests.get") as mock_get:
        with patch("services.tools.geocoding.taginfo_fetcher.time.sleep"):
            mock_get.side_effect = [resp1, resp2]

            results = _fetch_paginated(
                "/tags/popular",
                params={},
                max_items=10,
                request_delay=0,
            )

    assert len(results) == 10
    assert mock_get.call_count == 2


@pytest.mark.unit
def test_pagination_respects_max_items():
    """Should not return more items than max_items even if API has more."""
    page_data = [_make_tag("amenity", f"v{i}", 500) for i in range(999)]
    resp = _make_response(page_data, total=5000)

    with patch("services.tools.geocoding.taginfo_fetcher.requests.get") as mock_get:
        mock_get.return_value = resp

        results = _fetch_paginated("/tags/popular", params={}, max_items=500, request_delay=0)

    assert len(results) == 500


@pytest.mark.unit
def test_retry_with_exponential_backoff():
    """Should retry 3 times and then raise TagInfoFetchError."""
    import requests as req

    with patch("services.tools.geocoding.taginfo_fetcher.requests.get") as mock_get:
        with patch("services.tools.geocoding.taginfo_fetcher.time.sleep") as mock_sleep:
            mock_get.side_effect = req.RequestException("timeout")

            with pytest.raises(TagInfoFetchError):
                _fetch_paginated("/tags/popular", params={}, max_items=10, request_delay=0)

    assert mock_get.call_count == 3
    # Exponential backoff: sleeps at 1s then 2s
    sleep_calls = [c.args[0] for c in mock_sleep.call_args_list]
    assert 1.0 in sleep_calls
    assert 2.0 in sleep_calls


@pytest.mark.unit
def test_rate_limit_response_handled():
    """Should handle HTTP 429 with Retry-After header."""
    rate_limited = MagicMock()
    rate_limited.status_code = 429
    rate_limited.headers = {"Retry-After": "1"}

    success = _make_response([_make_tag()], total=1)

    with patch("services.tools.geocoding.taginfo_fetcher.requests.get") as mock_get:
        with patch("services.tools.geocoding.taginfo_fetcher.time.sleep"):
            mock_get.side_effect = [rate_limited, success]

            results = _fetch_paginated("/tags/popular", params={}, max_items=10, request_delay=0)

    assert len(results) == 1
