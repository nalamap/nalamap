import pytest
import geopandas as gpd
from shapely.geometry import Point

from services.tools.geoprocessing.projection_utils import (
    get_optimal_crs_for_bbox,
    OperationType,
    validate_crs,
    prepare_gdf_for_operation,
)


class TestCRSSelection:
    """Test CRS selection logic."""

    def test_utm_selection_for_local_extent(self):
        """Test UTM selection for small areas."""
        bbox = (13.0, 52.0, 14.0, 53.0)
        result = get_optimal_crs_for_bbox(bbox, OperationType.BUFFER)

        assert result["epsg_code"].startswith("EPSG:326")
        assert "UTM" in result["crs_name"]

    def test_polar_projection_arctic(self):
        """Test Arctic projection selection."""
        bbox = (10.0, 82.0, 30.0, 85.0)

        # For area operations
        result = get_optimal_crs_for_bbox(bbox, OperationType.AREA)
        assert result["epsg_code"] == "EPSG:3571"

        # For overlay operations
        result = get_optimal_crs_for_bbox(bbox, OperationType.OVERLAY)
        assert result["epsg_code"] == "EPSG:3995"

    def test_regional_projection_north_america(self):
        bbox = (-100.0, 40.0, -85.0, 50.0)
        result = get_optimal_crs_for_bbox(bbox, OperationType.AREA)
        assert "North America" in result["crs_name"]
        assert "Albers" in result["crs_name"]

    def test_fallback_for_global_extent(self):
        bbox = (-180.0, -90.0, 180.0, 90.0)
        result = get_optimal_crs_for_bbox(bbox, OperationType.BUFFER)
        assert result["epsg_code"] == "EPSG:3857"
        assert "too large" in result["selection_reason"].lower()

    def test_cross_antimeridian_handling(self):
        bbox = (175.0, -20.0, -175.0, -15.0)
        result = get_optimal_crs_for_bbox(bbox, OperationType.OVERLAY)
        assert result["epsg_code"] is not None

    @pytest.mark.parametrize(
        "operation,expected_property",
        [
            (OperationType.AREA, "equal-area"),
            (OperationType.BUFFER, "conformal"),
            (OperationType.OVERLAY, "conformal"),
            (OperationType.DISSOLVE, "equal-area"),
        ],
    )
    def test_operation_property_mapping(self, operation, expected_property):
        bbox = (0.0, 45.0, 10.0, 55.0)
        result = get_optimal_crs_for_bbox(bbox, operation)

    def test_crs_validation(self):
        assert validate_crs("EPSG:4326") is True
        assert validate_crs("EPSG:32633") is True
        assert validate_crs("EPSG:99999") is False
        assert validate_crs("INVALID") is False

    def test_prepare_gdf_with_auto_optimization(self):
        gdf = gpd.GeoDataFrame(
            {"name": ["A", "B"]},
            geometry=[Point(13.4, 52.5), Point(13.5, 52.6)],
            crs="EPSG:4326",
        )

        gdf_transformed, crs_info = prepare_gdf_for_operation(
            gdf, OperationType.BUFFER, auto_optimize_crs=True
        )

        assert "326" in str(gdf_transformed.crs)
        assert crs_info["auto_selected"] is True
        assert "UTM" in crs_info["crs_name"]

    def test_prepare_gdf_with_override(self):
        gdf = gpd.GeoDataFrame({"name": ["A"]}, geometry=[Point(0, 0)], crs="EPSG:4326")

        gdf_transformed, crs_info = prepare_gdf_for_operation(
            gdf, OperationType.AREA, override_crs="EPSG:3395"
        )

        assert "3395" in str(gdf_transformed.crs)
        assert crs_info["auto_selected"] is False
        assert "Manual override" in crs_info["selection_reason"]


class TestOperationIntegration:

    def test_buffer_with_smart_crs(self):
        from services.tools.geoprocessing.ops.buffer import op_buffer

        feature = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [0, 0]},
            "properties": {"name": "Equator Point"},
        }

        result = op_buffer(
            [{"type": "FeatureCollection", "features": [feature]}],
            radius=1000,
            auto_optimize_crs=True,
            projection_metadata=True,
        )

        assert len(result) == 1
        fc = result[0]
        assert "_crs_metadata" in fc.get("properties", {})
        assert fc["properties"]["_crs_metadata"]["auto_selected"] is True

    def test_area_calculation_accuracy(self):
        from services.tools.geoprocessing.ops.area import op_area

        test_cases = [
            (0, 0, "equator"),
            (45, 45, "mid-latitude"),
            (70, 20, "high-latitude"),
        ]

        for lat, lon, description in test_cases:
            delta = 0.01
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [lon - delta, lat - delta],
                            [lon + delta, lat - delta],
                            [lon + delta, lat + delta],
                            [lon - delta, lat + delta],
                            [lon - delta, lat - delta],
                        ]
                    ],
                },
                "properties": {"location": description},
            }

            result = op_area(
                [{"type": "FeatureCollection", "features": [feature]}],
                unit="square_kilometers",
                auto_optimize_crs=True,
            )

            assert len(result) == 1
            calculated_area = result[0]["features"][0]["properties"]["area"]
            assert 0.1 < calculated_area < 10.0
