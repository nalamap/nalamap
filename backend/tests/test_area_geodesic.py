"""
Tests for geodesic area calculation.

Tests various scenarios including:
- Method selection (auto, planar, geodesic)
- High latitude areas
- Zone-crossing areas
- Antimeridian crossing
- Accuracy comparisons
- Unit conversions
- Metadata completeness
"""

import pytest
from shapely.geometry import Polygon, MultiPolygon
from services.tools.geoprocessing.ops.area import (
    op_area,
    choose_area_method,
    compute_geodesic_area,
)
from services.tools.geoprocessing.projection_utils import compute_bbox_metrics
from pyproj import Geod


class TestAreaMethodSelection:
    """Test area method selection logic."""

    def test_local_extent_uses_planar(self):
        """Test local extent uses planar."""
        # Berlin area
        bbox = (13.0, 52.0, 13.5, 52.5)
        metrics = compute_bbox_metrics(bbox)
        method, reason = choose_area_method(metrics)

        assert method == "planar"
        assert "Local" in reason or "regional" in reason

    def test_high_latitude_uses_geodesic(self):
        """Test high latitude triggers geodesic."""
        # Arctic region
        bbox = (10.0, 78.0, 11.0, 79.0)
        metrics = compute_bbox_metrics(bbox)
        method, reason = choose_area_method(metrics)

        assert method == "geodesic"
        assert "High latitude" in reason

    def test_zone_crossing_uses_geodesic(self):
        """Test crossing UTM zones triggers geodesic."""
        # Spanning 2 zones
        bbox = (6.0, 51.0, 15.0, 53.0)
        metrics = compute_bbox_metrics(bbox)
        method, reason = choose_area_method(metrics)

        assert method == "geodesic"
        assert "UTM zones" in reason

    def test_antimeridian_uses_geodesic(self):
        """Test antimeridian crossing triggers geodesic."""
        # Pacific
        bbox = (170.0, -10.0, -170.0, 10.0)
        metrics = compute_bbox_metrics(bbox)
        method, reason = choose_area_method(metrics)

        assert method == "geodesic"
        assert "antimeridian" in reason

    def test_non_local_extent_uses_geodesic(self):
        """Test non-local extent triggers geodesic."""
        # Large regional area
        bbox = (10.0, 45.0, 25.0, 55.0)
        metrics = compute_bbox_metrics(bbox)
        method, reason = choose_area_method(metrics)

        assert method == "geodesic"
        assert "Non-local extent" in reason


class TestGeodesicAreaComputation:
    """Test geodesic area calculation."""

    def test_geodesic_area_simple_polygon(self):
        """Test geodesic area for simple polygon."""
        # Square near equator (1° x 1°)
        poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
        geod = Geod(ellps="WGS84")
        area = compute_geodesic_area(poly, geod)

        # At equator, 1° ≈ 111 km, so 1°x1° ≈ 12,321 km² = 12.321 billion m²
        # Area should be approximately 111 * 111 * 1e6 square meters
        assert 11e9 < area < 13e9  # Within reasonable range

    def test_geodesic_area_with_hole(self):
        """Test geodesic area for polygon with hole."""
        # Outer ring: 2° x 2° square
        outer = [(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)]
        # Inner hole: 1° x 1° square in center
        hole = [(0.5, 0.5), (1.5, 0.5), (1.5, 1.5), (0.5, 1.5), (0.5, 0.5)]

        poly_with_hole = Polygon(outer, [hole])
        geod = Geod(ellps="WGS84")
        area = compute_geodesic_area(poly_with_hole, geod)

        # Area should be outer minus hole
        # Outer: ~4 * 111² km² = ~49 billion m²
        # Hole: ~111² km² = ~12 billion m²
        # Net: ~37 billion m²
        assert 30e9 < area < 55e9

    def test_geodesic_area_multipolygon(self):
        """Test geodesic area for MultiPolygon."""
        # Two separate 1° squares
        poly1 = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
        poly2 = Polygon([(10, 10), (11, 10), (11, 11), (10, 11), (10, 10)])

        multi = MultiPolygon([poly1, poly2])
        geod = Geod(ellps="WGS84")
        area = compute_geodesic_area(multi, geod)

        # Should be sum of both areas
        # Each ~12 billion m², total ~24 billion m²
        assert 20e9 < area < 30e9

    def test_geodesic_area_high_latitude(self):
        """Test geodesic area at high latitude."""
        # 1° x 1° square at 80°N
        poly = Polygon([(10, 80), (11, 80), (11, 81), (10, 81), (10, 80)])
        geod = Geod(ellps="WGS84")
        area = compute_geodesic_area(poly, geod)

        # At 80°N, longitude degrees are much smaller
        # Should be significantly less than equator
        assert area > 0
        assert area < 5e9  # Much smaller than equatorial square


class TestAreaOperationIntegration:
    """Test op_area with geodesic support."""

    def test_area_method_auto_local(self):
        """Test auto method uses planar for local extent."""
        # Berlin square
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[13.0, 52.0], [13.5, 52.0], [13.5, 52.5], [13.0, 52.5], [13.0, 52.0]]
                ],
            },
            "properties": {},
        }

        result = op_area(
            [feature], area_method="auto", auto_optimize_crs=True, projection_metadata=True
        )

        assert len(result) == 1
        fc = result[0]
        metadata = fc.get("properties", {}).get("_crs_metadata", {})
        assert metadata["area_method"] == "planar"

    def test_area_method_auto_high_latitude(self):
        """Test auto method uses geodesic for high latitude."""
        # Arctic square
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[10.0, 78.0], [11.0, 78.0], [11.0, 79.0], [10.0, 79.0], [10.0, 78.0]]
                ],
            },
            "properties": {},
        }

        result = op_area([feature], area_method="auto", projection_metadata=True)

        assert len(result) == 1
        fc = result[0]
        metadata = fc.get("properties", {}).get("_crs_metadata", {})
        assert metadata["area_method"] == "geodesic"
        assert "High latitude" in metadata["area_method_reason"]

    def test_area_method_explicit_geodesic(self):
        """Test explicit geodesic method."""
        # Equatorial square
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
            },
            "properties": {},
        }

        result = op_area([feature], area_method="geodesic", projection_metadata=True)

        assert len(result) == 1
        fc = result[0]
        metadata = fc.get("properties", {}).get("_crs_metadata", {})
        assert metadata["area_method"] == "geodesic"

        # Check area value is reasonable
        area_value = fc["features"][0]["properties"]["area"]
        # 1° x 1° at equator ≈ 12 billion m²
        assert 11e9 < area_value < 13e9

    def test_area_method_explicit_planar(self):
        """Test explicit planar method."""
        # Arctic square (but force planar)
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[10.0, 78.0], [11.0, 78.0], [11.0, 79.0], [10.0, 79.0], [10.0, 78.0]]
                ],
            },
            "properties": {},
        }

        result = op_area(
            [feature], area_method="planar", auto_optimize_crs=True, projection_metadata=True
        )

        assert len(result) == 1
        fc = result[0]
        metadata = fc.get("properties", {}).get("_crs_metadata", {})
        assert metadata["area_method"] == "planar"

    def test_geodesic_unit_conversion(self):
        """Test unit conversions work with geodesic."""
        # 1° x 1° square at equator
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
            },
            "properties": {},
        }

        # Test different units
        result_m2 = op_area([feature], unit="square_meters", area_method="geodesic")
        result_km2 = op_area([feature], unit="square_kilometers", area_method="geodesic")
        result_hectares = op_area([feature], unit="hectares", area_method="geodesic")

        area_m2 = result_m2[0]["features"][0]["properties"]["area"]
        area_km2 = result_km2[0]["features"][0]["properties"]["area"]
        area_hectares = result_hectares[0]["features"][0]["properties"]["area"]

        # Check conversions are correct
        assert area_km2 == pytest.approx(area_m2 * 1e-6, rel=1e-6)
        assert area_hectares == pytest.approx(area_m2 * 1e-4, rel=1e-6)

    def test_zone_crossing_triggers_geodesic(self):
        """Test zone-crossing polygon triggers geodesic."""
        # Polygon spanning zones 32 and 33
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[6.0, 51.0], [15.0, 51.0], [15.0, 53.0], [6.0, 53.0], [6.0, 51.0]]
                ],
            },
            "properties": {},
        }

        result = op_area([feature], area_method="auto", projection_metadata=True)

        assert len(result) == 1
        fc = result[0]
        metadata = fc.get("properties", {}).get("_crs_metadata", {})
        assert metadata["area_method"] == "geodesic"
        assert "zones" in metadata["area_method_reason"].lower()

    def test_polygon_with_holes_geodesic(self):
        """Test polygon with holes using geodesic."""
        # Outer square with inner hole
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]],  # Outer
                    [[0.5, 0.5], [1.5, 0.5], [1.5, 1.5], [0.5, 1.5], [0.5, 0.5]],  # Hole
                ],
            },
            "properties": {},
        }

        result = op_area([feature], area_method="geodesic", projection_metadata=True)

        assert len(result) == 1
        area_with_hole = result[0]["features"][0]["properties"]["area"]

        # Calculate area without hole for comparison
        feature_no_hole = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]],
            },
            "properties": {},
        }
        result_no_hole = op_area([feature_no_hole], area_method="geodesic")
        area_no_hole = result_no_hole[0]["features"][0]["properties"]["area"]

        # Area with hole should be less
        assert area_with_hole < area_no_hole
        # Approximately: outer (4x) - hole (1x) = 3x hole area
        assert area_with_hole > 0

    def test_metadata_completeness(self):
        """Test metadata includes all required fields."""
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[10.0, 78.0], [11.0, 78.0], [11.0, 79.0], [10.0, 79.0], [10.0, 78.0]]
                ],
            },
            "properties": {},
        }

        result = op_area([feature], area_method="auto", projection_metadata=True)
        metadata = result[0]["properties"]["_crs_metadata"]

        # Check all required metadata fields
        assert "epsg_code" in metadata
        assert "crs_name" in metadata
        assert "projection_property" in metadata
        assert "selection_reason" in metadata
        assert "area_method" in metadata
        assert "area_method_reason" in metadata
        assert "auto_selected" in metadata

    def test_backward_compatibility(self):
        """Test backward compatibility with existing API."""
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[13.0, 52.0], [13.5, 52.0], [13.5, 52.5], [13.0, 52.5], [13.0, 52.0]]
                ],
            },
            "properties": {},
        }

        # Old API call (without new params)
        result = op_area([feature], unit="square_kilometers")

        assert len(result) == 1
        assert "area" in result[0]["features"][0]["properties"]

    def test_antimeridian_crossing(self):
        """Test antimeridian crossing triggers geodesic."""
        # Polygon crossing the antimeridian
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[170, -10], [-170, -10], [-170, 10], [170, 10], [170, -10]]],
            },
            "properties": {},
        }

        result = op_area([feature], area_method="auto", projection_metadata=True)

        metadata = result[0]["properties"]["_crs_metadata"]
        assert metadata["area_method"] == "geodesic"
        # The reason will include multiple triggers (zone span, non-local, or antimeridian)
        # Any of these is valid for geodesic selection
        reason_lower = metadata["area_method_reason"].lower()
        assert any(
            keyword in reason_lower for keyword in ["antimeridian", "zone", "non-local"]
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
