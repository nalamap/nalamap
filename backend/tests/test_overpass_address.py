"""
Unit tests for the Overpass address search feature (issue #100).

Tests cover:
- OverpassQueryBuilder.build_address_query()
- geocode_address_via_overpass tool (mocked Overpass API)
"""

import pytest
from langgraph.types import Command

from models.geodata import DataType, GeoDataObject
from services.tools import geocoding as gc
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
        assert '"addr:street"="O\\"Brien Road"' in query
        assert '"addr:street"="O"Brien Road"' not in query

    def test_non_addr_key_raises(self):
        with pytest.raises(ValueError, match=r"addr:\* keys"):
            self.builder.build_address_query({"name": "Baker Street"})

    def test_invalid_addr_key_characters_raise(self):
        with pytest.raises(ValueError, match="Invalid addr key"):
            self.builder.build_address_query({"addr:street\"]": "Baker Street"})


@pytest.mark.unit
class TestGeocodeAddressViaOverpass:
    """Tests for geocode_address_via_overpass with mocked Overpass/Nominatim calls."""

    def setup_method(self):
        self.state = {"messages": [], "geodata_results": []}

    def test_filters_recursed_non_address_elements_and_sets_metadata(self, monkeypatch):
        location = OverpassLocation(
            display_name="London",
            osm_relation_id=65606,
            lat=51.5074,
            lon=-0.1278,
        )
        monkeypatch.setattr(gc, "_geocode_location_for_overpass", lambda city: (location, None))

        captured = {}

        def fake_execute_query(self, query, timeout=60):
            captured["query"] = query
            return (
                {
                    "elements": [
                        {
                            "type": "node",
                            "id": 1,
                            "lat": 51.5237,
                            "lon": -0.1585,
                            "tags": {"addr:street": "Baker Street", "addr:housenumber": "221B"},
                        },
                        {
                            "type": "node",
                            "id": 2,
                            "lat": 51.5238,
                            "lon": -0.1586,
                            "tags": {},
                        },
                        {
                            "type": "way",
                            "id": 3,
                            "tags": {},
                            "geometry": [
                                {"lat": 51.5237, "lon": -0.1585},
                                {"lat": 51.5238, "lon": -0.1585},
                            ],
                        },
                        {
                            "type": "way",
                            "id": 4,
                            "tags": {"addr:street": "Baker Street", "addr:housenumber": "221B"},
                            "geometry": [
                                {"lat": 51.5237, "lon": -0.1585},
                                {"lat": 51.5238, "lon": -0.1585},
                            ],
                        },
                    ]
                },
                None,
            )

        monkeypatch.setattr(gc.OverpassClient, "execute_query", fake_execute_query)

        captured_features = {}

        def fake_create_feature_collection_geodata(
            features,
            data_source,
            query,
            location_name,
            osm_tag_key,
            osm_tag_value,
        ):
            captured_features["features"] = features
            captured_features["query"] = query
            captured_features["location_name"] = location_name
            captured_features["osm_tag_key"] = osm_tag_key
            captured_features["osm_tag_value"] = osm_tag_value
            return GeoDataObject(
                id="addr-layer",
                data_source_id="addr-layer",
                data_type=DataType.GEOJSON,
                data_origin="tool",
                data_source="Address",
                data_link="/tmp/mock.geojson",
                name="Address results",
            )

        monkeypatch.setattr(
            gc,
            "create_feature_collection_geodata",
            fake_create_feature_collection_geodata,
        )

        result = gc.geocode_address_via_overpass.func(
            state=self.state,
            tool_call_id="tool-1",
            street="Baker Street",
            housenumber="221B",
            city="London",
        )

        assert isinstance(result, Command)
        assert '"addr:street"="Baker Street"' in captured["query"]
        assert '"addr:housenumber"="221B"' in captured["query"]
        assert "area(3600065606)" in captured["query"]

        # Only address-tagged matches should remain after filtering recursed helpers.
        assert len(captured_features["features"]) == 2

        geodata = result.update["geodata_results"][0]
        assert geodata.processing_metadata is not None
        assert geodata.processing_metadata.operation == "overpass_address_query"
        assert geodata.processing_metadata.resolution_method == "address_tags"
        assert 'addr:street=Baker Street' in geodata.processing_metadata.osm_tags_used

    def test_falls_back_to_addr_city_when_city_geocode_fails(self, monkeypatch):
        monkeypatch.setattr(
            gc,
            "_geocode_location_for_overpass",
            lambda city: (None, "Nominatim error"),
        )

        captured = {}

        def fake_execute_query(self, query, timeout=60):
            captured["query"] = query
            return ({"elements": []}, None)

        monkeypatch.setattr(gc.OverpassClient, "execute_query", fake_execute_query)

        result = gc.geocode_address_via_overpass.func(
            state=self.state,
            tool_call_id="tool-2",
            street="Main Street",
            city="Berlin",
        )

        assert isinstance(result, Command)
        assert '"addr:city"="Berlin"' in captured["query"]
        assert "No address found" in result.update["messages"][-1].content
