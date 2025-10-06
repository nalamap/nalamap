import json

import pytest
from langchain_core.messages import HumanMessage, ToolMessage

from services.tools import geostate_management
from models.states import GeoDataAgentState


@pytest.fixture
def empty_state():
    state = GeoDataAgentState()
    state["messages"] = []
    state["global_geodata"] = []
    state["geodata_layers"] = []
    state["geodata_last_results"] = []
    return state


def test_set_result_list_returns_matching_entries(empty_state, sample_river_layer, sample_building_layer):
    empty_state["global_geodata"] = [sample_river_layer, sample_building_layer]

    command = geostate_management.set_result_list.func(
        state=empty_state,
        tool_call_id="call-1",
        results_title="Results",
        result_tuples=[[sample_river_layer.id, sample_river_layer.data_source_id]],
    )

    assert sample_river_layer in command.update["geodata_results"]
    tool_message = command.update["messages"][-1]
    assert isinstance(tool_message, ToolMessage)
    assert tool_message.name == "set_result_list"
    assert "Successfully added" in tool_message.content


def test_set_result_list_reports_missing_entries(empty_state, sample_river_layer):
    empty_state["global_geodata"] = [sample_river_layer]

    command = geostate_management.set_result_list.func(
        state=empty_state,
        tool_call_id="call-2",
        results_title="",
        result_tuples=[["missing", "unknown"]],
    )

    tool_message = command.update["messages"][-1]
    assert "not found" in tool_message.content
    assert command.update["geodata_results"] == []


def test_list_global_geodata_returns_expected_structure(empty_state, sample_river_layer):
    empty_state["global_geodata"] = [sample_river_layer]

    result = geostate_management.list_global_geodata.func(state=empty_state)
    assert result == [
        {
            "id": sample_river_layer.id,
            "data_source_id": sample_river_layer.data_source_id,
            "title": sample_river_layer.title,
        }
    ]


def test_describe_geodata_object_returns_exact_match(empty_state, sample_river_layer):
    empty_state["global_geodata"] = [sample_river_layer]

    result = geostate_management.describe_geodata_object.func(
        state=empty_state,
        id=sample_river_layer.id,
        data_source_id=sample_river_layer.data_source_id,
    )
    assert result == [sample_river_layer]


@pytest.mark.parametrize("prioritize_layers", [True, False])
def test_metadata_search_returns_relevant_dataset(
    empty_state,
    sample_river_layer,
    sample_building_layer,
    prioritize_layers,
):
    empty_state["messages"] = [HumanMessage("Describe dataset")]  # base history
    empty_state["geodata_layers"] = [sample_river_layer]
    empty_state["geodata_last_results"] = [sample_building_layer]

    command = geostate_management.metadata_search.func(
        state=empty_state,
        tool_call_id="call-3",
        query="rivers",
        prioritize_layers=prioritize_layers,
    )

    tool_message = command.update["messages"][-1]
    assert tool_message.name == "metadata_search"
    assert "Found" in tool_message.content

    _, payload = tool_message.content.split("\n\n", 1)
    metadata = json.loads(payload)
    assert metadata
    top_entry = metadata[0]
    assert top_entry["name"].lower().startswith("rivers")
    assert top_entry["data_source"] == sample_river_layer.data_source


def test_metadata_search_handles_no_matches(empty_state):
    empty_state["messages"] = []
    command = geostate_management.metadata_search.func(
        state=empty_state,
        tool_call_id="call-4",
        query="unknown",
        prioritize_layers=True,
    )

    tool_message = command.update["messages"][-1]
    assert tool_message.name == "metadata_search"
    assert "No datasets found" in tool_message.content
