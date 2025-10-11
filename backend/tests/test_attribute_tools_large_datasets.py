"""
Additional tests for attribute_tools.py focusing on large datasets and edge cases.
These tests complement the existing test_attribute_tools.py with scenarios similar
to the user journey tests but using synthetic public data.
"""

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, Polygon

from services.tools.attribute_tools import (
    aggregate_attributes_across_layers,
    build_schema_context,
    describe_dataset_gdf,
    filter_where_gdf,
    get_attribute_values_gdf,
    list_fields_gdf,
    parse_where,
    summarize_gdf,
    unique_values_gdf,
)


@pytest.fixture
def large_attribute_gdf():
    """
    Create a GeoDataFrame with many attributes (similar to Protected Areas with 92 attributes).
    Simulates real-world datasets with numerous attribute columns.
    """
    num_features = 50
    data = {
        "NAME": [f"Protected Area {i}" for i in range(num_features)],
        "ORIG_NAME": [f"Original Name {i}" for i in range(num_features)],
        "IUCN_CAT": ["II", "IV", "Ia", "V", "III"] * 10,
        "STATUS": ["Designated"] * 40 + ["Proposed"] * 10,
        "GIS_AREA": [1000 + i * 500 for i in range(num_features)],
        "REP_AREA": [950 + i * 480 for i in range(num_features)],
        # Biodiversity indicators (like BII - Biodiversity Intactness Index)
        "bii_2020_mean": [0.6 + (i % 20) * 0.01 for i in range(num_features)],
        "bii_2020_median": [0.58 + (i % 20) * 0.01 for i in range(num_features)],
        "bii_2020_std": [0.05 + (i % 10) * 0.01 for i in range(num_features)],
        "bii_2015_mean": [0.55 + (i % 20) * 0.01 for i in range(num_features)],
        "bii_2015_median": [0.53 + (i % 20) * 0.01 for i in range(num_features)],
        # Threat indicators
        "BUILTUP_area_ha": [10 + i * 5 for i in range(num_features)],
        "POP_gt10_area_ha": [5 + i * 3 for i in range(num_features)],
        "AQUEDUCT_FUTURE_HIGH": [0.1 + (i % 15) * 0.02 for i in range(num_features)],
        # Land use land cover (LULC) fields
        "LULC_111_forest_evergreen_needleaf_ha": [100 + i * 20 for i in range(num_features)],
        "LULC_112_forest_evergreen_broadleaf_ha": [150 + i * 15 for i in range(num_features)],
        "LULC_20_shrubs_ha": [80 + i * 10 for i in range(num_features)],
        "LULC_30_herbaceous_ha": [120 + i * 12 for i in range(num_features)],
        "LULC_80_water_ha": [50 + i * 8 for i in range(num_features)],
        # Administrative fields
        "ISO3": ["ARE"] * num_features,
        "GOV_TYPE": ["National"] * 30 + ["Regional"] * 20,
        "MANG_PLAN": ["Yes"] * 35 + [None] * 15,
    }

    # Add more dummy attributes to reach ~40+ total attributes
    for i in range(20):
        data[f"extra_attr_{i}"] = [f"value_{j % 5}" for j in range(num_features)]

    # Create simple polygon geometries
    geometries = []
    for i in range(num_features):
        x, y = i % 10, i // 10
        poly = Polygon([(x, y), (x + 0.5, y), (x + 0.5, y + 0.5), (x, y + 0.5)])
        geometries.append(poly)

    data["geometry"] = geometries

    return gpd.GeoDataFrame(data, crs="EPSG:4326")


@pytest.fixture
def protected_area_with_nulls_gdf():
    """Create a GeoDataFrame with many null values (common in real datasets)."""
    data = {
        "NAME": ["Area 1", "Area 2", None, "Area 4", "Area 5"],
        "IUCN_CAT": ["II", None, "IV", None, "V"],
        "STATUS": ["Designated", "Designated", None, "Proposed", "Designated"],
        "GIS_AREA": [1000, 2000, None, 1500, 3000],
        "MANG_PLAN": ["Yes", None, None, "Yes", None],
        "geometry": [Point(i, i) for i in range(5)],
    }
    return gpd.GeoDataFrame(data, crs="EPSG:4326")


class TestLargeAttributeDatasets:
    """Test attribute operations with datasets having many attributes."""

    def test_build_schema_with_many_attributes(self, large_attribute_gdf):
        """Test schema context building with 40+ attributes."""
        schema = build_schema_context(large_attribute_gdf)

        assert "row_count" in schema
        assert schema["row_count"] == 50
        assert "columns" in schema

        # Should cap at max_cols (default 40)
        assert len(schema["columns"]) <= 40

    def test_build_schema_prioritizes_name_fields(self, large_attribute_gdf):
        """Test that NAME-like fields are prioritized in schema context."""
        schema = build_schema_context(large_attribute_gdf)

        # NAME and ORIG_NAME should be in the columns
        col_names = [c["name"] for c in schema["columns"]]
        assert "NAME" in col_names
        assert "ORIG_NAME" in col_names

    def test_list_fields_with_many_attributes(self, large_attribute_gdf):
        """Test list_fields returns all attributes including extra ones."""
        result = list_fields_gdf(large_attribute_gdf)

        assert "fields" in result
        assert result["row_count"] == 50

        # Should have all columns (40+ attributes)
        assert len(result["fields"]) > 40

    def test_filter_with_many_attributes_present(self, large_attribute_gdf):
        """Test that filtering works even with many attributes in the dataframe."""
        result, suggestions = filter_where_gdf(large_attribute_gdf, "GIS_AREA > 20000")

        assert len(result) > 0
        assert all(result["GIS_AREA"] > 20000)
        assert suggestions == {}

    def test_summarize_multiple_biodiversity_fields(self, large_attribute_gdf):
        """Test summarizing multiple biodiversity indicator fields."""
        bii_fields = ["bii_2020_mean", "bii_2020_median", "bii_2015_mean"]
        result = summarize_gdf(large_attribute_gdf, bii_fields)

        for field in bii_fields:
            assert field in result
            assert "count" in result[field]
            assert "mean" in result[field]
            assert result[field]["count"] == 50

    def test_unique_values_on_categorical_with_many_attrs(self, large_attribute_gdf):
        """Test unique_values works correctly with many attributes present."""
        result = unique_values_gdf(large_attribute_gdf, "IUCN_CAT")

        assert result["field"] == "IUCN_CAT"
        assert "values" in result

        # Should have 5 unique categories
        assert len(result["values"]) == 5

        # Check counts
        categories = {v["value"]: v["count"] for v in result["values"]}
        assert categories["II"] == 10
        assert categories["IV"] == 10


class TestNullValueHandling:
    """Test handling of null/missing values in attribute operations."""

    def test_filter_with_is_null(self, protected_area_with_nulls_gdf):
        """Test IS NULL filtering."""
        result, _ = filter_where_gdf(protected_area_with_nulls_gdf, "IUCN_CAT IS NULL")

        assert len(result) == 2
        assert result["IUCN_CAT"].isna().all()

    def test_filter_with_is_not_null(self, protected_area_with_nulls_gdf):
        """Test IS NOT NULL filtering."""
        result, _ = filter_where_gdf(protected_area_with_nulls_gdf, "NAME IS NOT NULL")

        assert len(result) == 4
        assert result["NAME"].notna().all()

    def test_summarize_field_with_nulls(self, protected_area_with_nulls_gdf):
        """Test summarize correctly handles null values."""
        result = summarize_gdf(protected_area_with_nulls_gdf, ["GIS_AREA"])

        # Should only count non-null values
        assert result["GIS_AREA"]["count"] == 4  # One null value excluded

    def test_unique_values_excludes_nulls(self, protected_area_with_nulls_gdf):
        """Test that unique_values excludes null values by default."""
        result = unique_values_gdf(protected_area_with_nulls_gdf, "IUCN_CAT")

        # Should only have 3 non-null unique values
        assert len(result["values"]) == 3

        # Check that null is not in the values
        values = [v["value"] for v in result["values"]]
        assert None not in values
        assert pd.isna(values).sum() == 0


class TestComplexWhereFilters:
    """Test complex WHERE clause scenarios."""

    def test_filter_with_and_operator(self, large_attribute_gdf):
        """Test filtering with AND operator."""
        result, _ = filter_where_gdf(large_attribute_gdf, "GIS_AREA > 20000 AND IUCN_CAT = 'II'")

        assert len(result) > 0
        assert all(result["GIS_AREA"] > 20000)
        assert all(result["IUCN_CAT"] == "II")

    def test_filter_with_or_operator(self, large_attribute_gdf):
        """Test filtering with OR operator."""
        result, _ = filter_where_gdf(large_attribute_gdf, "IUCN_CAT = 'II' OR IUCN_CAT = 'IV'")

        assert len(result) == 20  # 10 + 10
        assert all(result["IUCN_CAT"].isin(["II", "IV"]))

    def test_filter_with_not_operator(self, large_attribute_gdf):
        """Test filtering with NOT operator."""
        result, _ = filter_where_gdf(large_attribute_gdf, "NOT STATUS = 'Proposed'")

        assert len(result) == 40
        assert all(result["STATUS"] == "Designated")

    def test_filter_with_parentheses(self, large_attribute_gdf):
        """Test filtering with parentheses for precedence."""
        result, _ = filter_where_gdf(
            large_attribute_gdf, "(IUCN_CAT = 'II' OR IUCN_CAT = 'IV') AND GIS_AREA > 15000"
        )

        assert all(result["IUCN_CAT"].isin(["II", "IV"]))
        assert all(result["GIS_AREA"] > 15000)

    def test_filter_with_in_operator(self, large_attribute_gdf):
        """Test filtering with IN operator."""
        # First, let's check if parse_where supports IN
        result, _ = filter_where_gdf(large_attribute_gdf, "IUCN_CAT IN ('II', 'IV', 'Ia')")

        assert len(result) == 30  # 10 + 10 + 10
        assert all(result["IUCN_CAT"].isin(["II", "IV", "Ia"]))


class TestFuzzyFieldMatching:
    """Test fuzzy field name matching functionality."""

    def test_case_insensitive_exact_match(self, large_attribute_gdf):
        """Test that case-insensitive exact matches work without suggestions."""
        result, suggestions = filter_where_gdf(large_attribute_gdf, "name = 'Protected Area 1'")

        # Should match 'NAME' field (case-insensitive exact match)
        assert len(result) == 1
        assert suggestions == {}  # Exact match, no suggestion needed

    def test_fuzzy_match_with_typo(self, large_attribute_gdf):
        """Test that typos are corrected via fuzzy matching."""
        result, suggestions = filter_where_gdf(
            large_attribute_gdf, "IUCN_CT = 'II'"
        )  # Typo: CT instead of CAT

        # Should fuzzy match to 'IUCN_CAT'
        assert "IUCN_CT" in suggestions
        assert suggestions["IUCN_CT"] == "IUCN_CAT"
        assert len(result) == 10

    def test_fuzzy_match_similar_field_name(self, large_attribute_gdf):
        """Test fuzzy matching with similar field names."""
        result, suggestions = filter_where_gdf(large_attribute_gdf, "GIS_ARE > 20000")

        # Should fuzzy match 'GIS_ARE' to 'GIS_AREA'
        assert "GIS_ARE" in suggestions
        assert suggestions["GIS_ARE"] == "GIS_AREA"
        assert all(result["GIS_AREA"] > 20000)

    def test_no_match_raises_error(self, large_attribute_gdf):
        """Test that completely unmatched fields raise an error."""
        with pytest.raises(ValueError, match="not found"):
            filter_where_gdf(large_attribute_gdf, "COMPLETELY_WRONG_FIELD = 'value'")


class TestDescribeDatasetWithLargeAttrs:
    """Test describe_dataset with datasets having many attributes."""

    def test_describe_dataset_performance(self, large_attribute_gdf):
        """Test that describe_dataset works efficiently with many attributes."""
        schema = build_schema_context(large_attribute_gdf)
        result = describe_dataset_gdf(large_attribute_gdf, schema)

        assert "row_count" in result
        assert result["row_count"] == 50
        assert "summary" in result
        # Note: suggested_next_steps has been removed to reduce LLM calls

    def test_describe_dataset_identifies_key_columns(self, large_attribute_gdf):
        """Test that key columns are properly identified."""
        schema = build_schema_context(large_attribute_gdf)
        result = describe_dataset_gdf(large_attribute_gdf, schema)

        assert "key_columns" in result
        key_col_names = [c["name"] for c in result["key_columns"]]

        # NAME should be prioritized
        assert "NAME" in key_col_names

    def test_describe_dataset_suggests_relevant_actions(self, large_attribute_gdf):
        """Test that dataset description includes summary (next steps removed)."""
        schema = build_schema_context(large_attribute_gdf)
        result = describe_dataset_gdf(large_attribute_gdf, schema)

        # suggested_next_steps has been removed to reduce LLM calls
        # Verify that other essential information is present
        assert "summary" in result
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0


class TestRealWorldScenarios:
    """Test scenarios inspired by the user journey."""

    def test_scenario_filter_by_name(self, large_attribute_gdf):
        """Scenario: User asks to show a specific protected area by name."""
        result, _ = filter_where_gdf(large_attribute_gdf, "NAME = 'Protected Area 15'")

        assert len(result) == 1
        assert result["NAME"].iloc[0] == "Protected Area 15"

    def test_scenario_biodiversity_assessment(self, large_attribute_gdf):
        """Scenario: User asks to assess biodiversity status."""
        # Filter to a specific area
        area, _ = filter_where_gdf(large_attribute_gdf, "NAME = 'Protected Area 15'")

        # Summarize biodiversity indicators
        bii_fields = [
            "bii_2020_mean",
            "bii_2020_median",
            "bii_2015_mean",
            "bii_2015_median",
        ]
        result = summarize_gdf(area, bii_fields)

        # Should have stats for each field
        for field in bii_fields:
            assert field in result
            assert result[field]["count"] == 1

    def test_scenario_threat_assessment(self, large_attribute_gdf):
        """Scenario: User asks to assess threats to a protected area."""
        # Filter to a specific area
        area, _ = filter_where_gdf(large_attribute_gdf, "NAME = 'Protected Area 15'")

        # Summarize threat indicators
        threat_fields = ["BUILTUP_area_ha", "POP_gt10_area_ha", "AQUEDUCT_FUTURE_HIGH"]
        result = summarize_gdf(area, threat_fields)

        # Should have stats for each threat indicator
        for field in threat_fields:
            assert field in result

    def test_scenario_filter_high_biodiversity_areas(self, large_attribute_gdf):
        """Scenario: User asks to find areas with high biodiversity."""
        result, _ = filter_where_gdf(large_attribute_gdf, "bii_2020_mean > 0.7")

        # Should have some high-biodiversity areas
        assert len(result) > 0
        assert all(result["bii_2020_mean"] > 0.7)

    def test_scenario_filter_by_category_and_status(self, large_attribute_gdf):
        """Scenario: User asks for designated areas of a specific IUCN category."""
        result, _ = filter_where_gdf(
            large_attribute_gdf, "IUCN_CAT = 'II' AND STATUS = 'Designated'"
        )

        assert len(result) > 0
        assert all(result["IUCN_CAT"] == "II")
        assert all(result["STATUS"] == "Designated")

    def test_scenario_list_all_categories(self, large_attribute_gdf):
        """Scenario: User asks what IUCN categories are present."""
        result = unique_values_gdf(large_attribute_gdf, "IUCN_CAT")

        assert result["field"] == "IUCN_CAT"
        assert len(result["values"]) == 5

        # Check that all expected categories are present
        categories = {v["value"] for v in result["values"]}
        assert categories == {"II", "IV", "Ia", "V", "III"}


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling scenarios."""

    def test_filter_returns_empty_dataframe(self, large_attribute_gdf):
        """Test filtering that matches no features returns empty GeoDataFrame."""
        result, _ = filter_where_gdf(large_attribute_gdf, "GIS_AREA > 1000000")

        assert len(result) == 0
        assert isinstance(result, gpd.GeoDataFrame)

    def test_summarize_with_nonexistent_field(self, large_attribute_gdf):
        """Test summarize with field that doesn't exist."""
        result = summarize_gdf(large_attribute_gdf, ["NONEXISTENT_FIELD"])

        assert "NONEXISTENT_FIELD" in result
        assert "error" in result["NONEXISTENT_FIELD"]

    def test_unique_values_with_nonexistent_field(self, large_attribute_gdf):
        """Test unique_values with field that doesn't exist."""
        result = unique_values_gdf(large_attribute_gdf, "NONEXISTENT_FIELD")

        assert result["field"] == "NONEXISTENT_FIELD"
        assert "error" in result

    def test_parse_where_invalid_syntax(self):
        """Test that invalid WHERE syntax raises an error."""
        with pytest.raises(ValueError):
            parse_where("INVALID SYNTAX HERE")

    def test_filter_with_numeric_comparison_on_string_field(self, large_attribute_gdf):
        """Test filtering with numeric comparison on string field."""
        # This should not crash, but may return empty result
        result, _ = filter_where_gdf(large_attribute_gdf, "NAME > 100")

        # Should return empty or partial result depending on coercion
        assert isinstance(result, gpd.GeoDataFrame)


class TestSchemaContextDetails:
    """Test detailed aspects of schema context building."""

    def test_schema_includes_top_values_for_text_fields(self, large_attribute_gdf):
        """Test that text fields include top values."""
        schema = build_schema_context(large_attribute_gdf)

        # Find a categorical text field
        status_col = next((c for c in schema["columns"] if c["name"] == "STATUS"), None)
        assert status_col is not None
        assert "top_values" in status_col
        assert len(status_col["top_values"]) > 0

    def test_schema_includes_min_max_for_numeric_fields(self, large_attribute_gdf):
        """Test that numeric fields include min/max values."""
        schema = build_schema_context(large_attribute_gdf)

        # Find a numeric field
        area_col = next((c for c in schema["columns"] if c["name"] == "GIS_AREA"), None)
        assert area_col is not None
        assert "min" in area_col
        assert "max" in area_col
        assert area_col["min"] < area_col["max"]

    def test_schema_geometry_column_identified(self, large_attribute_gdf):
        """Test that geometry column is properly identified."""
        schema = build_schema_context(large_attribute_gdf)

        assert "geometry_column" in schema
        assert schema["geometry_column"] == "geometry"

        # Geometry column should be in columns list
        geom_col = next((c for c in schema["columns"] if c["name"] == "geometry"), None)
        assert geom_col is not None
        assert geom_col["type"] == "geometry"

    def test_schema_with_custom_max_cols(self, large_attribute_gdf):
        """Test schema context with custom max_cols parameter."""
        schema = build_schema_context(large_attribute_gdf, max_cols=20)

        # Should cap at 20 columns
        assert len(schema["columns"]) <= 20


class TestPerformanceWithLargeDatasets:
    """Test performance characteristics with larger datasets."""

    def test_filter_performance_is_acceptable(self, large_attribute_gdf):
        """Test that filtering completes in reasonable time."""
        import time

        start = time.time()
        result, _ = filter_where_gdf(large_attribute_gdf, "GIS_AREA > 15000")
        elapsed = time.time() - start

        # Should complete very quickly (< 0.5 seconds for 50 features)
        assert elapsed < 0.5
        assert isinstance(result, gpd.GeoDataFrame)

    def test_schema_building_is_fast(self, large_attribute_gdf):
        """Test that schema building is fast even with many attributes."""
        import time

        start = time.time()
        schema = build_schema_context(large_attribute_gdf)
        elapsed = time.time() - start

        # Should complete quickly (< 0.5 seconds)
        assert elapsed < 0.5
        assert schema is not None

    def test_list_fields_is_fast(self, large_attribute_gdf):
        """Test that list_fields completes quickly."""
        import time

        start = time.time()
        result = list_fields_gdf(large_attribute_gdf)
        elapsed = time.time() - start

        # Should complete quickly (< 1 second)
        assert elapsed < 1.0
        assert result is not None


class TestGetAttributeValues:
    """Test the new get_attribute_values_gdf operation."""

    def test_get_attribute_values_basic(self, large_attribute_gdf):
        """Test basic retrieval of specific attribute values."""
        result = get_attribute_values_gdf(large_attribute_gdf, ["NAME", "IUCN_CAT", "STATUS"])

        assert "columns" in result
        assert len(result["columns"]) == 3
        assert "NAME" in result["columns"]
        assert "IUCN_CAT" in result["columns"]
        assert "STATUS" in result["columns"]

        assert len(result["columns"]["NAME"]) == 50
        assert len(result["columns"]["IUCN_CAT"]) == 50
        assert len(result["columns"]["STATUS"]) == 50

    def test_get_attribute_values_with_filter(self, large_attribute_gdf):
        """Test retrieval with WHERE clause filtering."""
        result = get_attribute_values_gdf(
            large_attribute_gdf, ["NAME", "GIS_AREA"], row_filter="GIS_AREA > 5000"
        )

        assert "row_count" in result
        assert result["row_count"] < 50  # Should be filtered
        assert len(result["columns"]["NAME"]) == result["row_count"]
        assert all(area > 5000 for area in result["columns"]["GIS_AREA"])

    def test_get_attribute_values_fuzzy_matching(self, large_attribute_gdf):
        """Test fuzzy field name matching."""
        # Request 'name' instead of 'NAME'
        result = get_attribute_values_gdf(large_attribute_gdf, ["name", "iucn_cat"])

        assert "field_suggestions" in result or "columns" in result
        # Should still retrieve data with corrected field names
        if "field_suggestions" in result:
            assert len(result["field_suggestions"]) > 0

    def test_get_attribute_values_missing_column(self, large_attribute_gdf):
        """Test error handling for non-existent columns."""
        result = get_attribute_values_gdf(large_attribute_gdf, ["NAME", "NONEXISTENT_FIELD"])

        assert "missing_columns" in result
        assert "NONEXISTENT_FIELD" in result["missing_columns"]
        # NAME should still be retrieved
        assert "columns" in result
        assert "NAME" in result["columns"]

    def test_get_attribute_values_numeric_fields(self, large_attribute_gdf):
        """Test retrieval of numeric attribute values."""
        result = get_attribute_values_gdf(
            large_attribute_gdf, ["GIS_AREA", "REP_AREA", "bii_2020_mean"]
        )

        assert len(result["columns"]) == 3
        assert all(isinstance(v, (int, float)) for v in result["columns"]["GIS_AREA"])
        assert all(isinstance(v, (int, float)) for v in result["columns"]["REP_AREA"])

    def test_get_attribute_values_with_nulls(self, protected_area_with_nulls_gdf):
        """Test retrieval when fields contain null values."""
        result = get_attribute_values_gdf(
            protected_area_with_nulls_gdf, ["NAME", "IUCN_CAT", "MANG_PLAN"]
        )

        assert "columns" in result
        assert None in result["columns"]["NAME"]
        assert None in result["columns"]["IUCN_CAT"]
        assert None in result["columns"]["MANG_PLAN"]

    def test_get_attribute_values_empty_columns_list(self, large_attribute_gdf):
        """Test error handling for empty columns list."""
        result = get_attribute_values_gdf(large_attribute_gdf, [])

        assert "error" in result
        assert "at least one column" in result["error"].lower()

    def test_get_attribute_values_single_column(self, large_attribute_gdf):
        """Test retrieval of a single column."""
        result = get_attribute_values_gdf(large_attribute_gdf, ["NAME"])

        assert len(result["columns"]) == 1
        assert "NAME" in result["columns"]
        assert len(result["columns"]["NAME"]) == 50

    def test_get_attribute_values_filtered_to_zero_rows(self, large_attribute_gdf):
        """Test retrieval when filter matches no rows."""
        result = get_attribute_values_gdf(
            large_attribute_gdf, ["NAME", "GIS_AREA"], row_filter="GIS_AREA > 999999"
        )

        assert result["row_count"] == 0
        assert "error" in result  # Should indicate no features match
        assert "columns" in result
        assert len(result["columns"]) == 0  # No data when filter matches nothing

    def test_get_attribute_values_performance(self, large_attribute_gdf):
        """Test that get_attribute_values completes quickly."""
        import time

        start = time.time()
        result = get_attribute_values_gdf(
            large_attribute_gdf, ["NAME", "IUCN_CAT", "GIS_AREA", "bii_2020_mean"]
        )
        elapsed = time.time() - start

        # Should complete quickly (< 0.5 seconds)
        assert elapsed < 0.5
        assert result is not None
        assert "columns" in result


class TestMultiLayerAggregation:
    """Test multi-layer attribute aggregation functionality."""

    @pytest.fixture
    def mock_state_with_layers(self, large_attribute_gdf, protected_area_with_nulls_gdf):
        """Create a mock state with multiple layers."""
        import tempfile

        from models.geodata import DataOrigin, DataType, GeoDataObject

        # Save GeoDataFrames to temporary files
        temp_dir = tempfile.mkdtemp()

        # Layer 1: Protected Areas
        layer1_path = f"{temp_dir}/protected_areas.geojson"
        large_attribute_gdf.to_file(layer1_path, driver="GeoJSON")

        # Layer 2: Conservation Sites (using nulls gdf as different layer)
        layer2_path = f"{temp_dir}/conservation_sites.geojson"
        protected_area_with_nulls_gdf.to_file(layer2_path, driver="GeoJSON")

        # Create GeoDataObjects
        layer1 = GeoDataObject(
            id="layer1",
            data_source_id="test_source_1",
            data_source="Test Source",
            name="Protected Areas",
            title="Protected Areas UAE",
            data_link=layer1_path,
            data_origin=DataOrigin.UPLOAD,
            data_type=DataType.GEOJSON,
        )

        layer2 = GeoDataObject(
            id="layer2",
            data_source_id="test_source_2",
            data_source="Test Source",
            name="Conservation Sites",
            title="Conservation Sites UAE",
            data_link=layer2_path,
            data_origin=DataOrigin.UPLOAD,
            data_type=DataType.GEOJSON,
        )

        return {
            "geodata_layers": [layer1, layer2],
            "messages": [],
        }

    def test_aggregate_single_layer(self, mock_state_with_layers):
        """Test aggregation across a single layer."""
        result = aggregate_attributes_across_layers(
            state=mock_state_with_layers,
            layer_names=["Protected Areas"],
            columns_per_layer={"Protected Areas": ["NAME", "IUCN_CAT"]},
        )

        assert "Protected Areas" in result
        assert "columns" in result["Protected Areas"]
        assert "NAME" in result["Protected Areas"]["columns"]
        assert "IUCN_CAT" in result["Protected Areas"]["columns"]
        assert result["Protected Areas"]["row_count"] == 50

    def test_aggregate_multiple_layers(self, mock_state_with_layers):
        """Test aggregation across multiple layers."""
        result = aggregate_attributes_across_layers(
            state=mock_state_with_layers,
            layer_names=["Protected Areas", "Conservation Sites"],
            columns_per_layer={
                "Protected Areas": ["NAME", "GIS_AREA"],
                "Conservation Sites": ["NAME", "IUCN_CAT"],
            },
        )

        assert "Protected Areas" in result
        assert "Conservation Sites" in result
        assert result["Protected Areas"]["row_count"] == 50
        assert result["Conservation Sites"]["row_count"] == 5

    def test_aggregate_with_missing_layer(self, mock_state_with_layers):
        """Test handling of non-existent layer."""
        result = aggregate_attributes_across_layers(
            state=mock_state_with_layers,
            layer_names=["Nonexistent Layer"],
            columns_per_layer={"Nonexistent Layer": ["NAME"]},
        )

        assert "Nonexistent Layer" in result
        assert "error" in result["Nonexistent Layer"]
        assert "not found" in result["Nonexistent Layer"]["error"].lower()
        assert "available_layers" in result["Nonexistent Layer"]

    def test_aggregate_with_compare_summary(self, mock_state_with_layers):
        """Test aggregation with compare summary type."""
        result = aggregate_attributes_across_layers(
            state=mock_state_with_layers,
            layer_names=["Protected Areas", "Conservation Sites"],
            columns_per_layer={
                "Protected Areas": ["NAME"],
                "Conservation Sites": ["NAME"],
            },
            summary_type="compare",
        )

        assert "combined_summary" in result
        summary = result["combined_summary"]
        assert summary["summary_type"] == "compare"
        assert summary["total_layers"] == 2
        assert summary["successful_layers"] == 2
        assert "layer_row_counts" in summary
        assert summary["layer_row_counts"]["Protected Areas"] == 50
        assert summary["layer_row_counts"]["Conservation Sites"] == 5

    def test_aggregate_with_combine_summary(self, mock_state_with_layers):
        """Test aggregation with combine summary type."""
        result = aggregate_attributes_across_layers(
            state=mock_state_with_layers,
            layer_names=["Protected Areas", "Conservation Sites"],
            columns_per_layer={
                "Protected Areas": ["NAME", "GIS_AREA"],
                "Conservation Sites": ["NAME", "IUCN_CAT"],
            },
            summary_type="combine",
        )

        assert "combined_summary" in result
        summary = result["combined_summary"]
        assert summary["summary_type"] == "combine"
        assert "all_columns_across_layers" in summary
        assert set(summary["all_columns_across_layers"]) == {"NAME", "GIS_AREA", "IUCN_CAT"}

    def test_aggregate_with_stats_summary(self, mock_state_with_layers):
        """Test aggregation with stats summary type."""
        result = aggregate_attributes_across_layers(
            state=mock_state_with_layers,
            layer_names=["Protected Areas", "Conservation Sites"],
            columns_per_layer={
                "Protected Areas": ["NAME", "GIS_AREA"],
                "Conservation Sites": ["NAME"],
            },
            summary_type="stats",
        )

        assert "combined_summary" in result
        summary = result["combined_summary"]
        assert summary["summary_type"] == "stats"
        assert summary["total_features_across_layers"] == 55  # 50 + 5
        assert summary["total_columns_retrieved"] == 3  # 2 + 1

    def test_aggregate_with_no_columns_specified(self, mock_state_with_layers):
        """Test handling when no columns specified for a layer."""
        result = aggregate_attributes_across_layers(
            state=mock_state_with_layers,
            layer_names=["Protected Areas"],
            columns_per_layer={},  # No columns specified
        )

        assert "Protected Areas" in result
        assert "error" in result["Protected Areas"]
        assert "no columns specified" in result["Protected Areas"]["error"].lower()

    def test_aggregate_partial_success(self, mock_state_with_layers):
        """Test aggregation with mix of successful and failed layers."""
        result = aggregate_attributes_across_layers(
            state=mock_state_with_layers,
            layer_names=["Protected Areas", "Nonexistent Layer"],
            columns_per_layer={
                "Protected Areas": ["NAME"],
                "Nonexistent Layer": ["NAME"],
            },
            summary_type="compare",
        )

        assert "combined_summary" in result
        summary = result["combined_summary"]
        assert summary["total_layers"] == 2
        assert summary["successful_layers"] == 1
        assert len(summary["failed_layers"]) == 1
        assert summary["failed_layers"][0]["layer"] == "Nonexistent Layer"

    def test_aggregate_performance(self, mock_state_with_layers):
        """Test that multi-layer aggregation completes quickly."""
        import time

        start = time.time()
        result = aggregate_attributes_across_layers(
            state=mock_state_with_layers,
            layer_names=["Protected Areas", "Conservation Sites"],
            columns_per_layer={
                "Protected Areas": ["NAME", "GIS_AREA", "IUCN_CAT"],
                "Conservation Sites": ["NAME", "STATUS"],
            },
            summary_type="stats",
        )
        elapsed = time.time() - start

        # Should complete quickly (< 1 second for 2 layers)
        assert elapsed < 1.0
        assert "combined_summary" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
