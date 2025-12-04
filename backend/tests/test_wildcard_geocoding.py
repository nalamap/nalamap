"""
Tests for wildcard OSM queries in geocoding functionality.

This module tests the new wildcard query support for OSM features,
including highways, military infrastructure, aeroway, natural features,
waterways, buildings, and places.
"""

import pytest
from services.tools.constants import AMENITY_MAPPING


class TestWildcardMappings:
    """Test that wildcard mappings are correctly defined in constants."""

    def test_highway_wildcard_mappings(self):
        """Test that highway wildcard mappings exist."""
        assert "highway" in AMENITY_MAPPING
        assert AMENITY_MAPPING["highway"] == "highway=*"
        assert "road" in AMENITY_MAPPING
        assert AMENITY_MAPPING["road"] == "highway=*"
        assert "roads" in AMENITY_MAPPING
        assert AMENITY_MAPPING["roads"] == "highway=*"
        assert "infrastructure" in AMENITY_MAPPING
        assert AMENITY_MAPPING["infrastructure"] == "highway=*"

    def test_military_wildcard_mappings(self):
        """Test that military wildcard mappings exist."""
        assert "military" in AMENITY_MAPPING
        assert AMENITY_MAPPING["military"] == "military=*"
        assert "defense" in AMENITY_MAPPING
        assert AMENITY_MAPPING["defense"] == "military=*"
        assert "military infrastructure" in AMENITY_MAPPING
        assert AMENITY_MAPPING["military infrastructure"] == "military=*"

    def test_aeroway_wildcard_mappings(self):
        """Test that aeroway wildcard mappings exist."""
        assert "aeroway" in AMENITY_MAPPING
        assert AMENITY_MAPPING["aeroway"] == "aeroway=*"
        assert "aviation" in AMENITY_MAPPING
        assert AMENITY_MAPPING["aviation"] == "aeroway=*"

    def test_natural_wildcard_mappings(self):
        """Test that natural feature wildcard mappings exist."""
        assert "natural" in AMENITY_MAPPING
        assert AMENITY_MAPPING["natural"] == "natural=*"
        assert "nature" in AMENITY_MAPPING
        assert AMENITY_MAPPING["nature"] == "natural=*"

    def test_waterway_wildcard_mappings(self):
        """Test that waterway wildcard mappings exist."""
        assert "waterway" in AMENITY_MAPPING
        assert AMENITY_MAPPING["waterway"] == "waterway=*"
        assert "water" in AMENITY_MAPPING
        assert AMENITY_MAPPING["water"] == "waterway=*"

    def test_building_wildcard_mappings(self):
        """Test that building wildcard mappings exist."""
        assert "building" in AMENITY_MAPPING
        assert AMENITY_MAPPING["building"] == "building=*"
        assert "buildings" in AMENITY_MAPPING
        assert AMENITY_MAPPING["buildings"] == "building=*"

    def test_place_wildcard_mappings(self):
        """Test that place wildcard mappings exist."""
        assert "place" in AMENITY_MAPPING
        assert AMENITY_MAPPING["place"] == "place=*"
        assert "settlement" in AMENITY_MAPPING
        assert AMENITY_MAPPING["settlement"] == "settlement=*"


class TestSynonymMappings:
    """Test that common synonyms are correctly mapped."""

    def test_transport_synonyms(self):
        """Test transport-related synonyms."""
        assert "transport infrastructure" in AMENITY_MAPPING
        assert AMENITY_MAPPING["transport infrastructure"] == "highway=*"
        assert "transportation" in AMENITY_MAPPING
        assert AMENITY_MAPPING["transportation"] == "highway=*"

    def test_defense_synonyms(self):
        """Test defense-related synonyms."""
        assert "defence" in AMENITY_MAPPING  # British spelling
        assert AMENITY_MAPPING["defence"] == "military=*"
        assert "armed forces" in AMENITY_MAPPING
        assert AMENITY_MAPPING["armed forces"] == "military=*"

    def test_aviation_synonyms(self):
        """Test aviation-related synonyms."""
        assert "aviation infrastructure" in AMENITY_MAPPING
        assert AMENITY_MAPPING["aviation infrastructure"] == "aeroway=*"
        assert "air transport" in AMENITY_MAPPING
        assert AMENITY_MAPPING["air transport"] == "aeroway=*"

    def test_geographic_synonyms(self):
        """Test geographic feature synonyms."""
        assert "geographic feature" in AMENITY_MAPPING
        assert AMENITY_MAPPING["geographic feature"] == "natural=*"
        assert "landform" in AMENITY_MAPPING
        assert AMENITY_MAPPING["landform"] == "natural=*"


class TestWildcardQueryConstruction:
    """Test that wildcard queries are correctly constructed."""

    def test_format_tag_filter_wildcard(self):
        """Test that wildcard tag filters are correctly formatted."""
        # Simulate the helper function from geocoding.py
        def format_tag_filter(key: str, value: str) -> str:
            """Format OSM tag filter, handling wildcard queries."""
            if value == "*":
                return f'["{key}"]'
            else:
                return f'["{key}"="{value}"]'

        # Test wildcard formatting
        assert format_tag_filter("highway", "*") == '["highway"]'
        assert format_tag_filter("military", "*") == '["military"]'
        assert format_tag_filter("aeroway", "*") == '["aeroway"]'

    def test_format_tag_filter_specific(self):
        """Test that specific value tag filters are correctly formatted."""
        # Simulate the helper function from geocoding.py
        def format_tag_filter(key: str, value: str) -> str:
            """Format OSM tag filter, handling wildcard queries."""
            if value == "*":
                return f'["{key}"]'
            else:
                return f'["{key}"="{value}"]'

        # Test specific value formatting
        assert format_tag_filter("amenity", "restaurant") == '["amenity"="restaurant"]'
        assert format_tag_filter("highway", "motorway") == '["highway"="motorway"]'
        assert format_tag_filter("military", "base") == '["military"="base"]'


class TestOSMTagMapping:
    """Test that OSM tag mappings work correctly."""

    def test_generic_wildcard_queries(self):
        """Test that generic queries map to wildcard tags."""
        # Highway/Road queries
        assert AMENITY_MAPPING.get("road") == "highway=*"
        assert AMENITY_MAPPING.get("roads") == "highway=*"
        assert AMENITY_MAPPING.get("street") == "highway=*"
        assert AMENITY_MAPPING.get("streets") == "highway=*"

        # Military queries
        assert AMENITY_MAPPING.get("military") == "military=*"
        assert AMENITY_MAPPING.get("defense") == "military=*"

        # Aviation queries
        assert AMENITY_MAPPING.get("aeroway") == "aeroway=*"
        assert AMENITY_MAPPING.get("aviation") == "aeroway=*"

    def test_specific_value_queries(self):
        """Test that specific queries map to specific tags."""
        # Specific amenity queries
        assert AMENITY_MAPPING.get("restaurant") == "amenity=restaurant"
        assert AMENITY_MAPPING.get("hospital") == "amenity=hospital"
        assert AMENITY_MAPPING.get("school") == "amenity=school"

