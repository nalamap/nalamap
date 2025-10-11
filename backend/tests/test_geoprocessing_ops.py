import math
import os
import sys

import pytest
from shapely.geometry import Point, Polygon, shape

from services.tools.geoprocessing.ops.area import op_area
from services.tools.geoprocessing.ops.buffer import op_buffer
from services.tools.geoprocessing.ops.centroid import op_centroid
from services.tools.geoprocessing.ops.clip import op_clip
from services.tools.geoprocessing.ops.dissolve import op_dissolve
from services.tools.geoprocessing.ops.merge import op_merge
from services.tools.geoprocessing.ops.overlay import op_overlay
from services.tools.geoprocessing.ops.simplify import op_simplify
from services.tools.geoprocessing.ops.sjoin import op_sjoin
from services.tools.geoprocessing.ops.sjoin_nearest import op_sjoin_nearest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_op_buffer_basic_and_error_cases():
    # Empty input returns empty list
    assert op_buffer([]) == []
    # More than one layer raises ValueError
    with pytest.raises(ValueError):
        op_buffer([{"type": "FeatureCollection"}, {"type": "FeatureCollection"}])
    # Buffer a single point and verify polygon output
    pt_fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {"type": "Point", "coordinates": [0, 0]},
            }
        ],
    }
    result = op_buffer([pt_fc], radius=1, radius_unit="meters")
    assert isinstance(result, list) and len(result) == 1
    fc = result[0]
    assert fc["type"] == "FeatureCollection"
    geom = shape(fc["features"][0]["geometry"])
    assert isinstance(geom, Polygon)


def test_op_centroid_empty_and_centroid_point():
    assert op_centroid([]) == []
    line_fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[0, 0], [2, 0]],
                },
            }
        ],
    }
    result = op_centroid([line_fc])
    assert len(result) == 1
    fc = result[0]
    pt = shape(fc["features"][0]["geometry"])
    assert isinstance(pt, Point)
    assert pt.x == pytest.approx(1.0)
    assert pt.y == pytest.approx(0.0)


def test_op_merge_insufficient_and_inner_join():
    fc1 = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": 1},
                "geometry": {"type": "Point", "coordinates": [0, 0]},
            }
        ],
    }
    # fewer than two returns original
    assert op_merge([fc1]) == [fc1]
    fc2 = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": 1, "val": "A"},
                "geometry": {"type": "Point", "coordinates": [1, 1]},
            }
        ],
    }
    merged = op_merge([fc1, fc2], on=["id"], how="inner")
    assert len(merged) == 1
    features = merged[0]["features"]
    assert len(features) == 1
    props = features[0]["properties"]
    assert props["id"] == 1
    assert props.get("val") == "A"
    # geometry from first layer retained
    geom = shape(features[0]["geometry"])
    assert isinstance(geom, Point)
    assert geom.x == pytest.approx(0.0)
    assert geom.y == pytest.approx(0.0)


def test_op_overlay_insufficient_and_intersection():
    # fewer than two returns original
    fc = {"type": "FeatureCollection", "features": []}
    assert op_overlay([fc], how="intersection", crs="EPSG:4326") == [fc]
    # overlapping rectangles
    rect1 = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]],
                },
            }
        ],
    }
    rect2 = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[1, 1], [3, 1], [3, 3], [1, 3], [1, 1]]],
                },
            }
        ],
    }
    result = op_overlay([rect1, rect2], how="intersection", crs="EPSG:4326")
    assert len(result) == 1
    features = result[0]["features"]
    assert len(features) == 1
    poly = shape(features[0]["geometry"])
    assert isinstance(poly, Polygon)
    # intersection should be a unit square from (1,1) to (2,2)
    assert poly.bounds == pytest.approx((1.0, 1.0, 2.0, 2.0))


def test_op_simplify_empty_and_tolerance_zero():
    assert op_simplify([]) == []
    poly = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [0, 1], [1, 0], [0, 0]]],
                },
            }
        ],
    }
    result = op_simplify([poly], tolerance=0.0, preserve_topology=True)
    assert len(result) == 1
    geom = shape(result[0]["features"][0]["geometry"])
    assert isinstance(geom, Polygon)
    # with zero tolerance, geometry unchanged
    assert geom.equals(Polygon(poly["features"][0]["geometry"]["coordinates"][0]))


def test_op_sjoin_insufficient_and_intersects_join():
    # fewer than two returns original
    fc = {"type": "FeatureCollection", "features": []}
    assert op_sjoin([fc], how="inner", predicate="intersects") == [fc]
    # point within square
    pt_fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": 1},
                "geometry": {"type": "Point", "coordinates": [0.5, 0.5]},
            }
        ],
    }
    sq_fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "sq"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                },
            }
        ],
    }
    result = op_sjoin([pt_fc, sq_fc], how="inner", predicate="intersects")
    assert len(result) == 1
    features = result[0]["features"]
    assert len(features) == 1
    pt = shape(features[0]["geometry"])
    assert isinstance(pt, Point)
    # geometry from left preserved
    assert pt.x == pytest.approx(0.5)
    assert pt.y == pytest.approx(0.5)


def test_op_sjoin_nearest_insufficient_and_distance_column():
    # fewer than two returns original
    fc = {"type": "FeatureCollection", "features": []}
    assert op_sjoin_nearest([fc], how="inner", max_distance=None, distance_col="dist") == [fc]
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
                "geometry": {"type": "Point", "coordinates": [1, 1]},
            }
        ],
    }
    result = op_sjoin_nearest([pt1_fc, pt2_fc], how="inner", max_distance=None, distance_col="dist")
    assert len(result) == 1
    features = result[0]["features"]
    assert len(features) == 1
    props = features[0]["properties"]
    # distance column present and approximately sqrt(2)
    assert "dist" in props
    assert props["dist"] == pytest.approx(math.hypot(1.0, 1.0))
    # geometry from left preserved
    pt = shape(features[0]["geometry"])
    assert isinstance(pt, Point)
    assert pt.x == pytest.approx(0.0)
    assert pt.y == pytest.approx(0.0)


# ========== Tests for new operations ==========


def test_op_dissolve_basic():
    """Test dissolve operation merges geometries."""
    # Create two adjacent squares
    sq1_fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": 1},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                },
            }
        ],
    }
    sq2_fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": 2},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[1, 0], [2, 0], [2, 1], [1, 1], [1, 0]]],
                },
            }
        ],
    }

    # Dissolve into single geometry
    result = op_dissolve([sq1_fc, sq2_fc])
    assert len(result) == 1
    features = result[0]["features"]
    # Should have one merged feature
    assert len(features) == 1
    geom = shape(features[0]["geometry"])
    assert geom.is_valid
    # Combined area should be 2 square units
    assert geom.area == pytest.approx(2.0, abs=0.01)


def test_op_dissolve_by_attribute():
    """Test dissolve grouped by attribute."""
    # Create features with categories
    features_fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"category": "A"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                },
            },
            {
                "type": "Feature",
                "properties": {"category": "A"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[1, 0], [2, 0], [2, 1], [1, 1], [1, 0]]],
                },
            },
            {
                "type": "Feature",
                "properties": {"category": "B"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 1], [1, 1], [1, 2], [0, 2], [0, 1]]],
                },
            },
        ],
    }

    # Dissolve by category
    result = op_dissolve([features_fc], by="category")
    assert len(result) == 1
    features = result[0]["features"]
    # Should have two features (one for each category)
    assert len(features) == 2


def test_op_buffer_with_dissolve():
    """Test buffer operation with dissolve flag."""
    # Create two close points
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
        ],
    }

    # Buffer without dissolve - should get 2 polygons
    result_no_dissolve = op_buffer([points_fc], radius=1, radius_unit="kilometers", dissolve=False)
    assert len(result_no_dissolve) == 1
    assert len(result_no_dissolve[0]["features"]) == 2

    # Buffer with dissolve - should get 1 merged polygon
    result_dissolve = op_buffer([points_fc], radius=1, radius_unit="kilometers", dissolve=True)
    assert len(result_dissolve) == 1
    assert len(result_dissolve[0]["features"]) == 1
    geom = shape(result_dissolve[0]["features"][0]["geometry"])
    assert isinstance(geom, Polygon)
    assert geom.is_valid


def test_op_area_calculation():
    """Test area calculation operation."""
    # Create a 1x1 degree square (approximately)
    square_fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "test_square"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                },
            }
        ],
    }

    # Calculate area in square meters
    result = op_area([square_fc], unit="square_meters")
    assert len(result) == 1
    features = result[0]["features"]
    assert len(features) == 1
    props = features[0]["properties"]
    assert "area" in props
    # Area should be positive
    assert props["area"] > 0

    # Calculate area in square kilometers
    result_km = op_area([square_fc], unit="square_kilometers")
    features_km = result_km[0]["features"]
    props_km = features_km[0]["properties"]
    # Square kilometers should be smaller number than square meters
    assert props_km["area"] < props["area"]


def test_op_clip_basic():
    """Test clip operation."""
    # Create a large square to be clipped
    large_square = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": 1},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]]],
                },
            }
        ],
    }

    # Create a smaller square to clip by
    clip_square = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": 2},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[1, 1], [3, 1], [3, 3], [1, 3], [1, 1]]],
                },
            }
        ],
    }

    # Clip the large square by the small square
    result = op_clip([large_square, clip_square])
    assert len(result) == 1
    features = result[0]["features"]
    assert len(features) == 1

    # Result should be the intersection (2x2 square)
    geom = shape(features[0]["geometry"])
    assert geom.is_valid
    # Area should be approximately 4 (2x2 in EPSG:4326)
    assert geom.area == pytest.approx(4.0, abs=0.01)
    # Bounds should match the clip area
    assert geom.bounds == pytest.approx((1.0, 1.0, 3.0, 3.0))


def test_op_clip_multiple_features():
    """Test clipping with multiple features in target layer."""
    # Create multiple squares
    multi_squares = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": 1},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]],
                },
            },
            {
                "type": "Feature",
                "properties": {"id": 2},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[2, 2], [4, 2], [4, 4], [2, 4], [2, 2]]],
                },
            },
        ],
    }

    # Clip mask
    clip_area = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[1, 1], [3, 1], [3, 3], [1, 3], [1, 1]]],
                },
            }
        ],
    }

    # Clip
    result = op_clip([multi_squares, clip_area])
    assert len(result) == 1
    features = result[0]["features"]
    # Should have clipped parts of both squares
    assert len(features) >= 1
    for feat in features:
        geom = shape(feat["geometry"])
        assert geom.is_valid
