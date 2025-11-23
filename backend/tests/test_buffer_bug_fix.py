"""
Test cases to reproduce and verify buffer operation bugs.

These tests specifically target the bugs found in buffer.py:
1. Missing f-string prefix on line 68 (multiple layers error message)
2. Missing f-string prefix on line 93-94 (empty layer warning)
"""

import pytest
from services.tools.geoprocessing.ops.buffer import op_buffer


class TestBufferErrorHandling:
    """Test buffer operation error handling and edge cases."""

    def test_buffer_multiple_layers_error_message(self):
        """Test buffer raises ValueError with error when multiple layers provided."""
        # Create two simple GeoJSON features
        layer1 = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {"name": "Test Layer 1"},
                }
            ],
        }

        layer2 = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [1, 1]},
                    "properties": {"name": "Test Layer 2"},
                }
            ],
        }

        # Should raise ValueError with proper error message
        with pytest.raises(ValueError) as exc_info:
            op_buffer([layer1, layer2], radius=100, radius_unit="meters")

        error_message = str(exc_info.value)

        # Verify error message is properly formatted (not showing literal {i+1} or {name})
        assert "Buffer operation error" in error_message
        assert "Only one layer can be buffered at a time" in error_message
        assert "Received 2 layers" in error_message

        # The error message should NOT contain unformatted template strings
        assert "{i+1}" not in error_message, "Error message contains unformatted {i+1}"
        assert "{name}" not in error_message, "Error message contains unformatted {name}"

        # Should contain formatted layer info
        assert "Layer" in error_message
        print(f"✓ Error message properly formatted: {error_message}")

    def test_buffer_empty_layer_warning(self, capsys):
        """Test that buffer handles empty layers with proper warning message."""
        # Create an empty FeatureCollection
        empty_layer = {"type": "FeatureCollection", "features": []}

        # Should return empty list and print warning
        result = op_buffer([empty_layer], radius=100, radius_unit="meters")

        # Verify result is empty
        assert result == [], "Empty layer should return empty result"

        # Capture print output
        captured = capsys.readouterr()

        # Verify warning message is properly formatted (not showing literal {type(layer_item)})
        if captured.out:
            assert (
                "{type(layer_item)}" not in captured.out
            ), "Warning message contains unformatted {type(layer_item)}"
            print(f"✓ Warning message properly formatted: {captured.out}")

    def test_buffer_single_valid_layer_success(self):
        """Test that buffer works correctly with a single valid layer."""
        # Create a valid GeoJSON point
        layer = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {"name": "Test Point"},
                }
            ],
        }

        # Should succeed and return buffered result
        result = op_buffer([layer], radius=1000, radius_unit="meters")

        assert len(result) == 1, "Should return one result"
        assert result[0]["type"] == "FeatureCollection"
        assert len(result[0]["features"]) > 0, "Should have features"

        # Verify the geometry was buffered (should be Polygon now)
        assert result[0]["features"][0]["geometry"]["type"] == "Polygon"
        print("✓ Single layer buffer operation succeeded")

    def test_buffer_with_dissolve(self):
        """Test buffer operation with dissolve option."""
        # Create multiple points
        layer = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {"name": "Point 1"},
                },
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0.001, 0.001]},
                    "properties": {"name": "Point 2"},
                },
            ],
        }

        # Buffer with dissolve
        result = op_buffer([layer], radius=1000, radius_unit="meters", dissolve=True)

        assert len(result) == 1, "Should return one result"
        assert result[0]["type"] == "FeatureCollection"
        # When dissolved, should have only one feature
        assert len(result[0]["features"]) == 1, "Dissolved result should have one feature"
        print("✓ Buffer with dissolve succeeded")

    def test_buffer_different_units(self):
        """Test buffer operation with different radius units."""
        layer = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {"name": "Test Point"},
                }
            ],
        }

        # Test with meters
        result_meters = op_buffer([layer], radius=1000, radius_unit="meters")
        assert len(result_meters) == 1
        print("✓ Buffer with meters succeeded")

        # Test with kilometers
        result_km = op_buffer([layer], radius=1, radius_unit="kilometers")
        assert len(result_km) == 1
        print("✓ Buffer with kilometers succeeded")

        # Test with miles
        result_miles = op_buffer([layer], radius=0.621371, radius_unit="miles")
        assert len(result_miles) == 1
        print("✓ Buffer with miles succeeded")

    def test_buffer_no_layers(self):
        """Test buffer operation with no layers."""
        result = op_buffer([], radius=100, radius_unit="meters")
        assert result == [], "No layers should return empty result"
        print("✓ Buffer with no layers handled correctly")

    def test_buffer_auto_optimize_crs(self):
        """Test buffer operation with auto CRS optimization."""
        layer = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [10.0, 53.5]},  # Hamburg
                    "properties": {"name": "Hamburg Point"},
                }
            ],
        }

        # Test with auto CRS optimization
        result = op_buffer(
            [layer],
            radius=1000,
            radius_unit="meters",
            auto_optimize_crs=True,
            projection_metadata=True,
        )

        assert len(result) == 1
        assert result[0]["type"] == "FeatureCollection"

        # Check if CRS metadata was added
        if "properties" in result[0] and "_crs_metadata" in result[0]["properties"]:
            print(f"✓ CRS metadata included: {result[0]['properties']['_crs_metadata']}")
        print("✓ Buffer with auto CRS optimization succeeded")


if __name__ == "__main__":
    # Run tests manually for quick verification
    print("Running buffer bug fix tests...\n")

    test_suite = TestBufferErrorHandling()

    # Test 1: Multiple layers error
    print("Test 1: Multiple layers error message")
    try:
        test_suite.test_buffer_multiple_layers_error_message()
        print("PASSED\n")
    except AssertionError as e:
        print(f"FAILED: {e}\n")

    # Test 2: Empty layer warning (requires capsys, skip in manual mode)
    print("Test 2: Empty layer warning (requires pytest capsys, run with pytest)\n")

    # Test 3: Single valid layer
    print("Test 3: Single valid layer")
    try:
        test_suite.test_buffer_single_valid_layer_success()
        print("PASSED\n")
    except Exception as e:
        print(f"FAILED: {e}\n")

    # Test 4: Dissolve option
    print("Test 4: Buffer with dissolve")
    try:
        test_suite.test_buffer_with_dissolve()
        print("PASSED\n")
    except Exception as e:
        print(f"FAILED: {e}\n")

    # Test 5: Different units
    print("Test 5: Different radius units")
    try:
        test_suite.test_buffer_different_units()
        print("PASSED\n")
    except Exception as e:
        print(f"FAILED: {e}\n")

    # Test 6: No layers
    print("Test 6: No layers")
    try:
        test_suite.test_buffer_no_layers()
        print("PASSED\n")
    except Exception as e:
        print(f"FAILED: {e}\n")

    # Test 7: Auto optimize CRS
    print("Test 7: Auto optimize CRS")
    try:
        test_suite.test_buffer_auto_optimize_crs()
        print("PASSED\n")
    except Exception as e:
        print(f"FAILED: {e}\n")

    print("Test suite complete!")
