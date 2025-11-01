"""
Tests for buffer method selection (planar vs geodesic).

Tests criteria including:
- Radius thresholds
- Latitude thresholds
- Zone crossing detection
- Antimeridian handling
- Geodesic buffer accuracy for points
"""

import pytest
import geopandas as gpd
from shapely.geometry import Point, MultiPoint, Polygon
from services.tools.geoprocessing.ops.buffer import (
    choose_buffer_method,
    create_geodesic_buffer_point,
    create_geodesic_buffer,
    op_buffer,
)
from services.tools.geoprocessing.projection_utils import compute_bbox_metrics


class TestBufferMethodSelection:
    """Test buffer method selection logic."""

    def test_small_radius_local_uses_planar(self):
        """Test small radius in local area uses planar."""
        # Berlin, 10 km radius
        bbox = (13.0, 52.0, 13.5, 52.5)
        metrics = compute_bbox_metrics(bbox)

        gdf = gpd.GeoDataFrame(geometry=[Point(13.4, 52.5)], crs="EPSG:4326")
        method, reason = choose_buffer_method(gdf, 10000, metrics)

        assert method == "planar"
        assert "Local extent" in reason or "moderate radius" in reason

    def test_large_radius_uses_geodesic(self):
        """Test large radius triggers geodesic."""
        # Berlin, 100 km radius
        bbox = (13.0, 52.0, 13.5, 52.5)
        metrics = compute_bbox_metrics(bbox)

        gdf = gpd.GeoDataFrame(geometry=[Point(13.4, 52.5)], crs="EPSG:4326")
        method, reason = choose_buffer_method(gdf, 100000, metrics)

        assert method == "geodesic"
        assert "Large radius" in reason

    def test_high_latitude_uses_geodesic(self):
        """Test high latitude triggers geodesic even with small radius."""
        # Arctic, 10 km radius
        bbox = (10.0, 78.0, 11.0, 79.0)
        metrics = compute_bbox_metrics(bbox)

        gdf = gpd.GeoDataFrame(geometry=[Point(10.5, 78.5)], crs="EPSG:4326")
        method, reason = choose_buffer_method(gdf, 10000, metrics)

        assert method == "geodesic"
        assert "High latitude" in reason

    def test_zone_crossing_uses_geodesic(self):
        """Test crossing UTM zones triggers geodesic."""
        # Spanning 2 zones
        bbox = (6.0, 51.0, 15.0, 53.0)
        metrics = compute_bbox_metrics(bbox)

        gdf = gpd.GeoDataFrame(geometry=[Point(10.0, 52.0)], crs="EPSG:4326")
        method, reason = choose_buffer_method(gdf, 20000, metrics)

        assert method == "geodesic"
        assert "UTM zones" in reason

    def test_antimeridian_uses_geodesic(self):
        """Test antimeridian crossing triggers geodesic."""
        # Pacific
        bbox = (170.0, -10.0, -170.0, 10.0)
        metrics = compute_bbox_metrics(bbox)

        gdf = gpd.GeoDataFrame(geometry=[Point(175.0, 0.0)], crs="EPSG:4326")
        method, reason = choose_buffer_method(gdf, 10000, metrics)

        assert method == "geodesic"
        assert "antimeridian" in reason

    def test_non_local_extent_uses_geodesic(self):
        """Test non-local extent triggers geodesic."""
        # Large area
        bbox = (10.0, 45.0, 25.0, 55.0)
        metrics = compute_bbox_metrics(bbox)

        gdf = gpd.GeoDataFrame(geometry=[Point(15.0, 50.0)], crs="EPSG:4326")
        method, reason = choose_buffer_method(gdf, 30000, metrics)

        assert method == "geodesic"
        assert "Non-local extent" in reason


class TestGeodesicBufferPoint:
    """Test geodesic buffer creation for points."""

    def test_geodesic_buffer_point_shape(self):
        """Test geodesic buffer creates valid polygon."""
        # Berlin
        buffer = create_geodesic_buffer_point(13.4, 52.5, 10000, num_points=36)

        assert isinstance(buffer, Polygon)
        assert buffer.is_valid
        # Should have 36 + 1 (closing) = 37 points
        assert len(buffer.exterior.coords) == 37

    def test_geodesic_buffer_equator(self):
        """Test geodesic buffer at equator (nearly circular)."""
        # Equator
        buffer = create_geodesic_buffer_point(0.0, 0.0, 100000, num_points=72)

        assert isinstance(buffer, Polygon)
        assert buffer.is_valid

        # At equator, geodesic buffer should be nearly circular
        # Check rough diameter (should be ~200 km)
        bounds = buffer.bounds
        width = bounds[2] - bounds[0]  # degrees
        # At equator, 1 degree ≈ 111 km, so ~200 km ≈ 1.8 degrees
        assert 1.5 < width < 2.1

    def test_geodesic_buffer_high_latitude(self):
        """Test geodesic buffer at high latitude (elliptical in degrees)."""
        # Arctic
        buffer = create_geodesic_buffer_point(10.0, 80.0, 100000, num_points=72)

        assert isinstance(buffer, Polygon)
        assert buffer.is_valid

        # At high latitude, geodesic buffer appears elliptical in degrees
        # (wider in longitude than latitude)
        bounds = buffer.bounds
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]

        # Width should be significantly larger than height
        assert width > height * 2

    def test_geodesic_buffer_resolution(self):
        """Test different resolutions for different radii."""
        # Small radius
        buffer_small = create_geodesic_buffer_point(13.4, 52.5, 10000, num_points=36)
        # Large radius
        buffer_large = create_geodesic_buffer_point(13.4, 52.5, 600000, num_points=180)

        # Large buffers should have more points for accuracy
        assert len(buffer_large.exterior.coords) > len(buffer_small.exterior.coords)


class TestGeodesicBufferGeoDataFrame:
    """Test geodesic buffer for GeoDataFrames."""

    def test_geodesic_buffer_single_point(self):
        """Test geodesic buffer for single point."""
        gdf = gpd.GeoDataFrame(geometry=[Point(13.4, 52.5)], crs="EPSG:4326")
        result = create_geodesic_buffer(gdf, 50000)

        assert len(result) == 1
        assert isinstance(result.geometry.iloc[0], Polygon)
        assert result.geometry.iloc[0].is_valid

    def test_geodesic_buffer_multipoint(self):
        """Test geodesic buffer for MultiPoint."""
        mp = MultiPoint([Point(13.0, 52.0), Point(14.0, 53.0)])
        gdf = gpd.GeoDataFrame(geometry=[mp], crs="EPSG:4326")
        result = create_geodesic_buffer(gdf, 50000)

        assert len(result) == 1
        # Result should be union of two circular buffers
        assert isinstance(result.geometry.iloc[0], (Polygon, MultiPoint.__bases__))
        assert result.geometry.iloc[0].is_valid

    def test_geodesic_buffer_preserves_crs(self):
        """Test geodesic buffer preserves CRS."""
        gdf = gpd.GeoDataFrame(geometry=[Point(13.4, 52.5)], crs="EPSG:4326")
        result = create_geodesic_buffer(gdf, 50000)

        assert result.crs == gdf.crs

    def test_geodesic_buffer_preserves_attributes(self):
        """Test geodesic buffer preserves feature attributes."""
        gdf = gpd.GeoDataFrame(
            {"name": ["Berlin"], "geometry": [Point(13.4, 52.5)]}, crs="EPSG:4326"
        )
        result = create_geodesic_buffer(gdf, 50000)

        assert "name" in result.columns
        assert result["name"].iloc[0] == "Berlin"


class TestBufferIntegration:
    """Test buffer operation with method selection."""

    def test_buffer_geodesic_metadata(self):
        """Test geodesic buffer includes correct metadata."""
        # Arctic point, should trigger geodesic
        feature = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [10.0, 78.0]},
            "properties": {"name": "Arctic"},
        }

        result = op_buffer(
            [feature],
            radius=10000,
            radius_unit="meters",
            auto_optimize_crs=True,
            projection_metadata=True,
        )

        assert len(result) == 1
        fc = result[0]

        # Check metadata
        assert "_crs_metadata" in fc.get("properties", {})
        metadata = fc["properties"]["_crs_metadata"]
        assert metadata["buffer_method"] == "geodesic"
        assert "High latitude" in metadata["buffer_method_reason"]

    def test_buffer_planar_metadata(self):
        """Test planar buffer includes correct metadata."""
        # Berlin, small radius, should use planar
        feature = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [13.4, 52.5]},
            "properties": {"name": "Berlin"},
        }

        result = op_buffer(
            [feature],
            radius=10,
            radius_unit="kilometers",
            auto_optimize_crs=True,
            projection_metadata=True,
        )

        assert len(result) == 1
        fc = result[0]

        # Check metadata
        assert "_crs_metadata" in fc.get("properties", {})
        metadata = fc["properties"]["_crs_metadata"]
        assert metadata["buffer_method"] == "planar"
        assert "UTM" in metadata.get("crs_name", "")

    def test_buffer_large_radius_geodesic(self):
        """Test large radius triggers geodesic buffer."""
        feature = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [0.0, 0.0]},
            "properties": {},
        }

        result = op_buffer(
            [feature],
            radius=100,
            radius_unit="kilometers",
            auto_optimize_crs=True,
            projection_metadata=True,
        )

        assert len(result) == 1
        fc = result[0]
        metadata = fc["properties"]["_crs_metadata"]
        assert metadata["buffer_method"] == "geodesic"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
