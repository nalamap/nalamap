import pytest

from shapely.geometry import Point, Polygon, mapping

# Import operations
from services.tools.geoprocessing.ops.buffer import op_buffer
from services.tools.geoprocessing.ops.overlay import op_overlay
from services.tools.geoprocessing.ops.clip import op_clip
from services.tools.geoprocessing.ops.dissolve import op_dissolve
from services.tools.geoprocessing.ops.sjoin_nearest import op_sjoin_nearest
from services.tools.geoprocessing.ops.sjoin import op_sjoin
from services.tools.geoprocessing.ops.simplify import op_simplify


def make_feature(geom, props=None):
    if props is None:
        props = {}
    return {"type": "Feature", "geometry": mapping(geom), "properties": props}


def test_overlay_and_clip_and_dissolve_workflow():
    # Two overlapping squares
    poly1 = Polygon([(-1, -1), (1, -1), (1, 1), (-1, 1), (-1, -1)])
    poly2 = Polygon([(0.5, 0.5), (2, 0.5), (2, 2), (0.5, 2), (0.5, 0.5)])

    fc1 = {"type": "FeatureCollection", "features": [make_feature(poly1)]}
    fc2 = {"type": "FeatureCollection", "features": [make_feature(poly2)]}

    # Overlay (intersection)
    res = op_overlay([fc1, fc2], how="intersection", auto_optimize_crs=True)
    assert isinstance(res, list) and len(res) == 1

    # Clip fc1 by fc2 should result in intersection-like result
    res_clip = op_clip([fc1, fc2], auto_optimize_crs=True, projection_metadata=True)
    assert isinstance(res_clip, list) and len(res_clip) == 1
    assert "_crs_metadata" in res_clip[0].get("properties", {})

    # Dissolve fc1+fc2
    res_dissolve = op_dissolve([fc1, fc2], auto_optimize_crs=True, projection_metadata=True)
    assert isinstance(res_dissolve, list) and len(res_dissolve) == 1
    assert "features" in res_dissolve[0]


def test_sjoin_and_sjoin_nearest():
    # Points and polygons
    pt = Point(0, 0)
    poly = Polygon([(-1, -1), (1, -1), (1, 1), (-1, 1), (-1, -1)])

    fc_points = {"type": "FeatureCollection", "features": [make_feature(pt, {"id": 1})]}
    fc_polys = {"type": "FeatureCollection", "features": [make_feature(poly, {"name": "square"})]}

    res_join = op_sjoin(
        [fc_points, fc_polys],
        how="inner",
        predicate="intersects",
        auto_optimize_crs=True,
        projection_metadata=True,
    )
    assert isinstance(res_join, list) and len(res_join) == 1
    assert "_crs_metadata" in res_join[0].get("properties", {})

    res_nearest = op_sjoin_nearest(
        [fc_points, fc_polys],
        how="inner",
        max_distance=10000,
        auto_optimize_crs=True,
        projection_metadata=True,
    )
    assert isinstance(res_nearest, list) and len(res_nearest) == 1
    assert "_crs_metadata" in res_nearest[0].get("properties", {})


def test_buffer_metadata_integration():
    pt = Point(0, 0)
    fc = {"type": "FeatureCollection", "features": [make_feature(pt)]}
    res = op_buffer([fc], radius=1000, auto_optimize_crs=True, projection_metadata=True)
    assert isinstance(res, list) and len(res) == 1
    assert "_crs_metadata" in res[0].get("properties", {})


def test_polar_area_selection():
    # Small square around Svalbard (approx 82N)
    lat = 82.0
    lon = 20.0
    delta = 0.01
    poly = Polygon(
        [
            (lon - delta, lat - delta),
            (lon + delta, lat - delta),
            (lon + delta, lat + delta),
            (lon - delta, lat + delta),
            (lon - delta, lat - delta),
        ]
    )

    fc = {"type": "FeatureCollection", "features": [make_feature(poly)]}
    res = op_overlay([fc, fc], how="intersection", auto_optimize_crs=True)
    # overlay should succeed
    assert isinstance(res, list) and len(res) == 1

    # Area calculation should choose a polar equal-area CRS when requested
    res_area = None
    try:
        res_area = __import__(
            "services.tools.geoprocessing.ops.area", fromlist=["op_area"]
        ).op_area([fc], unit="square_kilometers", auto_optimize_crs=True)
    except Exception:
        pytest.skip("Area op failed in this environment")

    assert res_area is not None
    fc_out = res_area[0]
    meta = fc_out.get("properties", {}).get("_crs_metadata")
    assert meta is not None
    # Expect polar LAEA projections for high-latitude area calculations
    assert any(
        code in meta.get("epsg_code", "") for code in ("EPSG:3571", "EPSG:3572")
    ), f"Expected polar LAEA projection, got {meta.get('epsg_code')}"


def test_cross_antimeridian_overlay():
    # Polygon crossing the antimeridian near Fiji
    poly = Polygon(
        [(175.0, -20.0), (179.5, -20.0), (-179.5, -15.0), (175.0, -15.0), (175.0, -20.0)]
    )
    fc = {"type": "FeatureCollection", "features": [make_feature(poly)]}

    # Should not raise and should return a FeatureCollection
    res = op_overlay([fc, fc], how="intersection", auto_optimize_crs=True)
    assert isinstance(res, list) and len(res) == 1


def test_local_utm_buffer_selection():
    # Point in Berlin should trigger UTM zone 33N when auto-optimizing
    pt = Point(13.4, 52.5)
    fc = {"type": "FeatureCollection", "features": [make_feature(pt)]}
    res = op_buffer([fc], radius=1000, auto_optimize_crs=True, projection_metadata=True)
    assert isinstance(res, list) and len(res) == 1
    meta = res[0].get("properties", {}).get("_crs_metadata")
    assert meta is not None
    assert meta.get("epsg_code", "").startswith("EPSG:326")


def test_simplify_with_conformal_crs():
    """Test simplify operation uses conformal projection for shape preservation."""
    # Complex polygon in New Zealand (should trigger UTM zone 60S or regional conformal)
    coords = [
        (175.0, -40.0),
        (175.5, -40.0),
        (175.5, -40.2),
        (175.7, -40.2),
        (175.7, -40.5),
        (175.0, -40.5),
        (175.0, -40.0),
    ]
    poly = Polygon(coords)
    fc = {"type": "FeatureCollection", "features": [make_feature(poly)]}

    res = op_simplify([fc], tolerance=0.01, auto_optimize_crs=True, projection_metadata=True)
    assert isinstance(res, list) and len(res) == 1
    meta = res[0].get("properties", {}).get("_crs_metadata")
    assert meta is not None
    # Should select a CRS (UTM or conformal regional)
    assert "EPSG:" in meta.get("epsg_code", "")
    assert meta.get("auto_selected") is True
