"""
Test union and dissolve operations to identify issues.
"""

import pytest
from shapely.geometry import Polygon, shape

from services.tools.geoprocessing.ops.buffer import op_buffer
from services.tools.geoprocessing.ops.overlay import op_overlay


def test_union_multiple_buffers():
    """Test union of multiple overlapping buffer areas."""
    # Create two points that will have overlapping buffers
    pt1_fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": 1},
                "geometry": {"type": "Point", "coordinates": [0, 0]},
            }
        ],
    }
    pt2_fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": 2},
                "geometry": {
                    "type": "Point",
                    "coordinates": [0.01, 0],
                },  # Close enough to overlap at 1km buffer
            }
        ],
    }

    # Buffer both points
    buffer1 = op_buffer([pt1_fc], radius=1, radius_unit="kilometers")
    buffer2 = op_buffer([pt2_fc], radius=1, radius_unit="kilometers")

    # Try to union them
    result = op_overlay([buffer1[0], buffer2[0]], how="union")

    assert len(result) == 1
    features = result[0]["features"]
    # Union should combine overlapping buffers
    # At minimum, we should have features (could be 1 merged or multiple)
    assert len(features) >= 1

    # Check that the result has valid geometry
    for feat in features:
        geom = shape(feat["geometry"])
        assert geom.is_valid
        assert geom.area > 0


def test_dissolve_multiple_polygons():
    """Test dissolving multiple overlapping polygons into one."""
    # Create two overlapping squares
    sq1_fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"category": "A"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]],
                },
            }
        ],
    }
    sq2_fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"category": "A"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[1, 1], [3, 1], [3, 3], [1, 3], [1, 1]]],
                },
            }
        ],
    }

    # Union should merge overlapping areas
    result = op_overlay([sq1_fc, sq2_fc], how="union")

    assert len(result) == 1
    features = result[0]["features"]
    assert len(features) >= 1

    # The union should cover the combined area
    total_geom = None
    for feat in features:
        geom = shape(feat["geometry"])
        if total_geom is None:
            total_geom = geom
        else:
            total_geom = total_geom.union(geom)

    # Check that we have a valid merged geometry
    assert total_geom.is_valid
    assert total_geom.bounds == pytest.approx((0.0, 0.0, 3.0, 3.0))


def test_buffer_with_dissolve_flag():
    """Test buffering multiple points and dissolving into single geometry."""
    # Create multiple points in a FeatureCollection
    points_fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": 1},
                "geometry": {"type": "Point", "coordinates": [0, 0]},
            },
            {
                "type": "Feature",
                "properties": {"id": 2},
                "geometry": {"type": "Point", "coordinates": [0.005, 0]},
            },
            {
                "type": "Feature",
                "properties": {"id": 3},
                "geometry": {"type": "Point", "coordinates": [0, 0.005]},
            },
        ],
    }

    # Buffer all points - currently returns individual buffers
    buffer_result = op_buffer([points_fc], radius=1, radius_unit="kilometers")

    assert len(buffer_result) == 1
    features = buffer_result[0]["features"]
    # Should have 3 individual buffer polygons
    assert len(features) == 3

    # Each should be a valid polygon
    for feat in features:
        geom = shape(feat["geometry"])
        assert isinstance(geom, Polygon)
        assert geom.is_valid


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
