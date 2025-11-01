"""
Tests for the enhanced projection decision algorithm.

Tests various scenarios including:
- UTM selection with zone seam avoidance
- EW-dominant orientation triggering LCC
- Large area triggering equal-area projections
- Polar region handling
- Antimeridian crossing
- Decision metadata completeness
"""

import pytest
from services.tools.geoprocessing.projection_utils import (
    decide_projection,
    compute_bbox_metrics,
    compute_utm_zone,
    compute_zone_span,
    is_antimeridian_crossing,
    OperationType,
    ProjectionProperty,
)


class TestBboxMetrics:
    """Test bbox metrics computation helpers."""

    def test_compute_utm_zone(self):
        """Test UTM zone calculation."""
        assert compute_utm_zone(0) == 31  # Prime meridian
        assert compute_utm_zone(-180) == 1  # Westernmost
        assert compute_utm_zone(180) == 60  # Wraps to max (clamped)
        assert compute_utm_zone(13.4) == 33  # Berlin ~ zone 33

    def test_compute_zone_span_single(self):
        """Test zone span for single zone."""
        # Berlin area (~3° span within zone 33)
        span = compute_zone_span(12.0, 15.0)
        assert span == 1

    def test_compute_zone_span_multiple(self):
        """Test zone span crossing zones."""
        # Germany (~10° span, crosses 2 zones)
        span = compute_zone_span(6.0, 15.0)
        assert span == 2

    def test_antimeridian_crossing(self):
        """Test antimeridian detection."""
        assert is_antimeridian_crossing(170, -170) is True
        assert is_antimeridian_crossing(10, 20) is False

    def test_bbox_metrics_local(self):
        """Test metrics for local extent (Berlin)."""
        # Berlin: ~52.5°N, 13.4°E, ~3° span
        bbox = (12.0, 51.5, 15.0, 53.5)
        metrics = compute_bbox_metrics(bbox)

        assert metrics["center_lon"] == pytest.approx(13.5, abs=0.1)
        assert metrics["center_lat"] == pytest.approx(52.5, abs=0.1)
        assert metrics["lon_extent"] == pytest.approx(3.0, abs=0.1)
        assert metrics["lat_extent"] == pytest.approx(2.0, abs=0.1)
        assert metrics["zone_span"] == 1
        assert metrics["is_polar"] is False
        assert metrics["antimeridian_crossing"] is False

    def test_bbox_metrics_ew_dominant(self):
        """Test metrics for EW-dominant extent."""
        # Wide EW strip across US
        bbox = (-120.0, 35.0, -70.0, 45.0)
        metrics = compute_bbox_metrics(bbox)

        assert metrics["lon_extent"] > metrics["lat_extent"]
        assert metrics["orientation_ratio"] > 1.5

    def test_bbox_metrics_polar(self):
        """Test metrics for polar region."""
        # Arctic
        bbox = (-30.0, 80.0, 30.0, 85.0)
        metrics = compute_bbox_metrics(bbox)

        assert metrics["is_polar"] is True

    def test_bbox_metrics_antimeridian(self):
        """Test metrics with antimeridian crossing."""
        # Pacific crossing
        bbox = (170.0, -20.0, -170.0, 20.0)
        metrics = compute_bbox_metrics(bbox)

        assert metrics["antimeridian_crossing"] is True
        assert metrics["zone_span"] >= 3


class TestProjectionDecision:
    """Test projection selection logic."""

    def test_local_utm_single_zone(self):
        """Test UTM selection for local extent within single zone."""
        # Berlin area
        bbox = (12.0, 51.5, 15.0, 53.5)
        result = decide_projection(bbox, OperationType.BUFFER)

        assert "EPSG:326" in result["epsg_code"]  # Northern hemisphere UTM
        assert "UTM" in result["crs_name"]
        assert "decision_path" in result
        assert "decision_inputs" in result
        assert any("Local extent" in step for step in result["decision_path"])

    def test_local_utm_avoid_zone_seam(self):
        """Test that UTM is avoided when crossing zone boundary."""
        # Spanning zones 32 and 33 with exactly 6° extent (local but crosses zones)
        bbox = (6.0, 51.0, 12.0, 53.0)  # 6° span, crosses 2 zones (32 and 33)
        result = decide_projection(bbox, OperationType.BUFFER)

        # Should skip UTM due to zone seam crossing and use regional LCC
        assert "UTM" not in result["crs_name"]
        # Decision path should mention zone seam or regional
        assert any(
            "zone" in step.lower() or "seam" in step.lower() or "regional" in step.lower()
            for step in result["decision_path"]
        )

    def test_ew_dominant_uses_lcc(self):
        """Test EW-dominant orientation triggers LCC."""
        # Wide EW strip across US (50° lon, 10° lat)
        bbox = (-120.0, 35.0, -70.0, 45.0)
        result = decide_projection(bbox, OperationType.CLIP)

        # Should detect EW dominance and use LCC
        assert "LCC" in result["crs_name"] or "Lambert Conformal Conic" in result["crs_name"]
        assert any("EW-dominant" in step for step in result["decision_path"])

    def test_large_area_equal_area(self):
        """Test large area triggers equal-area projection."""
        # Large extent covering much of North America
        # Make it roughly square to avoid EW-dominant trigger
        bbox = (-120.0, 25.0, -70.0, 55.0)  # ~50° x 30° = more balanced
        result = decide_projection(bbox, OperationType.DISSOLVE)

        # Should use equal-area (Albers) due to size and operation type
        assert "Albers" in result["crs_name"] or "equal" in result["projection_property"].lower()
        assert result["decision_inputs"]["area_km2"] > 2e6

    def test_polar_arctic_equal_area(self):
        """Test Arctic region uses LAEA for equal-area ops."""
        bbox = (-30.0, 80.0, 30.0, 85.0)
        result = decide_projection(bbox, OperationType.AREA)

        assert "EPSG:3571" == result["epsg_code"]  # Arctic LAEA
        assert "equal-area" in result["projection_property"]
        assert any("Polar" in step for step in result["decision_path"])

    def test_polar_arctic_conformal(self):
        """Test Arctic region uses Stereographic for conformal ops."""
        bbox = (-30.0, 80.0, 30.0, 85.0)
        result = decide_projection(bbox, OperationType.CLIP)

        assert "EPSG:3995" == result["epsg_code"]  # Arctic Stereographic
        assert "conformal" in result["projection_property"]

    def test_polar_antarctic(self):
        """Test Antarctic region."""
        bbox = (-30.0, -85.0, 30.0, -80.0)
        result = decide_projection(bbox, OperationType.AREA)

        assert "EPSG:3572" == result["epsg_code"]  # Antarctic LAEA
        assert "Antarctica" in result["crs_name"]

    def test_regional_europe_conformal(self):
        """Test Europe regional projection for conformal ops."""
        # Central Europe
        bbox = (5.0, 45.0, 20.0, 55.0)
        result = decide_projection(bbox, OperationType.OVERLAY)

        assert "europe" in result["crs_name"].lower() or "EPSG:3034" == result["epsg_code"]
        assert "conformal" in result["projection_property"]

    def test_regional_north_america_equal_area(self):
        """Test North America regional projection for equal-area ops."""
        # US Midwest - make it more square to avoid EW trigger
        bbox = (-100.0, 35.0, -85.0, 50.0)  # 15° x 15° = balanced
        result = decide_projection(bbox, OperationType.AREA)

        assert "Albers" in result["crs_name"] or "equal" in result["projection_property"].lower()
        assert any(
            "north_america" in step.lower() or "North America" in result["crs_name"]
            for step in result["decision_path"]
        )

    def test_antimeridian_crossing(self):
        """Test antimeridian crossing."""
        # Pacific region
        bbox = (170.0, -20.0, -170.0, 20.0)
        result = decide_projection(bbox, OperationType.BUFFER)

        # Should fall back or use appropriate regional
        assert any("antimeridian" in step.lower() for step in result["decision_path"])

    def test_global_extent_fallback(self):
        """Test global extent falls back."""
        bbox = (-180.0, -85.0, 180.0, 85.0)
        result = decide_projection(bbox, OperationType.BUFFER)

        assert "3857" in result["epsg_code"] or "fallback" in result["selection_reason"].lower()
        assert any(
            "too large" in step.lower() or "global" in step.lower()
            for step in result["decision_path"]
        )

    def test_invalid_bbox(self):
        """Test invalid bbox handling."""
        bbox = (-200.0, 0.0, 200.0, 100.0)  # Invalid coords
        result = decide_projection(bbox, OperationType.BUFFER)

        assert "invalid" in result["selection_reason"].lower()
        assert any("invalid" in step.lower() for step in result["decision_path"])

    def test_operation_type_area(self):
        """Test operation type influences projection property."""
        bbox = (10.0, 45.0, 20.0, 55.0)

        result_area = decide_projection(bbox, OperationType.AREA)
        assert result_area["decision_inputs"]["required_property"] == "equal-area"

        result_buffer = decide_projection(bbox, OperationType.BUFFER)
        assert result_buffer["decision_inputs"]["required_property"] == "conformal"

    def test_projection_priority_override(self):
        """Test user can override projection property."""
        bbox = (10.0, 45.0, 20.0, 55.0)

        result = decide_projection(
            bbox, OperationType.AREA, projection_priority=ProjectionProperty.CONFORMAL
        )

        assert any("override" in step.lower() for step in result["decision_path"])

    def test_metadata_completeness(self):
        """Test that all metadata fields are present."""
        bbox = (12.0, 51.5, 15.0, 53.5)
        result = decide_projection(bbox, OperationType.BUFFER)

        # Check all required fields
        assert "epsg_code" in result
        assert "crs_name" in result
        assert "projection_property" in result
        assert "selection_reason" in result
        assert "expected_error" in result
        assert "decision_path" in result
        assert "decision_inputs" in result

        # Check decision_path is a list of strings
        assert isinstance(result["decision_path"], list)
        assert all(isinstance(step, str) for step in result["decision_path"])

        # Check decision_inputs has key metrics
        inputs = result["decision_inputs"]
        assert "bbox" in inputs
        assert "centroid" in inputs
        assert "operation_type" in inputs
        assert "required_property" in inputs

    def test_near_equator_utm(self):
        """Test near-equator regions favor UTM for local extents."""
        # Singapore area
        bbox = (103.6, 1.2, 104.0, 1.5)
        result = decide_projection(bbox, OperationType.BUFFER)

        assert "UTM" in result["crs_name"]
        # Zone 48N = EPSG:32648, Zone 49N = EPSG:32649
        assert "EPSG:32648" in result["epsg_code"] or "EPSG:32649" in result["epsg_code"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
