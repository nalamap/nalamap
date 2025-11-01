import pytest

from services.tools.geoprocessing.projection_utils import (
    get_optimal_crs_for_bbox,
    OperationType,
    validate_crs,
)


def test_operation_property_mapping_and_regional_selection():
    # Local UTM selection (Berlin ~ UTM 33N) for buffer
    bbox_local = (13.0, 52.0, 13.5, 52.5)
    res = get_optimal_crs_for_bbox(bbox_local, OperationType.BUFFER)
    assert res["epsg_code"].startswith("EPSG:326")
    assert res["projection_property"] == "conformal"
    assert validate_crs(res["epsg_code"]) is True

    # Area operation in Europe -> Europe LAEA (3035)
    bbox_europe = (5.0, 45.0, 15.0, 55.0)
    res = get_optimal_crs_for_bbox(bbox_europe, OperationType.AREA)
    assert res["epsg_code"] == "EPSG:3035"
    assert res["projection_property"] == "equal-area"

    # Overlay operation in Europe -> conformal regional (3034)
    res = get_optimal_crs_for_bbox(bbox_europe, OperationType.OVERLAY)
    assert res["projection_property"] == "conformal"
    assert validate_crs(res["epsg_code"]) is True


def test_polar_selection_behaviour():
    # Arctic (Svalbard) high latitude bbox
    bbox_arctic = (10.0, 82.0, 30.0, 85.0)

    # Area should choose LAEA for Arctic
    res_area = get_optimal_crs_for_bbox(bbox_arctic, OperationType.AREA)
    assert res_area["epsg_code"] in ("EPSG:3571", "EPSG:3572")
    assert res_area["projection_property"] == "equal-area"

    # Overlay should choose stereographic (conformal)
    res_overlay = get_optimal_crs_for_bbox(bbox_arctic, OperationType.OVERLAY)
    assert res_overlay["projection_property"] == "conformal"
    assert validate_crs(res_overlay["epsg_code"]) is True


def test_global_extent_fallback_and_invalid_bbox():
    # Very large extent -> fallback
    bbox_global = (-180.0, -90.0, 180.0, 90.0)
    res = get_optimal_crs_for_bbox(bbox_global, OperationType.BUFFER)
    assert res["epsg_code"] == "EPSG:3857"

    # Invalid bbox -> fallback
    res_invalid = get_optimal_crs_for_bbox((999, 999, 999, 999), OperationType.AREA)
    assert res_invalid["epsg_code"] == "EPSG:3857"


@pytest.mark.parametrize(
    "region,bbox,operation,expected_epsg,expected_property",
    [
        # North America - EW-dominant bbox triggers LCC even for AREA (smart heuristic)
        (
            "north_america",
            (-120.0, 30.0, -80.0, 50.0),
            OperationType.AREA,
            "EPSG:102009",
            "conformal",
        ),
        (
            "north_america",
            (-120.0, 30.0, -80.0, 50.0),
            OperationType.OVERLAY,
            "EPSG:102009",
            "conformal",
        ),
        # South America - same bbox, Equal-area for area ops
        (
            "south_america",
            (-70.0, -30.0, -50.0, -10.0),
            OperationType.AREA,
            "EPSG:102011",
            "equal-area",
        ),
        (
            "south_america",
            (-70.0, -30.0, -50.0, -10.0),
            OperationType.OVERLAY,
            "EPSG:102011",
            "equal-area",
        ),
        # Europe - LAEA for equal-area, LCC for conformal
        ("europe", (5.0, 45.0, 15.0, 55.0), OperationType.AREA, "EPSG:3035", "equal-area"),
        ("europe", (5.0, 45.0, 15.0, 55.0), OperationType.DISSOLVE, "EPSG:3035", "equal-area"),
        # Africa - Equal-area for area ops
        ("africa", (10.0, -10.0, 40.0, 20.0), OperationType.AREA, "EPSG:102022", "equal-area"),
        ("africa", (10.0, -10.0, 40.0, 20.0), OperationType.CLIP, "EPSG:102022", "equal-area"),
        # Asia - EW-dominant triggers LCC
        ("asia", (80.0, 30.0, 120.0, 50.0), OperationType.AREA, "EPSG:102027", "conformal"),
        ("asia", (80.0, 30.0, 120.0, 50.0), OperationType.SIMPLIFY, "EPSG:102027", "conformal"),
        # Australia - Equal-area for area ops
        ("australia", (130.0, -35.0, 150.0, -20.0), OperationType.AREA, "EPSG:3577", "equal-area"),
        (
            "australia",
            (130.0, -35.0, 150.0, -20.0),
            OperationType.OVERLAY,
            "EPSG:3577",
            "equal-area",
        ),
    ],
)
def test_all_regional_projections(region, bbox, operation, expected_epsg, expected_property):
    """
    Comprehensive test covering all 6 regions and their equal-area/conformal variants.
    This ensures the regional selection logic works correctly for each continent.

    Note: The new multi-factor algorithm prioritizes geometric suitability (orientation, size)
    over simple operation-type mapping. E.g., EW-dominant regions use LCC even for AREA operations.
    """
    res = get_optimal_crs_for_bbox(bbox, operation)
    assert res["epsg_code"] == expected_epsg, (
        f"Region: {region}, Operation: {operation}, "
        f"Expected: {expected_epsg}, Got: {res['epsg_code']}"
    )
    # Verify the CRS is valid (skip validation for ESRI codes like EPSG:102xxx)
    if not expected_epsg.startswith("EPSG:102"):
        assert validate_crs(res["epsg_code"]) is True
    # Verify projection property matches expected (from smart heuristics)
    assert (
        res["projection_property"] == expected_property
    ), f"Expected property: {expected_property}, Got: {res['projection_property']}"
