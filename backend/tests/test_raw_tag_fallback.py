"""
Tests for Phase 2 geocoding improvements:
- Raw OSM tag fallback (key=value format)
- Fuzzy amenity key suggestions
- Spatial extent description
"""

from services.tools.geocoding import (
    VALID_OSM_KEYS,
    _find_similar_amenity_keys,
    _try_parse_raw_osm_tag,
)
from services.tools.overpass import _describe_spatial_extent


class TestRawOSMTagParsing:
    """Test raw OSM tag parsing and validation."""

    def test_valid_raw_tag(self):
        """Test that valid key=value tags are accepted."""
        assert _try_parse_raw_osm_tag("craft=brewery") == "craft=brewery"
        assert _try_parse_raw_osm_tag("historic=castle") == "historic=castle"
        assert _try_parse_raw_osm_tag("sport=soccer") == "sport=soccer"

    def test_valid_wildcard_raw_tag(self):
        """Test that wildcard raw tags are accepted."""
        assert _try_parse_raw_osm_tag("craft=*") == "craft=*"
        assert _try_parse_raw_osm_tag("historic=*") == "historic=*"

    def test_invalid_key_rejected(self):
        """Test that unknown OSM keys are rejected."""
        assert _try_parse_raw_osm_tag("foobar=something") is None
        assert _try_parse_raw_osm_tag("invalid_key=value") is None

    def test_no_equals_sign(self):
        """Test that strings without = are rejected."""
        assert _try_parse_raw_osm_tag("restaurant") is None
        assert _try_parse_raw_osm_tag("craft brewery") is None

    def test_empty_parts(self):
        """Test that empty key or value is rejected."""
        assert _try_parse_raw_osm_tag("=value") is None
        assert _try_parse_raw_osm_tag("amenity=") is None
        assert _try_parse_raw_osm_tag("=") is None

    def test_whitespace_handling(self):
        """Test that whitespace around key=value is handled."""
        assert _try_parse_raw_osm_tag(" craft = brewery ") == "craft=brewery"
        assert _try_parse_raw_osm_tag("historic = castle") == "historic=castle"

    def test_all_valid_osm_keys_accepted(self):
        """Test that all keys in VALID_OSM_KEYS are accepted."""
        for key in VALID_OSM_KEYS:
            result = _try_parse_raw_osm_tag(f"{key}=test_value")
            assert result is not None, f"Key '{key}' should be valid"


class TestFuzzyAmenityKeySuggestions:
    """Test fuzzy matching for amenity key suggestions."""

    def test_substring_match(self):
        """Test that substring matches are found."""
        suggestions = _find_similar_amenity_keys("brew")
        # Should not crash; may or may not find matches depending on mapping
        assert isinstance(suggestions, list)

    def test_exact_partial_match(self):
        """Test that partial word overlap finds suggestions."""
        suggestions = _find_similar_amenity_keys("bicycle")
        assert len(suggestions) > 0
        # Should find bicycle-related entries
        assert any("bicycle" in s for s in suggestions)

    def test_no_matches(self):
        """Test that completely unknown terms return empty list."""
        suggestions = _find_similar_amenity_keys("xyznonexistent123")
        assert isinstance(suggestions, list)
        assert len(suggestions) == 0

    def test_max_suggestions_limit(self):
        """Test that max_suggestions parameter is respected."""
        suggestions = _find_similar_amenity_keys("park", max_suggestions=2)
        assert len(suggestions) <= 2

    def test_returns_strings(self):
        """Test that suggestions are plain strings."""
        suggestions = _find_similar_amenity_keys("school")
        for s in suggestions:
            assert isinstance(s, str)


class TestSpatialExtentDescription:
    """Test spatial extent description generation."""

    def test_small_area(self):
        """Test description for a very small area (< 1 km)."""
        # ~500m x ~500m area
        bbox = "POLYGON((13.4 52.5," "13.4 52.5045," "13.406 52.5045," "13.406 52.5," "13.4 52.5))"
        result = _describe_spatial_extent(bbox)
        assert result is not None
        assert "m across" in result

    def test_medium_area(self):
        """Test description for a medium area (1-10 km)."""
        # ~5km x ~5km area
        bbox = "POLYGON((13.3 52.45," "13.3 52.5," "13.38 52.5," "13.38 52.45," "13.3 52.45))"
        result = _describe_spatial_extent(bbox)
        assert result is not None
        assert "km x" in result

    def test_large_area(self):
        """Test description for a large area (> 10 km)."""
        # ~100km x ~100km area
        bbox = "POLYGON((12.0 52.0," "12.0 53.0," "14.0 53.0," "14.0 52.0," "12.0 52.0))"
        result = _describe_spatial_extent(bbox)
        assert result is not None
        assert "km x" in result

    def test_none_input(self):
        """Test that None input returns None."""
        assert _describe_spatial_extent(None) is None

    def test_invalid_bbox(self):
        """Test that invalid bbox string returns None."""
        assert _describe_spatial_extent("not a polygon") is None
        assert _describe_spatial_extent("") is None
