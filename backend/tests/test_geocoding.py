import json
import os
import sys
from unittest.mock import Mock, patch

import pytest
import requests

# Add the backend directory to the path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.tools.geocoding import (  # noqa: E402
    create_geodata_object_from_geojson,
    geocode_using_geonames,
    geocode_using_nominatim,
)


@pytest.fixture
def mock_geonames_response():
    """Mock response for GeoNames API"""
    return {
        "geonames": [
            {
                "adminCode1": "07",
                "lng": "2.3488",
                "geonameId": 2988507,
                "toponymName": "Paris",
                "countryId": "3017382",
                "fcl": "P",
                "population": 2161000,
                "countryCode": "FR",
                "name": "Paris",
                "fclName": "city, village,...",
                "adminCodes1": {"ISO3166_2": "IDF"},
                "countryName": "France",
                "fcodeName": "capital of a political entity",
                "adminName1": "Île-de-France",
                "lat": "48.85341",
                "fcode": "PPLC",
            }
        ]
    }


@pytest.fixture
def mock_nominatim_response():
    """Mock response for Nominatim API"""
    return [
        {
            "place_id": 240109189,
            "licence": "Data © OpenStreetMap contributors, ODbL 1.0",
            "osm_type": "relation",
            "osm_id": 71525,
            "lat": "48.8566969",
            "lon": "2.3514616",
            "display_name": "Paris, France",
            "address": {
                "city": "Paris",
                "state": "Île-de-France",
                "country": "France",
                "country_code": "fr",
            },
            "boundingbox": ["48.815", "48.902", "2.224", "2.469"],
            "class": "place",
            "type": "city",
            "importance": 0.96893,
            "name": "Paris",
        }
    ]


@pytest.fixture
def mock_nominatim_geojson_response():
    """Mock response for Nominatim API with GeoJSON"""
    return [
        {
            "place_id": 240109189,
            "licence": "Data © OpenStreetMap contributors, ODbL 1.0",
            "osm_type": "relation",
            "osm_id": 71525,
            "lat": "48.8566969",
            "lon": "2.3514616",
            "display_name": "Paris, France",
            "boundingbox": ["48.815", "48.902", "2.224", "2.469"],
            "class": "place",
            "type": "city",
            "importance": 0.96893,
            "name": "Paris",
            "geojson": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [2.224, 48.815],
                        [2.469, 48.815],
                        [2.469, 48.902],
                        [2.224, 48.902],
                        [2.224, 48.815],
                    ]
                ],
            },
        }
    ]


class TestGeocodingBasicFunctions:
    """Test basic geocoding functions without state injection"""

    def test_geocode_using_geonames_success(self, mock_geonames_response):
        """Test successful GeoNames geocoding"""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_geonames_response
            mock_get.return_value = mock_response

            result = geocode_using_geonames.func("Paris")

            # Verify API call was made correctly
            expected_base = "http://api.geonames.org/searchJSON"
            mock_get.assert_called_once()
            call_args = mock_get.call_args[0]
            assert expected_base in call_args[0]
            assert "q=Paris" in call_args[0]
            assert "maxRows=3" in call_args[0]
            assert "username=nalamap" in call_args[0]

            # Verify result is valid JSON
            parsed_result = json.loads(result)
            assert len(parsed_result) == 1
            assert parsed_result[0]["name"] == "Paris"
            assert parsed_result[0]["countryCode"] == "FR"

    def test_geocode_using_geonames_no_results(self):
        """Test GeoNames with no results"""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"geonames": []}
            mock_get.return_value = mock_response

            result = geocode_using_geonames.func("NonexistentPlace")
            assert result == "[]"

    def test_geocode_using_geonames_api_error(self):
        """Test GeoNames API error handling"""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_get.return_value = mock_response

            result = geocode_using_geonames.func("Paris")
            assert result == "Error calling the GeoNames API."

    def test_geocode_using_geonames_custom_params(self, mock_geonames_response):
        """Test GeoNames with custom parameters"""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_geonames_response
            mock_get.return_value = mock_response

            geocode_using_geonames.func("Berlin", maxRows=5)

            # Verify maxRows parameter is correctly passed
            call_args = mock_get.call_args[0]
            assert "maxRows=5" in call_args[0]

    def test_geocode_using_nominatim_success(self, mock_nominatim_response):
        """Test successful Nominatim geocoding"""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_nominatim_response
            mock_get.return_value = mock_response

            result = geocode_using_nominatim.func("Paris, France")

            # Verify API call was made correctly
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            nominatim_base = "https://nominatim.openstreetmap.org/search"
            assert nominatim_base in call_args[0][0]
            assert "q=Paris, France" in call_args[0][0]
            # geojson=False by default
            assert "polygon_kml=0" in call_args[0][0]

            # Verify headers are set
            headers = call_args[1]["headers"]
            assert headers["User-Agent"].startswith("NaLaMap")

            # Verify result is valid JSON
            parsed_result = json.loads(result)
            assert len(parsed_result) == 1
            assert parsed_result[0]["display_name"] == "Paris, France"

    def test_geocode_using_nominatim_with_geojson(self, mock_nominatim_response):
        """Test Nominatim with GeoJSON enabled"""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_nominatim_response
            mock_get.return_value = mock_response

            geocode_using_nominatim.func("Paris", geojson=True, maxRows=1)

            call_args = mock_get.call_args[0]
            assert "polygon_kml=1" in call_args[0]
            assert "limit=1" in call_args[0]

    def test_geocode_using_nominatim_no_results(self):
        """Test Nominatim with no results"""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = []
            mock_get.return_value = mock_response

            result = geocode_using_nominatim.func("NonexistentPlace")
            assert result == "No results found."

    def test_geocode_using_nominatim_api_error(self):
        """Test Nominatim API error handling"""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.json.return_value = {"error": "Not found"}
            mock_get.return_value = mock_response

            # Mock print to avoid output during tests
            with patch("builtins.print"):
                result = geocode_using_nominatim.func("Paris")
                assert result == "Error querying the Nominatim API."


class TestGeodataObjectCreation:
    """Test GeoDataObject creation from geocoding responses"""

    def test_create_geodata_object_from_geojson_success(self, mock_nominatim_geojson_response):
        """Test successful GeoDataObject creation"""
        nominatim_data = mock_nominatim_geojson_response[0]

        with patch("services.tools.geocoding.store_file") as mock_store:
            test_url = "http://test.com/file.json"
            test_uuid = "test-uuid-123"
            mock_store.return_value = (test_url, test_uuid)

            geo_object = create_geodata_object_from_geojson(nominatim_data)

            assert geo_object is not None
            assert geo_object.name == "Paris"
            assert geo_object.title == "Paris"
            assert geo_object.description == "Paris, France"
            assert geo_object.data_source_id == "geocodeNominatim"
            assert geo_object.data_type == "GeoJson"
            assert geo_object.data_origin == "tool"
            assert geo_object.id == test_uuid
            assert geo_object.data_link == test_url

            # Verify bounding box is correctly formatted
            assert geo_object.bounding_box is not None
            assert "POLYGON" in geo_object.bounding_box

            # Verify properties are copied
            assert "place_id" in geo_object.properties
            assert geo_object.properties["place_id"] == 240109189

    def test_create_geodata_object_no_geojson(self):
        """Test GeoDataObject creation fails without geojson"""
        nominatim_data = {
            "name": "Paris",
            "lat": "48.8566969",
            "lon": "2.3514616",
        }

        geo_object = create_geodata_object_from_geojson(nominatim_data)
        assert geo_object is None

    def test_create_geodata_object_no_bounding_box(self, mock_nominatim_geojson_response):
        """Test GeoDataObject creation without bounding box"""
        nominatim_data = mock_nominatim_geojson_response[0].copy()
        del nominatim_data["boundingbox"]

        # We need to patch the geocoding function to handle missing boundingbox
        with patch("services.tools.geocoding.store_file") as mock_store:
            test_url = "http://test.com/file.json"
            test_uuid = "test-uuid-123"
            mock_store.return_value = (test_url, test_uuid)

            # Current implementation doesn't handle gracefully
            try:
                create_geodata_object_from_geojson(nominatim_data)  # noqa
                assert False, "Should have raised KeyError"
            except KeyError:
                # This is expected with current implementation
                pass


class TestGeocodingErrorHandling:
    """Test error handling and edge cases"""

    def test_malformed_api_response(self):
        """Test handling of malformed API responses"""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
            mock_get.return_value = mock_response

            # Current implementation doesn't handle gracefully
            try:
                geocode_using_geonames.func("Paris")
                assert False, "Should have raised JSONDecodeError"
            except json.JSONDecodeError:
                # This is expected with current implementation
                pass

    def test_network_timeout(self):
        """Test network timeout handling"""
        with patch("requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout()

            # Current implementation doesn't handle gracefully
            try:
                geocode_using_geonames.func("Paris")
                assert False, "Should have raised Timeout"
            except requests.exceptions.Timeout:
                # This is expected with current implementation
                pass

    def test_empty_query_handling(self):
        """Test handling of empty queries"""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"geonames": []}
            mock_get.return_value = mock_response

            result = geocode_using_geonames.func("")
            # Should handle empty query without crashing
            assert isinstance(result, str)

    def test_special_characters_in_query(self):
        """Test handling of special characters in queries"""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"geonames": []}
            mock_get.return_value = mock_response

            # Test with special characters that might break URL encoding
            geocode_using_geonames.func("Paris & London, café #1")

            # Verify the URL was properly constructed
            call_args = mock_get.call_args[0]
            url = call_args[0]
            # URL should contain the query, properly encoded
            assert "Paris" in url


class TestUrlConstruction:
    """Test URL construction and f-string formatting"""

    def test_geonames_url_formatting(self):
        """Test that GeoNames URLs are properly formatted with f-strings"""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"geonames": []}
            mock_get.return_value = mock_response

            geocode_using_geonames.func("Berlin", maxRows=5)

            call_args = mock_get.call_args[0]
            url = call_args[0]

            # Verify f-string substitution worked correctly
            assert "q=Berlin" in url
            assert "maxRows=5" in url
            assert "username=nalamap" in url
            # No unformatted template strings
            assert "={" not in url
            assert "}=" not in url

    def test_nominatim_url_formatting(self):
        """Test that Nominatim URLs are properly formatted with f-strings"""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = []
            mock_get.return_value = mock_response

            geocode_using_nominatim.func("London", geojson=True, maxRows=2)

            call_args = mock_get.call_args[0]
            url = call_args[0]

            # Verify f-string substitution worked correctly
            assert "q=London" in url
            assert "polygon_kml=1" in url
            assert "limit=2" in url
            # No unformatted template strings
            assert "={" not in url
            assert "}=" not in url

    def test_error_message_formatting(self):
        """Test that error messages are properly formatted"""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.json.return_value = {"error": "Not found"}
            mock_get.return_value = mock_response

            with patch("builtins.print") as mock_print:
                result = geocode_using_nominatim.func("NonexistentPlace")

                # Verify error handling doesn't contain unformatted strings
                assert result == "Error querying the Nominatim API."
                # The print call should have properly formatted content
                if mock_print.called:
                    printed_args = str(mock_print.call_args)
                    assert "={" not in printed_args
                    assert "}=" not in printed_args


class TestGeocodingIntegration:
    """Integration tests that verify the main issue was fixed"""

    def test_f_string_formatting_was_fixed(self):
        """
        Test that verifies the specific f-string issue was resolved.
        This test ensures URLs are properly formatted and don't contain
        unformatted template literals like 'url={location_name}'.
        """
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"geonames": []}
            mock_get.return_value = mock_response

            # This would have failed before the fix due to f-string issues
            geocode_using_geonames.func("test location")

            # Verify the URL was constructed properly
            call_args = mock_get.call_args[0]
            url = call_args[0]

            # These assertions would fail if f-strings weren't working
            assert "q=test location" in url or "q=test%20location" in url
            assert "maxRows=3" in url
            assert "username=nalamap" in url

            # Most importantly, verify no unformatted template strings
            assert "{location_name}" not in url
            assert "{maxRows}" not in url
            assert "url={" not in url

    def test_nominatim_f_string_formatting_was_fixed(self):
        """Test Nominatim f-string formatting fix"""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = []
            mock_get.return_value = mock_response

            # This would have failed before the fix
            geocode_using_nominatim.func("test query", geojson=True)

            call_args = mock_get.call_args[0]
            url = call_args[0]

            # Verify proper f-string substitution
            assert "q=test query" in url or "q=test%20query" in url
            assert "polygon_kml=1" in url

            # Verify no unformatted template strings
            assert "{query}" not in url
            assert "{geojson}" not in url
            assert "url={" not in url


class TestGeodataObjectGeoJSONStructure:
    """Test that GeoJSON created by geocoding is valid for geopandas"""

    def test_geojson_has_properties_field(self, mock_nominatim_geojson_response):
        """Test that created GeoJSON includes required 'properties' field"""
        nominatim_data = mock_nominatim_geojson_response[0]

        with patch("services.tools.geocoding.store_file") as mock_store:
            test_url = "http://test.com/file.json"
            test_uuid = "test-uuid-123"
            mock_store.return_value = (test_url, test_uuid)

            # Create the GeoDataObject
            geo_object = create_geodata_object_from_geojson(nominatim_data)
            assert geo_object is not None

            # Retrieve the stored GeoJSON
            call_args = mock_store.call_args
            stored_content = call_args[0][1]  # Second argument is the content bytes
            stored_geojson = json.loads(stored_content.decode("utf-8"))

            # Verify GeoJSON structure
            assert stored_geojson["type"] == "Feature"
            assert "geometry" in stored_geojson
            assert "properties" in stored_geojson, "GeoJSON Feature must have 'properties' field"

            # Verify properties are not empty
            assert isinstance(stored_geojson["properties"], dict)
            assert len(stored_geojson["properties"]) > 0

            # Verify key properties are included
            assert "place_id" in stored_geojson["properties"]
            assert "name" in stored_geojson["properties"]
            assert stored_geojson["properties"]["name"] == "Paris"

    def test_geojson_compatible_with_geopandas(self, mock_nominatim_geojson_response):
        """Test that created GeoJSON can be loaded by geopandas without errors"""
        try:
            import geopandas as gpd
        except ImportError:
            pytest.skip("geopandas not installed")

        nominatim_data = mock_nominatim_geojson_response[0]

        with patch("services.tools.geocoding.store_file") as mock_store:
            test_url = "http://test.com/file.json"
            test_uuid = "test-uuid-123"
            mock_store.return_value = (test_url, test_uuid)

            # Create the GeoDataObject
            geo_object = create_geodata_object_from_geojson(nominatim_data)
            assert geo_object is not None

            # Retrieve the stored GeoJSON
            call_args = mock_store.call_args
            stored_content = call_args[0][1]
            stored_geojson = json.loads(stored_content.decode("utf-8"))

            # This should not raise a KeyError for 'properties'
            gdf = gpd.GeoDataFrame.from_features([stored_geojson])
            assert len(gdf) == 1
            assert not gdf.empty
