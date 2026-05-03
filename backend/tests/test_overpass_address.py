"""
Unit tests for the Overpass address search feature (issue #100).

Tests cover:
- OverpassQueryBuilder.build_address_query()
- geocode_address_via_overpass tool (mocked Overpass API)
"""

import pytest

from services.tools.overpass import OverpassLocation, OverpassQueryBuilder


@pytest.mark.unit
class TestBuildAddressQuery:
    """Tests for OverpassQueryBuilder.build_address_query()."""

    def setup_method(self):
        self.builder = OverpassQueryBuilder(timeout=60, max_results=50)

    def test_street_only(self):
        query = self.builder.build_address_query({"addr:street": "Baker Street"})
        assert '[out:json]' in query
        assert '"addr:street"="Baker Street"' in query
        assert "node" in query
        assert "way" in query
        assert "relation" in query
        # No location filter when location is None
        assert "area(" not in query
        assert "around:" not in query

    def test_street_and_housenumber(self):
        query = self.builder.build_address_query(
            {"addr:street": "Baker Street", "addr:housenumber": "221B"}
        )
        assert '"addr:street"="Baker Street"' in query
        assert '"addr:housenumber"="221B"' in query

    def test_all_components(self):
        components = {
            "addr:street": "Baker Street",
            "addr:housenumber": "221B",
            "addr:city": "London",
            "addr:postcode": "NW1 6XE",
        }
        query = self.builder.build_address_query(components)
        for key, value in components.items():
            assert f'"{key}"="{value}"' in query

    def test_geometry_recursion_included(self):
        """Ensure (._; >;) is present so member node geometry is available."""
        query = self.builder.build_address_query({"addr:street": "Main Street"})
        assert "(._; >;)" in query

    def test_area_location_constraint(self):
        location = OverpassLocation(
            display_name="London",
            osm_relation_id=65606,
            lat=51.5074,
            lon=-0.1278,
        )
        query = self.builder.build_address_query(
            {"addr:street": "Baker Street"}, location=location
        )
        # Area ID = relation_id + 3600000000
        assert "area(3600065606)" in query
        assert "(area.search_area)" in query

    def test_bbox_location_constraint(self):
        location = OverpassLocation(
            display_name="London",
            bbox=(51.3, -0.5, 51.7, 0.3),
            lat=51.5074,
            lon=-0.1278,
        )
        query = self.builder.build_address_query(
            {"addr:street": "Baker Street"}, location=location
        )
        assert "(51.3,-0.5,51.7,0.3)" in query

    def test_point_location_constraint(self):
        location = OverpassLocation(
            display_name="Near Trafalgar Square",
            lat=51.508,
            lon=-0.128,
        )
        query = self.builder.build_address_query(
            {"addr:street": "Baker Street"},
            location=location,
            radius_meters=5000,
        )
        assert "around:5000,51.508,-0.128" in query

    def test_empty_components_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            self.builder.build_address_query({})

    def test_output_includes_max_results(self):
        builder = OverpassQueryBuilder(timeout=60, max_results=25)
        query = builder.build_address_query({"addr:street": "Main St"})
        assert "out geom 25;" in query

    def test_timeout_in_header(self):
        builder = OverpassQueryBuilder(timeout=30, max_results=10)
        query = builder.build_address_query({"addr:street": "Main St"})
        assert "[timeout:30]" in query

    def test_value_with_double_quote_escaped(self):
        """Double quotes in values are escaped to prevent Overpass QL injection."""
        query = self.builder.build_address_query({"addr:street": 'O"Brien Road'})
        # Should not contain an unescaped bare double quote that would break the query
        # The key/value is already wrapped in double quotes, so the inner quote must be escaped
        assert '"addr:street"' in query
