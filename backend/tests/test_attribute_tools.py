"""Tests for attribute_tools.py - comprehensive coverage of all operations."""

import json
from unittest.mock import Mock, patch

import geopandas as gpd
import pytest
from shapely.geometry import Point

from models.geodata import DataOrigin, DataType, GeoDataObject
from services.tools.attribute_tools import (
    _fc_from_gdf,
    _load_gdf,
    _save_gdf_as_geojson,
    _slug,
    build_schema_context,
    describe_dataset_gdf,
    filter_where_gdf,
    list_fields_gdf,
    parse_where,
    select_fields_gdf,
    sort_by_gdf,
    summarize_gdf,
    unique_values_gdf,
)


@pytest.fixture
def sample_gdf():
    """Create a sample GeoDataFrame for testing."""
    data = {
        "name": ["Feature A", "Feature B", "Feature C", "Feature D"],
        "value": [10, 20, 15, 30],
        "category": ["cat1", "cat2", "cat1", "cat2"],
        "geometry": [
            Point(0, 0),
            Point(1, 1),
            Point(2, 2),
            Point(3, 3),
        ],
    }
    return gpd.GeoDataFrame(data, crs="EPSG:4326")


@pytest.fixture
def sample_layer():
    """Create a sample GeoDataObject for testing."""
    return GeoDataObject(
        id="test-layer-id",
        data_source_id="test",
        data_type=DataType.GEOJSON,
        data_origin=DataOrigin.TOOL,
        data_source="Test",
        data_link="https://example.com/test.geojson",
        name="test_layer",
        title="Test Layer",
        description="Test layer for attribute tools",
        llm_description="Test layer",
        score=1.0,
        bounding_box=None,
        layer_type="GeoJSON",
        properties=None,
    )


class TestSlugify:
    """Test slug generation for filenames."""

    def test_basic_slug(self):
        assert _slug("Test Layer") == "test-layer"

    def test_special_chars_removed(self):
        assert _slug("Test@Layer#123!") == "testlayer123"

    def test_multiple_spaces(self):
        assert _slug("Test   Multiple   Spaces") == "test-multiple-spaces"

    def test_empty_string(self):
        assert _slug("") == "attribute-result"

    def test_all_special_chars(self):
        assert _slug("@#$%") == "attribute-result"


class TestFeatureCollectionConversion:
    """Test GeoDataFrame to GeoJSON FeatureCollection conversion."""

    def test_fc_from_gdf_with_geometry(self, sample_gdf):
        fc = _fc_from_gdf(sample_gdf, keep_geometry=True)
        assert fc["type"] == "FeatureCollection"
        assert len(fc["features"]) == 4
        assert fc["features"][0]["properties"]["name"] == "Feature A"
        assert fc["features"][0]["geometry"] is not None

    def test_fc_from_gdf_without_geometry(self, sample_gdf):
        fc = _fc_from_gdf(sample_gdf, keep_geometry=False)
        assert fc["type"] == "FeatureCollection"
        assert len(fc["features"]) == 4
        assert fc["features"][0]["geometry"] is None
        assert "name" in fc["features"][0]["properties"]


class TestSaveGdfAsGeoJSON:
    """Test saving GeoDataFrame as GeoJSON using central file management."""

    @patch("services.tools.attribute_tools.store_file")
    def test_save_gdf_as_geojson_local(self, mock_store_file, sample_gdf):
        """Test saving GeoDataFrame to local storage."""
        mock_store_file.return_value = (
            "http://localhost:8000/api/stream/test_123.geojson",
            "test_123.geojson",
        )

        result = _save_gdf_as_geojson(sample_gdf, "Test Result", keep_geometry=True)

        # Verify store_file was called
        assert mock_store_file.called
        call_args = mock_store_file.call_args
        filename, content = call_args[0]
        assert filename.endswith(".geojson")
        assert isinstance(content, bytes)

        # Verify the content is valid GeoJSON
        fc = json.loads(content.decode("utf-8"))
        assert fc["type"] == "FeatureCollection"
        assert len(fc["features"]) == 4

        # Verify result object
        assert isinstance(result, GeoDataObject)
        assert result.data_type == DataType.GEOJSON
        assert result.title == "Test Result"
        assert result.data_link == "http://localhost:8000/api/stream/test_123.geojson"

    @patch("services.tools.attribute_tools.store_file")
    def test_save_gdf_without_geometry(self, mock_store_file, sample_gdf):
        """Test saving GeoDataFrame without geometry."""
        mock_store_file.return_value = (
            "http://localhost:8000/api/stream/test_123.geojson",
            "test_123.geojson",
        )

        _save_gdf_as_geojson(sample_gdf, "No Geometry", keep_geometry=False)

        call_args = mock_store_file.call_args
        content = call_args[0][1]
        fc = json.loads(content.decode("utf-8"))

        # Verify geometry is None in all features
        for feature in fc["features"]:
            assert feature["geometry"] is None


class TestLoadGdf:
    """Test loading GeoDataFrame from various sources."""

    @patch("services.tools.attribute_tools.requests.get")
    def test_load_from_http(self, mock_get, tmp_path, sample_gdf):
        """Test loading GeoDataFrame from HTTP URL."""
        # Create a temp GeoJSON file
        temp_file = tmp_path / "test.geojson"
        sample_gdf.to_file(temp_file, driver="GeoJSON")

        with open(temp_file, "rb") as f:
            content = f.read()

        # Mock HTTP response
        mock_response = Mock()
        mock_response.content = content
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Load from HTTP
        with patch("services.tools.attribute_tools.LOCAL_UPLOAD_DIR", str(tmp_path)):
            gdf = _load_gdf("https://example.com/test.geojson")

        assert len(gdf) == 4
        assert "name" in gdf.columns
        assert "value" in gdf.columns

    def test_load_from_local_file(self, tmp_path, sample_gdf):
        """Test loading GeoDataFrame from local file."""
        temp_file = tmp_path / "test.geojson"
        sample_gdf.to_file(temp_file, driver="GeoJSON")

        gdf = _load_gdf(str(temp_file))

        assert len(gdf) == 4
        assert list(gdf["name"]) == ["Feature A", "Feature B", "Feature C", "Feature D"]


class TestListFieldsGdf:
    """Test listing fields operation."""

    def test_list_fields_basic(self, sample_gdf):
        result = list_fields_gdf(sample_gdf)

        assert "fields" in result
        assert "row_count" in result
        assert result["row_count"] == 4
        assert len(result["fields"]) == 4  # name, value, category, geometry

        # Find the name field
        name_field = next(f for f in result["fields"] if f["name"] == "name")
        assert name_field["example"] == "Feature A"
        assert name_field["null_count"] == 0

    def test_list_fields_with_nulls(self):
        data = {
            "field1": [1, 2, None, 4],
            "field2": ["a", None, "c", "d"],
            "geometry": [Point(0, 0), Point(1, 1), Point(2, 2), Point(3, 3)],
        }
        gdf = gpd.GeoDataFrame(data, crs="EPSG:4326")

        result = list_fields_gdf(gdf)

        field1 = next(f for f in result["fields"] if f["name"] == "field1")
        assert field1["null_count"] == 1


class TestSummarizeGdf:
    """Test summarize operation."""

    def test_summarize_numeric_field(self, sample_gdf):
        result = summarize_gdf(sample_gdf, ["value"])

        assert "value" in result
        stats = result["value"]
        assert stats["count"] == 4
        assert stats["mean"] == 18.75  # (10 + 20 + 15 + 30) / 4
        assert stats["min"] == 10
        assert stats["max"] == 30

    def test_summarize_multiple_fields(self, sample_gdf):
        result = summarize_gdf(sample_gdf, ["value"])
        assert len(result) == 1

    def test_summarize_nonexistent_field(self, sample_gdf):
        result = summarize_gdf(sample_gdf, ["nonexistent"])
        assert "nonexistent" in result
        assert "error" in result["nonexistent"]


class TestUniqueValuesGdf:
    """Test unique_values operation."""

    def test_unique_values_all(self, sample_gdf):
        result = unique_values_gdf(sample_gdf, "category")

        assert result["field"] == "category"
        assert "values" in result
        assert len(result["values"]) == 2

        # Should have cat1 and cat2 with counts
        categories = {v["value"]: v["count"] for v in result["values"]}
        assert categories["cat1"] == 2
        assert categories["cat2"] == 2

    def test_unique_values_top_k(self, sample_gdf):
        result = unique_values_gdf(sample_gdf, "category", top_k=1)

        assert len(result["values"]) == 1

    def test_unique_values_nonexistent_field(self, sample_gdf):
        result = unique_values_gdf(sample_gdf, "nonexistent")
        assert "error" in result


class TestParseWhere:
    """Test CQL-lite WHERE clause parsing."""

    def test_parse_simple_comparison(self):
        ast = parse_where("value > 10")
        assert ast[0] == "cmp"
        assert ast[1] == "value"
        assert ast[2] == ">"
        assert ast[3] == 10

    def test_parse_string_comparison(self):
        ast = parse_where("name = 'Feature A'")
        assert ast[0] == "cmp"
        assert ast[1] == "name"
        assert ast[2] == "="
        assert ast[3] == "Feature A"


class TestFilterWhereGdf:
    """Test filter_where operation."""

    def test_filter_simple_comparison(self, sample_gdf):
        result = filter_where_gdf(sample_gdf, "value > 15")
        assert len(result) == 2  # 20 and 30
        assert list(result["name"]) == ["Feature B", "Feature D"]

    def test_filter_string_comparison(self, sample_gdf):
        result = filter_where_gdf(sample_gdf, "name = 'Feature A'")
        assert len(result) == 1
        assert result["name"].iloc[0] == "Feature A"

    def test_filter_invalid_field(self, sample_gdf):
        with pytest.raises(ValueError, match="Unknown field"):
            filter_where_gdf(sample_gdf, "nonexistent > 10")


class TestSelectFieldsGdf:
    """Test select_fields operation."""

    def test_select_include(self, sample_gdf):
        result = select_fields_gdf(sample_gdf, include=["name", "value"])
        assert set(result.columns) == {"name", "value", "geometry"}

    def test_select_exclude(self, sample_gdf):
        result = select_fields_gdf(sample_gdf, exclude=["category"])
        assert "category" not in result.columns
        assert "name" in result.columns
        assert "value" in result.columns


class TestSortByGdf:
    """Test sort_by operation."""

    def test_sort_ascending(self, sample_gdf):
        result = sort_by_gdf(sample_gdf, [("value", "asc")])
        values = list(result["value"])
        assert values == [10, 15, 20, 30]

    def test_sort_descending(self, sample_gdf):
        result = sort_by_gdf(sample_gdf, [("value", "desc")])
        values = list(result["value"])
        assert values == [30, 20, 15, 10]

    def test_sort_multiple_fields(self, sample_gdf):
        result = sort_by_gdf(sample_gdf, [("category", "asc"), ("value", "desc")])
        # cat1 entries should come first, sorted by value desc
        assert list(result["category"])[:2] == ["cat1", "cat1"]


class TestBuildSchemaContext:
    """Test schema context building."""

    def test_build_schema_basic(self, sample_gdf):
        schema = build_schema_context(sample_gdf)

        assert "row_count" in schema
        assert schema["row_count"] == 4
        assert "geometry_column" in schema
        assert "columns" in schema

        # Find the category column
        cat_col = next(c for c in schema["columns"] if c["name"] == "category")
        assert "top_values" in cat_col
        assert set(cat_col["top_values"]) == {"cat1", "cat2"}

    def test_build_schema_numeric_range(self, sample_gdf):
        schema = build_schema_context(sample_gdf)

        value_col = next(c for c in schema["columns"] if c["name"] == "value")
        assert "min" in value_col
        assert "max" in value_col
        assert value_col["min"] == 10
        assert value_col["max"] == 30


class TestDescribeDatasetGdf:
    """Test describe_dataset operation."""

    def test_describe_dataset(self, sample_gdf):
        schema = build_schema_context(sample_gdf)
        result = describe_dataset_gdf(sample_gdf, schema)

        assert "row_count" in result
        assert result["row_count"] == 4
        assert "geometry_types" in result
        assert "Point" in result["geometry_types"]
        assert "summary" in result
        assert "suggested_next_steps" in result
        assert isinstance(result["suggested_next_steps"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
