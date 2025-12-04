"""
Tests for OSM geometry filtering functionality.

This module tests the geometry filtering system that filters OSM elements
by geometry type (node, way, relation) based on user intent and OSM key.
"""

import pytest
from services.tools.constants import OSM_GEOMETRY_PREFERENCES
from services.tools.geocoding import (
    get_geometry_preferences,
    should_include_element_in_query,
    should_include_element_in_results,
    should_include_geojson_geometry,
)


class TestConfiguration:
    """Test that OSM_GEOMETRY_PREFERENCES is properly configured."""

    def test_highway_preferences_exist(self):
        """Test that highway preferences are configured."""
        assert "highway" in OSM_GEOMETRY_PREFERENCES
        prefs = OSM_GEOMETRY_PREFERENCES["highway"]
        assert "preferred_geometries" in prefs
        assert "exclude_geometries" in prefs
        assert "exclude_values" in prefs
        assert "description" in prefs

    def test_highway_preferences_content(self):
        """Test that highway preferences have correct values."""
        prefs = OSM_GEOMETRY_PREFERENCES["highway"]
        assert "way" in prefs["preferred_geometries"]
        assert "relation" in prefs["preferred_geometries"]
        assert "node" in prefs["exclude_geometries"]
        assert "bus_stop" in prefs["exclude_values"]

    def test_railway_preferences_exist(self):
        """Test that railway preferences are configured."""
        assert "railway" in OSM_GEOMETRY_PREFERENCES
        prefs = OSM_GEOMETRY_PREFERENCES["railway"]
        assert "node" in prefs["exclude_geometries"]
        assert "station" in prefs["exclude_values"]

    def test_waterway_preferences_exist(self):
        """Test that waterway preferences are configured."""
        assert "waterway" in OSM_GEOMETRY_PREFERENCES
        prefs = OSM_GEOMETRY_PREFERENCES["waterway"]
        assert "node" in prefs["exclude_geometries"]
        assert "weir" in prefs["exclude_values"]

    def test_aeroway_preferences_exist(self):
        """Test that aeroway preferences are configured."""
        assert "aeroway" in OSM_GEOMETRY_PREFERENCES
        prefs = OSM_GEOMETRY_PREFERENCES["aeroway"]
        assert "node" in prefs["exclude_geometries"]
        assert "gate" in prefs["exclude_values"]

    def test_power_preferences_exist(self):
        """Test that power preferences are configured."""
        assert "power" in OSM_GEOMETRY_PREFERENCES
        prefs = OSM_GEOMETRY_PREFERENCES["power"]
        assert "node" in prefs["exclude_geometries"]
        assert "tower" in prefs["exclude_values"]


@pytest.mark.unit
class TestGetGeometryPreferences:
    """Test get_geometry_preferences helper function."""

    def test_returns_configured_preferences(self):
        """Test that configured keys return their preferences."""
        prefs = get_geometry_preferences("highway")
        assert prefs["preferred_geometries"] == ["way", "relation"]
        assert "node" in prefs["exclude_geometries"]

    def test_returns_default_for_unconfigured_key(self):
        """Test that unconfigured keys return default preferences."""
        prefs = get_geometry_preferences("amenity")
        assert "node" in prefs["preferred_geometries"]
        assert "way" in prefs["preferred_geometries"]
        assert "relation" in prefs["preferred_geometries"]
        assert prefs["exclude_geometries"] == []
        assert prefs["exclude_values"] == set()

    def test_all_configured_keys_return_preferences(self):
        """Test that all configured keys return valid preferences."""
        for key in OSM_GEOMETRY_PREFERENCES.keys():
            prefs = get_geometry_preferences(key)
            assert "preferred_geometries" in prefs
            assert "exclude_geometries" in prefs
            assert "exclude_values" in prefs
            assert isinstance(prefs["preferred_geometries"], list)
            assert isinstance(prefs["exclude_geometries"], list)
            assert isinstance(prefs["exclude_values"], set)


@pytest.mark.unit
class TestShouldIncludeElementInQuery:
    """Test should_include_element_in_query helper function."""

    def test_highway_wildcard_excludes_nodes(self):
        """Test that highway=* excludes nodes from query."""
        assert should_include_element_in_query("highway", "*", "node") is False
        assert should_include_element_in_query("highway", "*", "way") is True
        assert should_include_element_in_query("highway", "*", "relation") is True

    def test_highway_specific_value_includes_all(self):
        """Test that specific highway values include all types."""
        # Specific values not in exclude_values should include all
        assert should_include_element_in_query("highway", "motorway", "node") is True
        assert should_include_element_in_query("highway", "motorway", "way") is True
        assert should_include_element_in_query("highway", "motorway", "relation") is True

    def test_railway_wildcard_excludes_nodes(self):
        """Test that railway=* excludes nodes from query."""
        assert should_include_element_in_query("railway", "*", "node") is False
        assert should_include_element_in_query("railway", "*", "way") is True
        assert should_include_element_in_query("railway", "*", "relation") is True

    def test_waterway_wildcard_excludes_nodes(self):
        """Test that waterway=* excludes nodes from query."""
        assert should_include_element_in_query("waterway", "*", "node") is False
        assert should_include_element_in_query("waterway", "*", "way") is True
        assert should_include_element_in_query("waterway", "*", "relation") is True

    def test_unconfigured_key_includes_all(self):
        """Test that unconfigured keys include all element types."""
        assert should_include_element_in_query("amenity", "*", "node") is True
        assert should_include_element_in_query("amenity", "*", "way") is True
        assert should_include_element_in_query("amenity", "*", "relation") is True

    def test_excluded_specific_value(self):
        """Test that excluded specific values return False."""
        # bus_stop is in exclude_values for highway
        assert should_include_element_in_query("highway", "bus_stop", "node") is False
        assert should_include_element_in_query("highway", "bus_stop", "way") is False
        assert should_include_element_in_query("highway", "bus_stop", "relation") is False


@pytest.mark.unit
class TestShouldIncludeElementInResults:
    """Test should_include_element_in_results helper function."""

    def test_excludes_node_geometry_for_highway(self):
        """Test that nodes are excluded for highway queries."""
        element = {"type": "node", "tags": {"highway": "motorway"}}
        assert should_include_element_in_results(element, "highway", "*") is False

    def test_includes_way_geometry_for_highway(self):
        """Test that ways are included for highway queries."""
        element = {"type": "way", "tags": {"highway": "motorway"}}
        assert should_include_element_in_results(element, "highway", "*") is True

    def test_excludes_excluded_values(self):
        """Test that excluded tag values are filtered out."""
        # bus_stop is in exclude_values
        element = {"type": "way", "tags": {"highway": "bus_stop"}}
        assert should_include_element_in_results(element, "highway", "*") is False

    def test_includes_non_excluded_values(self):
        """Test that non-excluded values are included."""
        element = {"type": "way", "tags": {"highway": "motorway"}}
        assert should_include_element_in_results(element, "highway", "*") is True

    def test_wildcard_query_includes_all_highway_values(self):
        """Test that wildcard queries include all highway values (not just exact match)."""
        # For wildcard queries, any element with the highway key should be included
        # (unless excluded by geometry type or exclude_values)
        test_cases = [
            ({"type": "way", "tags": {"highway": "motorway"}}, True),
            ({"type": "way", "tags": {"highway": "primary"}}, True),
            ({"type": "way", "tags": {"highway": "secondary"}}, True),
            ({"type": "way", "tags": {"highway": "residential"}}, True),
            ({"type": "way", "tags": {"highway": "bus_stop"}}, False),  # Excluded value
            ({"type": "node", "tags": {"highway": "motorway"}}, False),  # Excluded geometry
        ]
        for element, expected in test_cases:
            result = should_include_element_in_results(element, "highway", "*")
            assert (
                result == expected
            ), f"Failed for element {element}: expected {expected}, got {result}"

    def test_unconfigured_key_includes_all(self):
        """Test that unconfigured keys include all elements."""
        element = {"type": "node", "tags": {"amenity": "restaurant"}}
        assert should_include_element_in_results(element, "amenity", "*") is True

    def test_railway_excludes_stations(self):
        """Test that railway stations (nodes) are excluded."""
        element = {"type": "node", "tags": {"railway": "station"}}
        assert should_include_element_in_results(element, "railway", "*") is False

    def test_railway_includes_tracks(self):
        """Test that railway tracks (ways) are included."""
        element = {"type": "way", "tags": {"railway": "rail"}}
        assert should_include_element_in_results(element, "railway", "*") is True

    def test_waterway_excludes_weirs(self):
        """Test that waterway weirs (nodes) are excluded."""
        element = {"type": "node", "tags": {"waterway": "weir"}}
        assert should_include_element_in_results(element, "waterway", "*") is False

    def test_waterway_includes_rivers(self):
        """Test that waterway rivers (ways) are included."""
        element = {"type": "way", "tags": {"waterway": "river"}}
        assert should_include_element_in_results(element, "waterway", "*") is True

    def test_element_without_tags(self):
        """Test that elements without tags are handled."""
        element = {"type": "way"}
        # Should not crash, but may return True or False depending on implementation
        result = should_include_element_in_results(element, "highway", "*")
        assert isinstance(result, bool)

    def test_element_without_matching_key(self):
        """Test that elements without matching key are handled."""
        element = {"type": "way", "tags": {"other_key": "value"}}
        result = should_include_element_in_results(element, "highway", "*")
        # Should check geometry type exclusion
        assert isinstance(result, bool)


@pytest.mark.integration
class TestQueryConstructionIntegration:
    """Integration tests for query construction with geometry filtering."""

    def test_highway_wildcard_query_structure(self):
        """Test that highway=* query excludes nodes."""
        # This tests the logic, not actual query execution
        assert should_include_element_in_query("highway", "*", "node") is False
        assert should_include_element_in_query("highway", "*", "way") is True
        assert should_include_element_in_query("highway", "*", "relation") is True

    def test_railway_wildcard_query_structure(self):
        """Test that railway=* query excludes nodes."""
        assert should_include_element_in_query("railway", "*", "node") is False
        assert should_include_element_in_query("railway", "*", "way") is True
        assert should_include_element_in_query("railway", "*", "relation") is True

    def test_amenity_wildcard_query_structure(self):
        """Test that amenity=* query includes all types."""
        assert should_include_element_in_query("amenity", "*", "node") is True
        assert should_include_element_in_query("amenity", "*", "way") is True
        assert should_include_element_in_query("amenity", "*", "relation") is True


@pytest.mark.unit
class TestShouldIncludeGeoJSONGeometry:
    """Test should_include_geojson_geometry helper function."""

    def test_highway_excludes_polygons(self):
        """Test that highway queries exclude Polygon geometries."""
        assert should_include_geojson_geometry("Polygon", "highway") is False
        assert should_include_geojson_geometry("LineString", "highway") is True
        assert should_include_geojson_geometry("Point", "highway") is True

    def test_railway_excludes_polygons(self):
        """Test that railway queries exclude Polygon geometries."""
        assert should_include_geojson_geometry("Polygon", "railway") is False
        assert should_include_geojson_geometry("LineString", "railway") is True
        assert should_include_geojson_geometry("Point", "railway") is True

    def test_waterway_excludes_polygons(self):
        """Test that waterway queries exclude Polygon geometries."""
        assert should_include_geojson_geometry("Polygon", "waterway") is False
        assert should_include_geojson_geometry("LineString", "waterway") is True
        assert should_include_geojson_geometry("Point", "waterway") is True

    def test_aeroway_excludes_polygons(self):
        """Test that aeroway queries exclude Polygon geometries."""
        assert should_include_geojson_geometry("Polygon", "aeroway") is False
        assert should_include_geojson_geometry("LineString", "aeroway") is True
        assert should_include_geojson_geometry("Point", "aeroway") is True

    def test_power_excludes_polygons(self):
        """Test that power queries exclude Polygon geometries."""
        assert should_include_geojson_geometry("Polygon", "power") is False
        assert should_include_geojson_geometry("LineString", "power") is True
        assert should_include_geojson_geometry("Point", "power") is True

    def test_unconfigured_key_includes_all_geometries(self):
        """Test that unconfigured keys include all geometry types."""
        assert should_include_geojson_geometry("Polygon", "amenity") is True
        assert should_include_geojson_geometry("LineString", "amenity") is True
        assert should_include_geojson_geometry("Point", "amenity") is True

    def test_building_includes_polygons(self):
        """Test that building queries include Polygon geometries."""
        assert should_include_geojson_geometry("Polygon", "building") is True
        assert should_include_geojson_geometry("LineString", "building") is True
        assert should_include_geojson_geometry("Point", "building") is True


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_exclude_lists(self):
        """Test that empty exclude lists work correctly."""
        # Unconfigured keys have empty exclude lists
        prefs = get_geometry_preferences("amenity")
        assert prefs["exclude_geometries"] == []
        assert prefs["exclude_values"] == set()

    def test_specific_value_not_wildcard(self):
        """Test that specific values (not wildcard) work correctly."""
        # Specific values should check exclude_values
        assert should_include_element_in_query("highway", "bus_stop", "way") is False
        assert should_include_element_in_query("highway", "motorway", "way") is True

    def test_missing_geometry_type(self):
        """Test handling of missing geometry type in element."""
        element = {"tags": {"highway": "motorway"}}
        # Should handle gracefully
        result = should_include_element_in_results(element, "highway", "*")
        assert isinstance(result, bool)

    def test_missing_tags(self):
        """Test handling of missing tags in element."""
        element = {"type": "way"}
        result = should_include_element_in_results(element, "highway", "*")
        assert isinstance(result, bool)
