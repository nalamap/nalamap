"""
Comprehensive test suite for attribute_tool2.py.

Tests focus on the simplified interface and agent-friendliness of attribute_tool2.
The underlying operations are already tested in test_attribute_tools.py.
"""

import json
from unittest.mock import patch

import geopandas as gpd
import pytest
from shapely.geometry import Point

from models.geodata import DataOrigin, DataType, GeoDataObject


@pytest.fixture
def sample_gdf():
    """Create a sample GeoDataFrame for testing."""
    data = {
        "name": ["Feature A", "Feature B", "Feature C", "Feature D"],
        "value": [10, 20, 15, 30],
        "category": ["cat1", "cat2", "cat1", "cat2"],
        "population": [1000, 5000, 3000, 8000],
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


@pytest.fixture
def mock_state(sample_layer):
    """Create a mock GeoDataAgentState with sample layer."""
    return {
        "geodata_layers": [sample_layer],
        "geodata_results": [],
        "messages": [],
    }


class TestListFieldsOperation:
    """Test list_fields operation."""

    @patch("services.tools.attribute_tool2._load_gdf")
    def test_list_fields_success(self, mock_load, sample_gdf, mock_state):
        """Test successful list_fields operation."""
        from services.tools.attribute_tool2 import attribute_tool2

        mock_load.return_value = sample_gdf

        result = attribute_tool2.func(
            state=mock_state,
            tool_call_id="test-id",
            operation="list_fields",
            target_layer_name="test_layer",
        )

        messages = result.update["messages"]
        assert len(messages) == 1
        content = json.loads(messages[0].content)
        assert content["operation"] == "list_fields"
        assert "fields" in content["result"]


class TestSummarizeOperation:
    """Test summarize operation."""

    @patch("services.tools.attribute_tool2._load_gdf")
    def test_summarize_success(self, mock_load, sample_gdf, mock_state):
        """Test successful summarize operation."""
        from services.tools.attribute_tool2 import attribute_tool2

        mock_load.return_value = sample_gdf

        result = attribute_tool2.func(
            state=mock_state,
            tool_call_id="test-id",
            operation="summarize",
            fields=["value", "population"],
        )

        messages = result.update["messages"]
        content = json.loads(messages[0].content)
        assert content["operation"] == "summarize"
        assert "value" in content["result"]
        assert content["result"]["value"]["count"] == 4

    @patch("services.tools.attribute_tool2._load_gdf")
    def test_summarize_missing_param(self, mock_load, sample_gdf, mock_state):
        """Test summarize without fields parameter."""
        from services.tools.attribute_tool2 import attribute_tool2

        mock_load.return_value = sample_gdf

        result = attribute_tool2.func(
            state=mock_state,
            tool_call_id="test-id",
            operation="summarize",
        )

        messages = result.update["messages"]
        assert messages[0].status == "error"
        assert "'fields' parameter is required" in messages[0].content


class TestUniqueValuesOperation:
    """Test unique_values operation."""

    @patch("services.tools.attribute_tool2._load_gdf")
    def test_unique_values_success(self, mock_load, sample_gdf, mock_state):
        """Test successful unique_values operation."""
        from services.tools.attribute_tool2 import attribute_tool2

        mock_load.return_value = sample_gdf

        result = attribute_tool2.func(
            state=mock_state,
            tool_call_id="test-id",
            operation="unique_values",
            field="category",
        )

        messages = result.update["messages"]
        content = json.loads(messages[0].content)
        assert content["operation"] == "unique_values"
        assert content["result"]["field"] == "category"
        assert len(content["result"]["values"]) == 2


class TestFilterWhereOperation:
    """Test filter_where operation."""

    @patch("services.tools.attribute_tools.store_file")
    @patch("services.tools.attribute_tool2._load_gdf")
    def test_filter_where_success(self, mock_load, mock_store, sample_gdf, mock_state):
        """Test successful filter_where operation."""
        from services.tools.attribute_tool2 import attribute_tool2

        mock_load.return_value = sample_gdf
        mock_store.return_value = ("http://localhost/test.geojson", "test.geojson")

        result = attribute_tool2.func(
            state=mock_state,
            tool_call_id="test-id",
            operation="filter_where",
            where="value > 15",
        )

        # Should create a new layer
        assert "geodata_results" in result.update
        assert len(result.update["geodata_results"]) == 1

        # Should have success message
        messages = result.update["messages"]
        assert "Successfully filtered" in messages[0].content

    @patch("services.tools.attribute_tool2._load_gdf")
    def test_filter_where_missing_param(self, mock_load, sample_gdf, mock_state):
        """Test filter_where without where parameter."""
        from services.tools.attribute_tool2 import attribute_tool2

        mock_load.return_value = sample_gdf

        result = attribute_tool2.func(
            state=mock_state,
            tool_call_id="test-id",
            operation="filter_where",
        )

        messages = result.update["messages"]
        assert messages[0].status == "error"
        assert "'where' parameter is required" in messages[0].content


class TestSelectFieldsOperation:
    """Test select_fields operation."""

    @patch("services.tools.attribute_tools.store_file")
    @patch("services.tools.attribute_tool2._load_gdf")
    def test_select_fields_include(self, mock_load, mock_store, sample_gdf, mock_state):
        """Test select_fields with include parameter."""
        from services.tools.attribute_tool2 import attribute_tool2

        mock_load.return_value = sample_gdf
        mock_store.return_value = ("http://localhost/test.geojson", "test.geojson")

        result = attribute_tool2.func(
            state=mock_state,
            tool_call_id="test-id",
            operation="select_fields",
            include_fields=["name", "value"],
        )

        # Should create a new layer
        assert "geodata_results" in result.update
        assert len(result.update["geodata_results"]) == 1


class TestSortByOperation:
    """Test sort_by operation."""

    @patch("services.tools.attribute_tools.store_file")
    @patch("services.tools.attribute_tool2._load_gdf")
    def test_sort_by_success(self, mock_load, mock_store, sample_gdf, mock_state):
        """Test successful sort_by operation."""
        from services.tools.attribute_tool2 import attribute_tool2

        mock_load.return_value = sample_gdf
        mock_store.return_value = ("http://localhost/test.geojson", "test.geojson")

        result = attribute_tool2.func(
            state=mock_state,
            tool_call_id="test-id",
            operation="sort_by",
            sort_fields=[("value", "desc")],
        )

        # Should create a new layer
        assert "geodata_results" in result.update


class TestDescribeDatasetOperation:
    """Test describe_dataset operation."""

    @patch("services.tools.attribute_tool2._load_gdf")
    def test_describe_dataset_success(self, mock_load, sample_gdf, mock_state):
        """Test successful describe_dataset operation."""
        from services.tools.attribute_tool2 import attribute_tool2

        mock_load.return_value = sample_gdf

        result = attribute_tool2.func(
            state=mock_state,
            tool_call_id="test-id",
            operation="describe_dataset",
        )

        messages = result.update["messages"]
        content = json.loads(messages[0].content)
        assert content["operation"] == "describe_dataset"
        assert "row_count" in content["result"]
        assert content["result"]["row_count"] == 4


class TestGetAttributeValuesOperation:
    """Test get_attribute_values operation."""

    @patch("services.tools.attribute_tool2._load_gdf")
    def test_get_attribute_values_success(self, mock_load, sample_gdf, mock_state):
        """Test successful get_attribute_values operation."""
        from services.tools.attribute_tool2 import attribute_tool2

        mock_load.return_value = sample_gdf

        result = attribute_tool2.func(
            state=mock_state,
            tool_call_id="test-id",
            operation="get_attribute_values",
            columns=["name", "value"],
        )

        messages = result.update["messages"]
        content = json.loads(messages[0].content)
        assert content["operation"] == "get_attribute_values"
        assert "name" in content["result"]["columns"]
        assert content["result"]["row_count"] == 4


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_no_layers_in_state(self):
        """Test with empty state."""
        from services.tools.attribute_tool2 import attribute_tool2

        empty_state = {"geodata_layers": [], "geodata_results": [], "messages": []}

        result = attribute_tool2.func(
            state=empty_state,
            tool_call_id="test-id",
            operation="list_fields",
        )

        messages = result.update["messages"]
        assert messages[0].status == "error"
        assert "No geodata layers found" in messages[0].content

    def test_layer_not_found(self, mock_state):
        """Test with non-existent layer."""
        from services.tools.attribute_tool2 import attribute_tool2

        result = attribute_tool2.func(
            state=mock_state,
            tool_call_id="test-id",
            operation="list_fields",
            target_layer_name="nonexistent",
        )

        messages = result.update["messages"]
        assert messages[0].status == "error"
        assert "not found" in messages[0].content

    @patch("services.tools.attribute_tool2._load_gdf")
    def test_load_error(self, mock_load, mock_state):
        """Test error during loading."""
        from services.tools.attribute_tool2 import attribute_tool2

        mock_load.side_effect = Exception("Load failed")

        result = attribute_tool2.func(
            state=mock_state,
            tool_call_id="test-id",
            operation="list_fields",
        )

        messages = result.update["messages"]
        assert messages[0].status == "error"
        assert "Error loading" in messages[0].content


class TestIntegration:
    """Integration tests."""

    @patch("services.tools.attribute_tools.store_file")
    @patch("services.tools.attribute_tool2._load_gdf")
    def test_workflow_explore_then_filter(self, mock_load, mock_store, sample_gdf, mock_state):
        """Test a complete workflow."""
        from services.tools.attribute_tool2 import attribute_tool2

        mock_load.return_value = sample_gdf
        mock_store.return_value = ("http://localhost/test.geojson", "test.geojson")

        # Step 1: List fields
        result1 = attribute_tool2.func(
            state=mock_state,
            tool_call_id="call-1",
            operation="list_fields",
        )
        content1 = json.loads(result1.update["messages"][0].content)
        assert "fields" in content1["result"]

        # Step 2: Get unique values
        result2 = attribute_tool2.func(
            state=mock_state,
            tool_call_id="call-2",
            operation="unique_values",
            field="category",
        )
        content2 = json.loads(result2.update["messages"][0].content)
        assert len(content2["result"]["values"]) == 2

        # Step 3: Filter based on findings
        result3 = attribute_tool2.func(
            state=mock_state,
            tool_call_id="call-3",
            operation="filter_where",
            where="category = 'cat1'",
        )
        assert len(result3.update["geodata_results"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
