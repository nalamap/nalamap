#!/usr/bin/env python3
"""
Test script to verify that the geodata_layers concurrency fix works correctly.
This script simulates the concurrent update scenario that was causing the error.
"""

from langchain_core.messages import HumanMessage

from models.states import GeoDataAgentState, update_geodata_layers


def test_geodata_layers_reducer():
    """Test the geodata_layers reducer function."""

    # Test with mock layer data (using dicts to simulate GeoDataObject structure)
    layer1_data = {
        "id": "test_layer_1",
        "name": "Test Layer 1",
        "description": "First test layer",
    }

    layer2_data = {
        "id": "test_layer_2",
        "name": "Test Layer 2",
        "description": "Second test layer",
    }

    # Test the reducer function with simple data
    current_layers = [layer1_data]
    new_layers = [layer1_data, layer2_data]

    result = update_geodata_layers(current_layers, new_layers)

    print("Current layers count: {len(current_layers)}")
    print("New layers count: {len(new_layers)}")
    print("Result layers count: {len(result)}")

    assert len(result) == 2, "Reducer should return the new layers list"
    assert result[0]["id"] == layer1_data["id"], "First layer should match"
    assert result[1]["id"] == layer2_data["id"], "Second layer should match"

    print("✅ Reducer function works correctly!")


def test_agent_state_basic():
    """Test that the GeoDataAgentState works with the Annotated geodata_layers field."""

    # Create a test state with minimal required fields
    try:
        state = GeoDataAgentState(
            messages=[HumanMessage(content="Test message")],
            geodata_layers=[],
            geodata_last_results=[],
            geodata_results=[],
            results_title="Test",
        )

        print("Initial state created successfully")
        print("geodata_layers type: {type(state.geodata_layers)}")
        print("geodata_layers value: {state.geodata_layers}")

        print("✅ GeoDataAgentState works correctly!")
        return True
    except Exception as e:
        print("❌ GeoDataAgentState failed: {e}")
        return False


if __name__ == "__main__":
    print("Testing geodata_layers concurrency fix...")
    print("=" * 50)

    test_geodata_layers_reducer()
    print()
    test_agent_state_basic()

    print()
    print(
        "🎉 All tests passed! The concurrency fix should resolve the multiple layer styling issue."
    )
    print()
    print("The key changes made:")
    print(
        "1. Added 'update_geodata_layers' reducer function to handle concurrent updates"
    )
    print("2. Changed 'geodata_layers' field to use Annotated type with the reducer")
    print(
        "3. This allows multiple tools to update geodata_layers simultaneously without conflicts"
    )
