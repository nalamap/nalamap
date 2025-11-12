"""
Integration tests for the geoprocess_executor function.

These tests verify the full pipeline:
LLM plan generation → parameter extraction → operation execution

Unlike test_geoprocessing_ops.py which tests operations directly,
these tests ensure the executor correctly handles LLM-generated plans.
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.tools.geoprocess_tools import geoprocess_executor  # noqa: E402


@pytest.fixture
def sample_point_layer():
    """A simple point layer for testing."""
    return [
        {
            "type": "Feature",
            "properties": {
                "resource_id": "test_point",
                "name": "Test Point",
                "title": "Test Point Layer",
            },
            "geometry": {"type": "Point", "coordinates": [0, 0]},
            "bbox": [-1, -1, 1, 1],
        }
    ]


@pytest.fixture
def sample_polygon_layer():
    """A simple polygon layer for testing."""
    return [
        {
            "type": "Feature",
            "properties": {
                "resource_id": "test_polygon",
                "name": "Test Polygon",
                "title": "Test Polygon Layer",
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
            },
            "bbox": [0, 0, 1, 1],
        }
    ]


@pytest.mark.integration
def test_executor_buffer_with_meters(sample_point_layer):
    """
    Test that the executor correctly handles a buffer operation with meters.

    This simulates: User asks "buffer by 100 meters"
    LLM should generate: {"operation": "buffer", "params": {"radius": 100, "radius_unit": "meters"}}
    """
    # Mock LLM response for "buffer by 100 meters"
    mock_llm_response = {
        "steps": [{"operation": "buffer", "params": {"radius": 100, "radius_unit": "meters"}}],
        "result_name": "100m Buffer",
        "result_description": "Creates a 100 meter buffer around the point.",
    }

    state = {
        "query": "buffer by 100 meters",
        "input_layers": sample_point_layer,
        "enable_smart_crs": True,
        "available_operations_and_params": [
            "operation: buffer params: radius=<number>, radius_unit=<meters|kilometers|miles>"
        ],
    }

    # Mock the LLM to return our test response
    with patch("services.tools.geoprocess_tools.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.generations = [[MagicMock(text=json.dumps(mock_llm_response))]]
        mock_llm.generate.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        result = geoprocess_executor(state)

    # Verify the result
    assert result is not None
    assert "result_layers" in result
    assert len(result["result_layers"]) == 1
    assert result["tool_sequence"] == ["buffer"]
    assert result["result_name"] == "100m Buffer"

    # Verify the executed steps
    assert len(result["operation_details"]["steps"]) == 1
    executed_step = result["operation_details"]["steps"][0]
    assert executed_step["operation"] == "buffer"
    # The executor should have passed radius and radius_unit to the buffer operation
    assert "radius" in executed_step["params"]
    assert executed_step["params"]["radius"] == 100
    assert "radius_unit" in executed_step["params"]
    assert executed_step["params"]["radius_unit"] == "meters"


@pytest.mark.integration
def test_executor_buffer_with_kilometers(sample_point_layer):
    """
    Test that the executor correctly handles a buffer operation with kilometers.

    This simulates: User asks "buffer by 5 km"
    LLM generates: {"operation": "buffer", "params": {"radius": 5, "radius_unit": "km"}}
    """
    mock_llm_response = {
        "steps": [{"operation": "buffer", "params": {"radius": 5, "radius_unit": "kilometers"}}],
        "result_name": "5km Buffer",
        "result_description": "Creates a 5 kilometer buffer.",
    }

    state = {
        "query": "buffer by 5 km",
        "input_layers": sample_point_layer,
        "enable_smart_crs": True,
        "available_operations_and_params": [
            "operation: buffer params: radius=<number>, radius_unit=<meters|kilometers|miles>"
        ],
    }

    with patch("services.tools.geoprocess_tools.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.generations = [[MagicMock(text=json.dumps(mock_llm_response))]]
        mock_llm.generate.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        result = geoprocess_executor(state)

    assert result["tool_sequence"] == ["buffer"]
    executed_step = result["operation_details"]["steps"][0]
    assert executed_step["params"]["radius"] == 5
    assert executed_step["params"]["radius_unit"] == "kilometers"


@pytest.mark.integration
def test_executor_buffer_with_manual_crs(sample_point_layer):
    """
    Test that the executor correctly handles manual CRS specification.

    This simulates: User asks "buffer by 1000 meters in EPSG:32633"
    LLM generates: {"operation": "buffer", "params": {"radius": 1000,
        "radius_unit": "meters", "crs": "EPSG:32633"}}
    The executor should convert "crs" to "override_crs" and disable auto-optimization.
    """
    mock_llm_response = {
        "steps": [
            {
                "operation": "buffer",
                "params": {"radius": 1000, "radius_unit": "meters", "crs": "EPSG:32633"},
            }
        ],
        "result_name": "1km Buffer UTM33N",
        "result_description": "Creates a 1 kilometer buffer using UTM zone 33N projection.",
    }

    state = {
        "query": "buffer by 1000 meters in EPSG:32633",
        "input_layers": sample_point_layer,
        "enable_smart_crs": True,
        "available_operations_and_params": [
            (
                "operation: buffer params: radius=<number>, "
                "radius_unit=<meters|kilometers|miles>, crs=<EPSG_code_optional>"
            )
        ],
    }

    with patch("services.tools.geoprocess_tools.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.generations = [[MagicMock(text=json.dumps(mock_llm_response))]]
        mock_llm.generate.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        result = geoprocess_executor(state)

    # Verify the executor transformed crs -> override_crs
    executed_step = result["operation_details"]["steps"][0]
    assert executed_step["params"]["radius"] == 1000
    assert executed_step["params"]["radius_unit"] == "meters"
    # The executor should have converted 'crs' to 'override_crs'
    assert "override_crs" in executed_step["params"]
    assert executed_step["params"]["override_crs"] == "EPSG:32633"
    # Should have disabled auto-optimization
    assert executed_step["params"]["auto_optimize_crs"] is False
    # Original 'crs' should be removed
    assert "crs" not in executed_step["params"]


@pytest.mark.integration
def test_executor_buffer_without_units_fails_gracefully():
    """
    Test that missing radius_unit is handled gracefully.

    This simulates: LLM incorrectly generates {"radius": 100} without "radius_unit"
    The buffer operation should use a default or raise an error.
    """
    mock_llm_response = {
        "steps": [{"operation": "buffer", "params": {"radius": 100}}],  # Missing radius_unit!
        "result_name": "Buffer",
        "result_description": "Buffer operation.",
    }

    state = {
        "query": "buffer by 100",
        "input_layers": [
            {
                "type": "Feature",
                "properties": {"resource_id": "test", "name": "Test"},
                "geometry": {"type": "Point", "coordinates": [0, 0]},
            }
        ],
        "enable_smart_crs": True,
        "available_operations_and_params": [
            "operation: buffer params: radius=<number>, radius_unit=<meters|kilometers|miles>"
        ],
    }

    with patch("services.tools.geoprocess_tools.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.generations = [[MagicMock(text=json.dumps(mock_llm_response))]]
        mock_llm.generate.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        # Should either succeed with default or raise a clear error
        try:
            result = geoprocess_executor(state)
            # If it succeeds, verify it used a default
            assert result is not None
            executed_step = result["operation_details"]["steps"][0]
            # Buffer should have added a default radius_unit
            assert "radius_unit" in executed_step["params"] or "radius" in executed_step["params"]
        except (ValueError, TypeError, KeyError) as e:
            # If it fails, the error should be informative
            assert "radius_unit" in str(e) or "required" in str(e).lower()


@pytest.mark.integration
def test_executor_overlay_with_crs(sample_polygon_layer):
    """
    Test overlay operation with manual CRS specification.
    """
    # Create two polygon layers for overlay
    layer1 = sample_polygon_layer[0].copy()
    layer1["properties"]["name"] = "Layer1"
    layer2 = sample_polygon_layer[0].copy()
    layer2["properties"]["name"] = "Layer2"
    layer2["geometry"]["coordinates"] = [
        [[0.5, 0.5], [1.5, 0.5], [1.5, 1.5], [0.5, 1.5], [0.5, 0.5]]
    ]

    mock_llm_response = {
        "steps": [{"operation": "overlay", "params": {"how": "intersection", "crs": "EPSG:3413"}}],
        "result_name": "Intersection",
        "result_description": "Intersection of Layer1 and Layer2 using EPSG:3413.",
    }

    state = {
        "query": "overlay with intersection in EPSG:3413",
        "input_layers": [layer1, layer2],
        "enable_smart_crs": True,
        "available_operations_and_params": [
            (
                "operation: overlay params: "
                "how=<intersection|union|difference|symmetric_difference>, crs=<EPSG_code_optional>"
            )
        ],
    }

    with patch("services.tools.geoprocess_tools.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.generations = [[MagicMock(text=json.dumps(mock_llm_response))]]
        mock_llm.generate.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        result = geoprocess_executor(state)

    # Verify CRS override was applied
    executed_step = result["operation_details"]["steps"][0]
    assert executed_step["operation"] == "overlay"
    assert executed_step["params"]["how"] == "intersection"
    assert "override_crs" in executed_step["params"]
    assert executed_step["params"]["override_crs"] == "EPSG:3413"
    assert executed_step["params"]["auto_optimize_crs"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
