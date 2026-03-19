"""Integration tests for the semantic resolver wired into geocoding.py (F05).

These tests exercise the resolution chain:
  AMENITY_MAPPING → raw tag → SemanticTagResolver → _expand_tags_with_llm → fuzzy

All external I/O (Overpass, Nominatim, OpenAI) is mocked.

NOTE: geocoding.py is loaded as ``services.tools._geocoding_legacy`` by the
      package __init__.py, so patch targets must use that module path.
"""

from unittest.mock import MagicMock, patch

import pytest

from services.tools.geocoding.tag_resolver import TagResolution

# The geocoding.py functions live here at runtime
_MOD = "services.tools._geocoding_legacy"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_OVERPASS_EMPTY = {"elements": []}
_OVERPASS_ONE_NODE = {
    "elements": [{"type": "node", "id": 1, "lat": 48.8, "lon": 2.3, "tags": {"amenity": "cafe"}}]
}

# A minimal location object returned by _geocode_location_for_overpass
_MOCK_LOCATION = MagicMock()
_MOCK_LOCATION.lat = 48.85
_MOCK_LOCATION.lon = 2.35
_MOCK_LOCATION.display_name = "Paris, France"
_MOCK_LOCATION.bbox = None


def _make_resolution(tags, method="semantic", detail="expanded via tag embeddings"):
    return TagResolution(tags=tags, method=method, detail=detail)


def _call_overpass(amenity_key="unknown_place", location_name="Paris"):
    """Helper: call geocode_using_overpass_to_geostate with a minimal mocked env."""
    import services.tools.geocoding as gc

    state = {"messages": [], "geodata_results": []}
    tool_call_id = "test-call-id"

    return gc.geocode_using_overpass_to_geostate.func(
        query=amenity_key,
        amenity_key=amenity_key,
        location_name=location_name,
        state=state,
        tool_call_id=tool_call_id,
    )


# ---------------------------------------------------------------------------
# Tests: semantic resolver in the chain
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_semantic_resolver_used_when_store_initialized():
    """When vector store is populated and returns enough tags (≥5), the semantic
    resolver is the primary path and _expand_tags_with_llm must NOT be called.
    (If the semantic result is thin — fewer than 5 tags — LLM supplementing fires;
    that behaviour is tested separately in test_thin_semantic_result_is_supplemented.)"""
    # Return 5 tags to simulate a "good" (non-thin) semantic result
    mock_resolution = _make_resolution(
        [
            {"key": "building", "value": "residential"},
            {"key": "building", "value": "apartments"},
            {"key": "building", "value": "house"},
            {"key": "building", "value": "detached"},
            {"key": "building", "value": "terrace"},
        ]
    )

    with (
        patch(f"{_MOD}._tag_resolver") as mock_resolver,
        patch(f"{_MOD}._expand_tags_with_llm") as mock_llm,
        patch(
            f"{_MOD}._geocode_location_for_overpass",
            return_value=(_MOCK_LOCATION, None),
        ),
        patch(
            f"{_MOD}.OverpassClient.execute_query",
            return_value=(_OVERPASS_EMPTY, None),
        ),
    ):
        mock_resolver.resolve.return_value = mock_resolution

        _call_overpass("residential buildings")

    mock_resolver.resolve.assert_called_once_with("residential buildings")
    mock_llm.assert_not_called()


@pytest.mark.unit
def test_llm_fallback_when_store_not_initialized():
    """When semantic resolver returns None (store empty), _expand_tags_with_llm is used."""
    with (
        patch(f"{_MOD}._tag_resolver") as mock_resolver,
        patch(f"{_MOD}._expand_tags_with_llm", return_value=None) as mock_llm,
        patch(
            f"{_MOD}._geocode_location_for_overpass",
            return_value=(_MOCK_LOCATION, None),
        ),
        patch(
            f"{_MOD}.OverpassClient.execute_query",
            return_value=(_OVERPASS_EMPTY, None),
        ),
    ):
        mock_resolver.resolve.return_value = None  # store not initialised

        _call_overpass("residential buildings")

    mock_resolver.resolve.assert_called_once()
    mock_llm.assert_called_once()


@pytest.mark.unit
def test_llm_fallback_when_resolver_returns_empty_tags():
    """When semantic resolver returns TagResolution with empty tags, fall back to LLM."""
    empty_resolution = _make_resolution([])

    with (
        patch(f"{_MOD}._tag_resolver") as mock_resolver,
        patch(f"{_MOD}._expand_tags_with_llm", return_value=None) as mock_llm,
        patch(
            f"{_MOD}._geocode_location_for_overpass",
            return_value=(_MOCK_LOCATION, None),
        ),
        patch(
            f"{_MOD}.OverpassClient.execute_query",
            return_value=(_OVERPASS_EMPTY, None),
        ),
    ):
        mock_resolver.resolve.return_value = empty_resolution

        _call_overpass("xyzunknown")

    mock_resolver.resolve.assert_called_once()
    mock_llm.assert_called_once()


@pytest.mark.unit
def test_static_mapping_bypasses_resolver():
    """Static AMENITY_MAPPING keys must not touch the semantic resolver."""
    with (
        patch(f"{_MOD}._tag_resolver") as mock_resolver,
        patch(
            f"{_MOD}._geocode_location_for_overpass",
            return_value=(_MOCK_LOCATION, None),
        ),
        patch(
            f"{_MOD}.OverpassClient.execute_query",
            return_value=(_OVERPASS_EMPTY, None),
        ),
    ):
        # "restaurant" is in AMENITY_MAPPING
        _call_overpass("restaurant")

    mock_resolver.resolve.assert_not_called()


@pytest.mark.unit
def test_raw_tag_bypasses_resolver():
    """Raw key=value tags must not touch the semantic resolver."""
    with (
        patch(f"{_MOD}._tag_resolver") as mock_resolver,
        patch(
            f"{_MOD}._geocode_location_for_overpass",
            return_value=(_MOCK_LOCATION, None),
        ),
        patch(
            f"{_MOD}.OverpassClient.execute_query",
            return_value=(_OVERPASS_EMPTY, None),
        ),
    ):
        _call_overpass("craft=brewery")

    mock_resolver.resolve.assert_not_called()


@pytest.mark.unit
def test_semantic_resolver_multi_tag_uses_build_multi_tag_query():
    """When semantic resolver returns multiple tags, build_multi_tag_query is used."""
    multi_resolution = _make_resolution(
        [
            {"key": "building", "value": "residential"},
            {"key": "building", "value": "apartments"},
        ]
    )

    with (
        patch(f"{_MOD}._tag_resolver") as mock_resolver,
        patch(
            f"{_MOD}._geocode_location_for_overpass",
            return_value=(_MOCK_LOCATION, None),
        ),
        patch(
            f"{_MOD}.OverpassClient.execute_query",
            return_value=(_OVERPASS_EMPTY, None),
        ),
        patch(
            f"{_MOD}.OverpassQueryBuilder.build_multi_tag_query",
            return_value="[out:json];node;out;",
        ) as mock_multi,
    ):
        mock_resolver.resolve.return_value = multi_resolution

        _call_overpass("residential buildings")

    mock_multi.assert_called_once()


@pytest.mark.unit
def test_semantic_resolver_single_tag_uses_build_amenity_query():
    """When semantic resolver returns exactly one tag and LLM supplementing returns
    nothing, build_amenity_query is used (single-tag path)."""
    single_resolution = _make_resolution([{"key": "amenity", "value": "cafe"}])

    with (
        patch(f"{_MOD}._tag_resolver") as mock_resolver,
        # LLM supplement returns None → single tag from semantic is kept as-is
        patch(f"{_MOD}._expand_tags_with_llm", return_value=None),
        patch(
            f"{_MOD}._geocode_location_for_overpass",
            return_value=(_MOCK_LOCATION, None),
        ),
        patch(
            f"{_MOD}.OverpassClient.execute_query",
            return_value=(_OVERPASS_EMPTY, None),
        ),
        patch(
            f"{_MOD}.OverpassQueryBuilder.build_amenity_query",
            return_value="[out:json];node;out;",
        ) as mock_amenity,
    ):
        mock_resolver.resolve.return_value = single_resolution

        _call_overpass("coffee place")

    mock_amenity.assert_called_once()


@pytest.mark.unit
def test_resolver_not_called_when_static_mapping_hit():
    """A key found in AMENITY_MAPPING must result in zero resolver calls."""
    import services.tools.geocoding as gc

    # Make sure "restaurant" is in the mapping (it should be)
    assert "restaurant" in gc.AMENITY_MAPPING, "test requires 'restaurant' in AMENITY_MAPPING"

    with (
        patch(f"{_MOD}._tag_resolver") as mock_resolver,
        patch(
            f"{_MOD}._geocode_location_for_overpass",
            return_value=(_MOCK_LOCATION, None),
        ),
        patch(
            f"{_MOD}.OverpassClient.execute_query",
            return_value=(_OVERPASS_EMPTY, None),
        ),
    ):
        _call_overpass("restaurant")

    mock_resolver.resolve.assert_not_called()


@pytest.mark.unit
def test_thin_semantic_result_is_supplemented_with_llm():
    """When semantic resolver returns fewer than 5 tags (thin result), the code
    calls _expand_tags_with_llm to supplement — combining both tag sets."""
    thin_resolution = _make_resolution(
        [
            {"key": "building", "value": "residential"},
            {"key": "building", "value": "house"},
        ]
    )
    llm_extra = [
        {"key": "building", "value": "detached"},
        {"key": "building", "value": "semidetached_house"},
        {"key": "building", "value": "terrace"},
        {"key": "building", "value": "apartments"},
    ]

    with (
        patch(f"{_MOD}._tag_resolver") as mock_resolver,
        patch(f"{_MOD}._expand_tags_with_llm", return_value=llm_extra) as mock_llm,
        patch(
            f"{_MOD}._geocode_location_for_overpass",
            return_value=(_MOCK_LOCATION, None),
        ),
        patch(
            f"{_MOD}.OverpassClient.execute_query",
            return_value=(_OVERPASS_EMPTY, None),
        ),
        patch(
            f"{_MOD}.OverpassQueryBuilder.build_multi_tag_query",
            return_value="[out:json];node;out;",
        ) as mock_multi,
    ):
        mock_resolver.resolve.return_value = thin_resolution
        _call_overpass("residential buildings")

    # LLM supplement must have been called once
    mock_llm.assert_called_once_with("residential buildings")
    # Combined result has >1 tag → multi-tag query path
    mock_multi.assert_called_once()
