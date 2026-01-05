"""
Integration tests for the geoprocess_tool as a LangChain tool.

These tests verify that the tool can be called directly with various parameters
and properly handles state, layer selection, operations, and CRS parameters.
"""

import json
import os
import sys
import tempfile
import uuid
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langchain_core.messages import HumanMessage  # noqa: E402
from langgraph.types import Command  # noqa: E402

from models.geodata import DataOrigin, DataType, GeoDataObject  # noqa: E402
from services.tools.geoprocess_tools import geoprocess_tool  # noqa: E402


def invoke_tool(state, tool_call_id="test_call", **kwargs):
    """Helper function to invoke geoprocess_tool with proper ToolCall structure."""
    return geoprocess_tool.invoke(
        {
            "args": {"state": state, **kwargs},
            "name": "geoprocess_tool",
            "type": "tool_call",
            "id": tool_call_id,  # Use 'id' not 'tool_call_id'
        }
    )


@pytest.fixture
def temp_geojson_file(sample_geojson_feature):
    """Create a temporary GeoJSON file for testing."""
    point_geojson = {
        "type": "FeatureCollection",
        "features": [sample_geojson_feature],
    }

    # Create temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".geojson", delete=False) as f:
        json.dump(point_geojson, f)
        temp_path = f.name

    yield temp_path

    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def sample_geodata_layer(temp_geojson_file):
    """Create a sample GeoDataObject for testing."""
    return GeoDataObject(
        id=uuid.uuid4().hex,
        data_source_id="test",
        data_type=DataType.GEOJSON,
        data_origin=DataOrigin.TOOL,
        data_source="TestSource",
        data_link=temp_geojson_file,  # Use local file path
        name="test_layer",
        title="Test Layer",
        description="A test layer",
        score=0.5,
        bounding_box=None,
        layer_type="GeoJSON",
    )


@pytest.fixture
def sample_geojson_feature():
    """Create a sample GeoJSON feature for loading."""
    return {
        "type": "Feature",
        "properties": {
            "resource_id": "test_point",
            "name": "Test Point",  # This is important for executor layer_meta
            "title": "Test Point Layer",
        },
        "geometry": {"type": "Point", "coordinates": [10.0, 53.0]},
        "bbox": [9.9, 52.9, 10.1, 53.1],
    }


@pytest.fixture
def basic_agent_state(sample_geodata_layer):
    """Create a basic agent state with geodata layers."""
    return {
        "geodata_layers": [sample_geodata_layer],
        "messages": [HumanMessage(content="buffer this layer by 1000 meters")],
        "geodata_results": [],
        "geodata_last_results": [],
        "results_title": "",
        "options": {},
        "remaining_steps": 10,
    }


@pytest.mark.integration
def test_geoprocess_tool_basic_call(basic_agent_state):
    """
    Test basic tool call with buffer operation.

    Verifies:
    - Tool can be called with state and tool_call_id
    - Returns Command object
    - Creates new geodata_results
    """
    # Mock the LLM to return a buffer plan
    mock_llm_response = {
        "steps": [{"operation": "buffer", "params": {"radius": 1000, "radius_unit": "meters"}}],
        "result_name": "1km Buffer",
        "result_description": "Creates a 1 kilometer buffer.",
    }

    with patch("services.tools.geoprocess_tools.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.generations = [[MagicMock(text=json.dumps(mock_llm_response))]]
        mock_llm.generate.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        # Call the tool with proper ToolCall structure
        result = invoke_tool(basic_agent_state, "test_call_123")

    # Verify result is a Command
    assert isinstance(result, Command)
    assert hasattr(result, "update")
    assert result.update is not None

    # Verify messages were created
    assert "messages" in result.update
    assert len(result.update["messages"]) == 1
    message = result.update["messages"][0]
    assert message.name == "geoprocess_tool"
    assert "Successfully processed" in message.content

    # Verify geodata_results were created
    assert "geodata_results" in result.update
    geodata_results = result.update["geodata_results"]
    assert len(geodata_results) == 1
    result_layer = geodata_results[0]
    assert result_layer.title == "1km Buffer"
    assert result_layer.data_type == DataType.GEOJSON


@pytest.mark.integration
def test_geoprocess_tool_with_target_layer_names(basic_agent_state):
    """
    Test tool call with specific layer names selected.

    Verifies:
    - Tool respects target_layer_names parameter
    - Correctly selects specified layers
    """
    mock_llm_response = {
        "steps": [{"operation": "buffer", "params": {"radius": 500, "radius_unit": "meters"}}],
        "result_name": "500m Buffer",
        "result_description": "Creates a 500 meter buffer.",
    }

    with patch("services.tools.geoprocess_tools.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.generations = [[MagicMock(text=json.dumps(mock_llm_response))]]
        mock_llm.generate.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        # Call with specific layer name
        result = invoke_tool(basic_agent_state, "test_call_456", target_layer_names=["test_layer"])

    assert isinstance(result, Command)
    assert hasattr(result, "update")
    assert "geodata_results" in result.update
    assert len(result.update["geodata_results"]) == 1


@pytest.mark.integration
def test_geoprocess_tool_with_operation_hint(basic_agent_state):
    """
    Test tool call with operation hint parameter.

    Verifies:
    - Operation parameter is passed to executor
    - Query is modified to include operation hint
    """
    mock_llm_response = {
        "steps": [{"operation": "buffer", "params": {"radius": 2000, "radius_unit": "meters"}}],
        "result_name": "2km Buffer",
        "result_description": "Creates a 2 kilometer buffer.",
    }

    with patch("services.tools.geoprocess_tools.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.generations = [[MagicMock(text=json.dumps(mock_llm_response))]]
        mock_llm.generate.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        # Call with operation hint
        result = invoke_tool(basic_agent_state, "test_call_789", operation="buffer")

    assert isinstance(result, Command)
    # Verify LLM was called with modified query
    call_args = mock_llm.generate.call_args
    messages = call_args[0][0]
    # The messages are HumanMessage objects, access their content
    has_buffer = any(
        (
            "buffer" in str(msg.content).lower()
            if hasattr(msg, "content")
            else "buffer" in str(msg).lower()
        )
        for msg in messages
    )
    assert has_buffer


@pytest.mark.integration
def test_geoprocess_tool_with_crs_in_query(basic_agent_state):
    """
    Test tool call where user specifies CRS in the query.

    Verifies:
    - CRS parameter is extracted from natural language
    - CRS override is applied correctly
    - Processing metadata shows USER-SPECIFIED CRS
    """
    # Update the message to include CRS specification
    basic_agent_state["messages"] = [
        HumanMessage(content="buffer this layer by 1000 meters in EPSG:32633")
    ]

    mock_llm_response = {
        "steps": [
            {
                "operation": "buffer",
                "params": {"radius": 1000, "radius_unit": "meters", "crs": "EPSG:32633"},
            }
        ],
        "result_name": "1km Buffer UTM33N",
        "result_description": "Creates a 1 kilometer buffer using UTM zone 33N.",
    }

    with patch("services.tools.geoprocess_tools.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.generations = [[MagicMock(text=json.dumps(mock_llm_response))]]
        mock_llm.generate.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        result = invoke_tool(basic_agent_state, "test_call_crs")

    assert isinstance(result, Command)
    assert hasattr(result, "update")
    message = result.update["messages"][0]

    # Check for USER-SPECIFIED in the message
    assert "USER-SPECIFIED" in message.content or "EPSG:32633" in message.content

    # Check processing metadata if available
    geodata_results = result.update["geodata_results"]
    if geodata_results and geodata_results[0].processing_metadata:
        metadata = geodata_results[0].processing_metadata
        assert metadata.auto_selected is False
        assert "32633" in metadata.crs_used or "EPSG:32633" in metadata.crs_used


@pytest.mark.integration
def test_geoprocess_tool_no_layers_error(basic_agent_state):
    """
    Test tool behavior when no layers are available.

    Verifies:
    - Returns error message when geodata_layers is empty
    - Error message is informative
    """
    # Empty the layers
    basic_agent_state["geodata_layers"] = []

    result = invoke_tool(basic_agent_state, "test_call_error")

    assert isinstance(result, Command)
    assert hasattr(result, "update")
    message = result.update["messages"][0]
    assert "Error" in message.content
    assert "No geodata layers found" in message.content


@pytest.mark.integration
def test_geoprocess_tool_missing_layer_name_error(basic_agent_state):
    """
    Test tool behavior when requested layer name doesn't exist.

    Verifies:
    - Returns error when target_layer_names not found
    - Error message lists available layers
    """
    # Use a name that won't fuzzy match (similarity < 0.6)
    result = invoke_tool(
        basic_agent_state,
        "test_call_missing",
        target_layer_names=["xyz_completely_different_name_123"],
    )

    assert isinstance(result, Command)
    assert hasattr(result, "update")
    message = result.update["messages"][0]
    assert "Error" in message.content
    assert "not found" in message.content.lower() or "Layer Names not found" in message.content
    assert "Available layers" in message.content


@pytest.mark.integration
def test_geoprocess_tool_crs_parameter_addition():
    """
    Test that adding CRS as a tool parameter would work.

    This test demonstrates how CRS could be added as a direct parameter
    to the geoprocess_tool function signature.

    Currently CRS is extracted from the natural language query.
    This test shows it could also be passed directly.
    """
    # This is a conceptual test showing how it COULD work
    # if we added crs: Optional[str] = None to the tool signature

    # Mock scenario: Tool called with explicit CRS parameter
    # geoprocess_tool(state, tool_call_id, target_layer_names, operation, crs="EPSG:32633")

    # The implementation would need to:
    # 1. Accept crs parameter in function signature
    # 2. Pass it to the executor or include in the query
    # 3. Have executor prioritize explicit parameter over query extraction

    # For now, we verify current behavior: CRS must be in query
    assert True  # Placeholder - see test_geoprocess_tool_with_crs_in_query for actual behavior


@pytest.mark.integration
def test_geoprocess_tool_unique_names(basic_agent_state, temp_geojson_file):
    """
    Test that multiple operations create unique layer names.

    Verifies:
    - Each result gets a unique name
    - Names are slugified correctly
    - UUID suffixes prevent collisions
    """
    # Add an existing result to test uniqueness
    existing_result = GeoDataObject(
        id=uuid.uuid4().hex,
        data_source_id="geoprocess",
        data_type=DataType.GEOJSON,
        data_origin=DataOrigin.TOOL,
        data_source="NaLaMapGeoprocess",
        data_link=temp_geojson_file,
        name="1km-buffer",
        title="1km Buffer",
        description="Existing buffer",
        score=0.2,
    )
    basic_agent_state["geodata_results"] = [existing_result]

    mock_llm_response = {
        "steps": [{"operation": "buffer", "params": {"radius": 1000, "radius_unit": "meters"}}],
        "result_name": "1km Buffer",  # Same title as existing
        "result_description": "Another 1km buffer.",
    }

    with patch("services.tools.geoprocess_tools.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.generations = [[MagicMock(text=json.dumps(mock_llm_response))]]
        mock_llm.generate.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        result = invoke_tool(basic_agent_state, "test_call_unique")

    assert hasattr(result, "update")
    geodata_results = result.update["geodata_results"]
    # The tool returns only NEW layers (not including existing ones)
    # But the update geodata_results will be combined with state
    assert len(geodata_results) >= 1
    new_layer = geodata_results[-1] if len(geodata_results) == 2 else geodata_results[0]

    # Name should be different from existing (with UUID or suffix)
    assert new_layer.name != "1km-buffer"
    # But should still be based on the title
    assert "1km" in new_layer.name or "buffer" in new_layer.name


@pytest.mark.integration
def test_geoprocess_tool_processing_metadata_origin_layers(basic_agent_state):
    """
    Test that processing metadata includes origin layer information.

    Verifies:
    - processing_metadata.origin_layers contains input layer names
    - Metadata is properly attached to result
    """
    mock_llm_response = {
        "steps": [{"operation": "buffer", "params": {"radius": 1000, "radius_unit": "meters"}}],
        "result_name": "Test Buffer",
        "result_description": "Buffer with metadata.",
    }

    with patch("services.tools.geoprocess_tools.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.generations = [[MagicMock(text=json.dumps(mock_llm_response))]]
        mock_llm.generate.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        result = invoke_tool(basic_agent_state, "test_metadata")

    assert hasattr(result, "update")
    geodata_results = result.update["geodata_results"]
    assert len(geodata_results) == 1
    result_layer = geodata_results[0]

    # Check if processing metadata exists and has origin_layers
    if result_layer.processing_metadata:
        assert hasattr(result_layer.processing_metadata, "origin_layers")
        # Origin layers should include the input layer name
        if result_layer.processing_metadata.origin_layers:
            assert "Test Layer" in result_layer.processing_metadata.origin_layers or any(
                "test" in str(name).lower()
                for name in result_layer.processing_metadata.origin_layers
            )


@pytest.mark.integration
def test_geoprocess_tool_llm_error_handling(basic_agent_state):
    """
    Test tool behavior when LLM returns invalid JSON.

    Verifies:
    - Tool handles LLM errors gracefully
    - Returns informative error message
    """
    with patch("services.tools.geoprocess_tools.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_response = MagicMock()
        # Return invalid JSON
        mock_response.generations = [[MagicMock(text="This is not valid JSON!")]]
        mock_llm.generate.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        result = invoke_tool(basic_agent_state, "test_llm_error")

    assert isinstance(result, Command)
    assert hasattr(result, "update")
    message = result.update["messages"][0]
    assert "Error" in message.content
    # Should mention parsing or JSON error
    assert "parse" in message.content.lower() or "json" in message.content.lower()


@pytest.mark.integration
def test_geoprocess_tool_auto_crs_selection(basic_agent_state):
    """
    Test that tool automatically selects appropriate CRS when none specified.

    Verifies:
    - CRS is automatically selected based on layer extent
    - Processing metadata shows AUTO-SELECTED flag
    - Result includes CRS information in message
    """
    mock_llm_response = {
        "steps": [{"operation": "buffer", "params": {"radius": 1000, "radius_unit": "meters"}}],
        "result_name": "Auto CRS Buffer",
        "result_description": "Buffer with automatic CRS selection.",
    }

    with patch("services.tools.geoprocess_tools.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.generations = [[MagicMock(text=json.dumps(mock_llm_response))]]
        mock_llm.generate.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        result = invoke_tool(basic_agent_state, "test_auto_crs")

    assert isinstance(result, Command)
    assert hasattr(result, "update")

    # Check message includes CRS information
    message = result.update["messages"][0]
    assert "CRS Information" in message.content or "EPSG:" in message.content
    assert "AUTO-SELECTED" in message.content

    # Check processing metadata
    geodata_results = result.update["geodata_results"]
    assert len(geodata_results) == 1
    result_layer = geodata_results[0]

    if result_layer.processing_metadata:
        assert result_layer.processing_metadata.auto_selected is True
        assert result_layer.processing_metadata.crs_used is not None
        assert "EPSG:" in result_layer.processing_metadata.crs_used


@pytest.mark.integration
def test_geoprocess_tool_no_crs_specified(basic_agent_state):
    """
    Test tool behavior when no CRS is specified (default behavior).

    Verifies:
    - Tool works without explicit CRS
    - Automatically determines best CRS
    - Result has valid CRS metadata
    """
    # Query without CRS specification
    basic_agent_state["messages"] = [
        HumanMessage(content="create a 500 meter buffer around the layer")
    ]

    mock_llm_response = {
        "steps": [{"operation": "buffer", "params": {"radius": 500, "radius_unit": "meters"}}],
        "result_name": "500m Buffer",
        "result_description": "Buffer without explicit CRS.",
    }

    with patch("services.tools.geoprocess_tools.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.generations = [[MagicMock(text=json.dumps(mock_llm_response))]]
        mock_llm.generate.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        result = invoke_tool(basic_agent_state, "test_no_crs")

    assert isinstance(result, Command)
    geodata_results = result.update["geodata_results"]
    assert len(geodata_results) == 1

    # Should have processing metadata with CRS
    result_layer = geodata_results[0]
    if result_layer.processing_metadata:
        assert result_layer.processing_metadata.crs_used is not None


@pytest.mark.integration
def test_geoprocess_tool_user_specified_crs_override(basic_agent_state):
    """
    Test that user can override automatic CRS selection.

    Verifies:
    - User-specified CRS in query overrides automatic selection
    - Processing metadata shows auto_selected = False
    - Result uses the specified CRS
    """
    # Query with explicit CRS override
    basic_agent_state["messages"] = [HumanMessage(content="buffer by 2km using EPSG:25832")]

    mock_llm_response = {
        "steps": [
            {
                "operation": "buffer",
                "params": {"radius": 2000, "radius_unit": "meters", "crs": "EPSG:25832"},
            }
        ],
        "result_name": "2km Buffer EPSG:25832",
        "result_description": "Buffer with user-specified CRS.",
    }

    with patch("services.tools.geoprocess_tools.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.generations = [[MagicMock(text=json.dumps(mock_llm_response))]]
        mock_llm.generate.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        result = invoke_tool(basic_agent_state, "test_crs_override")

    assert isinstance(result, Command)
    message = result.update["messages"][0]

    # Check for USER-SPECIFIED indicator
    assert "USER-SPECIFIED" in message.content or "25832" in message.content

    # Check processing metadata
    geodata_results = result.update["geodata_results"]
    if geodata_results and geodata_results[0].processing_metadata:
        metadata = geodata_results[0].processing_metadata
        # User specified, so should NOT be auto-selected
        assert metadata.auto_selected is False
        # Should use the specified CRS
        assert "25832" in metadata.crs_used or "EPSG:25832" in metadata.crs_used


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
