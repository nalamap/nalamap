"""Integration-style tests for the revamped attribute_tool3."""

import json
from typing import Dict
from unittest.mock import patch

import geopandas as gpd
import pandas as pd
import pytest
from langchain_core.messages import HumanMessage
from shapely.geometry import Point

from models.geodata import DataOrigin, DataType, GeoDataObject
from models.states import GeoDataAgentState
from services.default_agent_settings import DEFAULT_AVAILABLE_TOOLS
from services.single_agent import tools as SINGLE_AGENT_TOOLS
from services.tools.attribute_tool3 import attribute_tool3


@pytest.fixture()
def sample_layer() -> GeoDataObject:
    return GeoDataObject(
        id="layer-1",
        data_source_id="test",
        data_type=DataType.GEOJSON,
        data_origin=DataOrigin.TOOL,
        data_source="Test",
        data_link="https://example.com/data.geojson",
        name="test_layer",
        title="Test Layer",
    )


@pytest.fixture()
def sample_state(sample_layer: GeoDataObject) -> GeoDataAgentState:
    state = GeoDataAgentState()
    state["messages"] = [HumanMessage(content="Please provide an overview of the layer")]
    state["geodata_layers"] = [sample_layer]
    state["geodata_results"] = []
    state["geodata_last_results"] = []
    state["results_title"] = ""
    state["options"] = {}
    state["remaining_steps"] = 5
    return state


@pytest.fixture()
def sample_gdf() -> gpd.GeoDataFrame:
    df = pd.DataFrame(
        {
            "name": ["Feature A", "Feature B", "Feature C"],
            "value": [10, 25, 5],
            "category": ["alpha", "beta", "alpha"],
        }
    )
    return gpd.GeoDataFrame(df, geometry=[Point(0, 0), Point(1, 1), Point(2, 2)], crs="EPSG:4326")


def _invoke_tool(state: GeoDataAgentState, extra_args: Dict[str, object]) -> Dict[str, object]:
    call_id = extra_args.get("tool_call_id", "call-1")
    call = {
        "id": call_id,
        "tool_call_id": call_id,
        "type": "tool_call",
        "name": "attribute_tool3",
        "args": {"state": state, **extra_args},
    }
    command = attribute_tool3.invoke(call)
    message = command.update["messages"][0]
    return json.loads(message.content)


def test_returns_error_when_no_layers(sample_state: GeoDataAgentState):
    sample_state["geodata_layers"] = []
    payload = _invoke_tool(sample_state, {"tool_call_id": "call-1"})

    assert payload["status"] == "error"
    assert "No geodata layers" in payload["message"]


def test_list_fields_returns_schema(sample_state: GeoDataAgentState, sample_gdf: gpd.GeoDataFrame):
    with patch("services.tools.attribute_tool3.GeoDataLoader.load", return_value=sample_gdf):
        payload = _invoke_tool(
            sample_state,
            {
                "tool_call_id": "call-2",
                "operation": "list_fields",
                "target_layer_names": [sample_state["geodata_layers"][0].name],
            },
        )

    assert payload["status"] == "success"
    field_names = {field["name"] for field in payload["result"]["fields"]}
    assert {"name", "value", "category", "geometry"}.issubset(field_names)


def test_summarize_numeric_fields(sample_state: GeoDataAgentState, sample_gdf: gpd.GeoDataFrame):
    with patch("services.tools.attribute_tool3.GeoDataLoader.load", return_value=sample_gdf):
        payload = _invoke_tool(
            sample_state,
            {
                "tool_call_id": "call-3",
                "operation": "summarize",
                "params": {"fields": ["value"]},
            },
        )

    assert payload["status"] == "success"
    assert pytest.approx(payload["result"]["value"]["mean"], 0.01) == 13.3333


def test_unique_values_missing_field_is_error(sample_state: GeoDataAgentState, sample_gdf: gpd.GeoDataFrame):
    with patch("services.tools.attribute_tool3.GeoDataLoader.load", return_value=sample_gdf):
        payload = _invoke_tool(
            sample_state,
            {
                "tool_call_id": "call-4",
                "operation": "unique_values",
                "params": {"field": "missing"},
            },
        )

    assert payload["status"] == "error"
    assert payload["details"]["missing_fields"] == ["missing"]


def test_filter_where_creates_new_layer(sample_state: GeoDataAgentState, sample_gdf: gpd.GeoDataFrame, sample_layer: GeoDataObject):
    result_layer = sample_layer.model_copy(update={"id": "filtered", "name": "filtered"})

    with (
        patch("services.tools.attribute_tool3.GeoDataLoader.load", return_value=sample_gdf),
        patch("services.tools.attribute_tool3.ResultWriter.persist", return_value=result_layer) as mock_persist,
    ):
        payload = _invoke_tool(
            sample_state,
            {
                "tool_call_id": "call-5",
                "operation": "filter_where",
                "params": {"where": "value > 15"},
            },
        )

    assert payload["status"] == "success"
    assert payload["result_handling"] == "layer"
    assert payload["result"]["new_layer"]["id"] == "filtered"
    mock_persist.assert_called_once()


def test_filter_where_handles_no_matches(sample_state: GeoDataAgentState, sample_gdf: gpd.GeoDataFrame):
    with patch("services.tools.attribute_tool3.GeoDataLoader.load", return_value=sample_gdf):
        payload = _invoke_tool(
            sample_state,
            {
                "tool_call_id": "call-6",
                "operation": "filter_where",
                "params": {"where": "value > 100"},
            },
        )

    assert payload["status"] == "success"
    assert payload["result"]["feature_count"] == 0
    assert payload["result_handling"] == "chat"


def test_select_fields_can_drop_geometry(sample_state: GeoDataAgentState, sample_gdf: gpd.GeoDataFrame, sample_layer: GeoDataObject):
    result_layer = sample_layer.model_copy(update={"id": "selection", "name": "selection"})

    with (
        patch("services.tools.attribute_tool3.GeoDataLoader.load", return_value=sample_gdf),
        patch("services.tools.attribute_tool3.ResultWriter.persist", return_value=result_layer),
    ):
        payload = _invoke_tool(
            sample_state,
            {
                "tool_call_id": "call-7",
                "operation": "select_fields",
                "params": {"include": ["name", "value"], "keep_geometry": False},
            },
        )

    assert payload["status"] == "success"
    assert payload["result"]["new_layer"]["name"] == "selection"
    assert payload["result_handling"] == "layer"


def test_sort_by_multiple_fields(sample_state: GeoDataAgentState, sample_gdf: gpd.GeoDataFrame, sample_layer: GeoDataObject):
    result_layer = sample_layer.model_copy(update={"id": "sorted", "name": "sorted"})

    with (
        patch("services.tools.attribute_tool3.GeoDataLoader.load", return_value=sample_gdf),
        patch("services.tools.attribute_tool3.ResultWriter.persist", return_value=result_layer),
    ):
        payload = _invoke_tool(
            sample_state,
            {
                "tool_call_id": "call-8",
                "operation": "sort_by",
                "params": {"fields": [["category", "asc"], ["value", "desc"]]},
            },
        )

    assert payload["status"] == "success"
    assert payload["result"]["new_layer"]["id"] == "sorted"
    assert payload["result"]["orders"] == ["asc", "desc"]


def test_describe_dataset_includes_recommendations(sample_state: GeoDataAgentState, sample_gdf: gpd.GeoDataFrame):
    with patch("services.tools.attribute_tool3.GeoDataLoader.load", return_value=sample_gdf):
        payload = _invoke_tool(sample_state, {"tool_call_id": "call-9", "operation": "describe_dataset"})

    assert payload["status"] == "success"
    assert payload["result"]["recommended_actions"]
    assert payload["result"]["sample_records"]


def test_get_attribute_values_with_row_filter(sample_state: GeoDataAgentState, sample_gdf: gpd.GeoDataFrame):
    with patch("services.tools.attribute_tool3.GeoDataLoader.load", return_value=sample_gdf):
        payload = _invoke_tool(
            sample_state,
            {
                "tool_call_id": "call-10",
                "operation": "get_attribute_values",
                "params": {"columns": ["name", "value"], "row_filter": "value >= 10", "limit": 2},
            },
        )

    assert payload["status"] == "success"
    assert payload["result"]["columns"] == ["name", "value"]
    assert payload["result"]["row_count"] == 2
    assert len(payload["result"]["rows"]) <= 2


def test_planner_is_used_when_operation_missing(sample_state: GeoDataAgentState, sample_gdf: gpd.GeoDataFrame):
    sample_state["messages"] = [HumanMessage(content="Give me a summary of the dataset")]
    with patch("services.tools.attribute_tool3.GeoDataLoader.load", return_value=sample_gdf):
        payload = _invoke_tool(sample_state, {"tool_call_id": "call-11"})

    assert payload["status"] == "success"
    assert payload["operation"] == "summarize"


def test_tool_is_registered_by_default():
    assert "attribute_tool3" in DEFAULT_AVAILABLE_TOOLS
    tool_names = {tool.name for tool in SINGLE_AGENT_TOOLS}
    assert "attribute_tool3" in tool_names
