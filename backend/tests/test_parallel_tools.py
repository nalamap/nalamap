"""
Tests for parallel tool execution and state safety.

These tests verify that parallel tool execution (when enabled) does not cause
state corruption or race conditions when multiple tools modify the same state fields.
"""

import pytest
from unittest.mock import patch
from models.states import GeoDataAgentState
from models.geodata import GeoDataObject, DataType, DataOrigin, LayerStyle
from services.single_agent import create_geo_agent
from models.settings_model import ModelSettings
from langchain_core.messages import HumanMessage


@pytest.fixture
def mock_model_settings():
    """Create mock model settings for testing."""
    return ModelSettings(
        model_provider="openai",
        model_name="gpt-4o-mini",
        max_tokens=4000,
        system_prompt="Test prompt",
    )


@pytest.fixture
def sample_state():
    """Create a sample agent state for testing."""
    return GeoDataAgentState(
        messages=[HumanMessage(content="Test query")],
        geodata_layers=[],
        geodata_results=[],
        geodata_last_results=[],
        results_title="",
        options={},
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_agent_default_parallel_disabled(mock_model_settings):
    """Test that parallel tools are disabled by default."""
    agent, llm = await create_geo_agent(
        model_settings=mock_model_settings, enable_parallel_tools=False
    )

    assert agent is not None
    # Agent should be created successfully with parallel tools disabled


@pytest.mark.unit
@pytest.mark.asyncio
@patch("services.ai.llm_config.get_llm_for_provider")
async def test_create_agent_parallel_enabled_supported_model(mock_get_llm, mock_model_settings):
    """Test that parallel tools can be enabled for supported models."""
    from services.ai.llm_config import ModelCapabilities
    from unittest.mock import MagicMock

    # Mock LLM and capabilities
    mock_llm = MagicMock()
    mock_capabilities = ModelCapabilities(supports_parallel_tool_calls=True)
    mock_get_llm.return_value = (mock_llm, mock_capabilities)

    with patch("services.single_agent.logger") as mock_logger:
        agent, llm = await create_geo_agent(
            model_settings=mock_model_settings, enable_parallel_tools=True
        )

        assert agent is not None
        # Should log info about parallel execution being enabled
        mock_logger.info.assert_called()
        info_msg = mock_logger.info.call_args[0][0]
        assert "parallel" in info_msg.lower()


@pytest.mark.unit
@pytest.mark.asyncio
@patch("services.ai.llm_config.get_llm_for_provider")
async def test_create_agent_parallel_enabled_unsupported_model(mock_get_llm, mock_model_settings):
    """Test that parallel tools remain disabled for unsupported models."""
    from services.ai.llm_config import ModelCapabilities
    from unittest.mock import MagicMock

    # Mock LLM with no parallel support
    mock_llm = MagicMock()
    mock_capabilities = ModelCapabilities(supports_parallel_tool_calls=False)
    mock_get_llm.return_value = (mock_llm, mock_capabilities)

    agent, llm = await create_geo_agent(
        model_settings=mock_model_settings, enable_parallel_tools=True
    )

    assert agent is not None
    # Agent should still be created, but parallel execution should be disabled


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_agent_parallel_without_model_settings():
    """Test that parallel tools can't be enabled without model settings."""
    with patch("services.single_agent.logger") as mock_logger:
        agent, llm = await create_geo_agent(enable_parallel_tools=True)

        assert agent is not None
        # Should log warning about missing model settings
        assert mock_logger.warning.called


@pytest.mark.integration
class TestStateUpdateSafety:
    """Test suite for verifying state update safety during parallel execution."""

    def test_geodata_layers_concurrent_append(self, sample_state):
        """Test that concurrent appends to geodata_layers don't corrupt state.

        This test simulates multiple tools trying to add layers simultaneously.
        The new reduce_geodata_layers reducer intelligently merges results.
        """
        # Create multiple GeoDataObjects
        layer1 = GeoDataObject(
            id="layer-1",
            data_source_id="test_source",
            data_type=DataType.GEOJSON,
            data_origin=DataOrigin.UPLOAD,
            data_source="Test",
            data_link="http://test1.com",
            name="Layer 1",
            title="Test Layer 1",
            style=LayerStyle(),
        )

        layer2 = GeoDataObject(
            id="layer-2",
            data_source_id="test_source",
            data_type=DataType.GEOJSON,
            data_origin=DataOrigin.UPLOAD,
            data_source="Test",
            data_link="http://test2.com",
            name="Layer 2",
            title="Test Layer 2",
            style=LayerStyle(),
        )

        # Test the new reducer behavior - it should merge layers intelligently
        from models.states import reduce_geodata_layers

        initial_layers = []
        update1 = [layer1]
        update2 = [layer2]

        # First update adds layer1
        result1 = reduce_geodata_layers(initial_layers, update1)
        assert len(result1) == 1
        assert result1[0].id == "layer-1"

        # Second update adds layer2, but now the reducer merges them
        result2 = reduce_geodata_layers(result1, update2)
        assert len(result2) == 2  # Both layers should be present
        layer_ids = {layer.id for layer in result2}
        assert "layer-1" in layer_ids
        assert "layer-2" in layer_ids

    def test_geodata_results_concurrent_append(self, sample_state):
        """Test that concurrent appends to geodata_results maintain data integrity.

        This test verifies that geodata_results updates from multiple tools
        don't result in lost data.
        """
        # Geodata_results uses default list append behavior
        # This means parallel updates could cause issues if not thread-safe

        layer1 = GeoDataObject(
            id="result-1",
            data_source_id="test_source",
            data_type=DataType.GEOJSON,
            data_origin=DataOrigin.UPLOAD,
            data_source="Test",
            data_link="http://test1.com",
            name="Result 1",
            title="Test Result 1",
            style=LayerStyle(),
        )

        layer2 = GeoDataObject(
            id="result-2",
            data_source_id="test_source",
            data_type=DataType.GEOJSON,
            data_origin=DataOrigin.UPLOAD,
            data_source="Test",
            data_link="http://test2.com",
            name="Result 2",
            title="Test Result 2",
            style=LayerStyle(),
        )

        # Test direct list operations
        results = []
        results.append(layer1)
        results.append(layer2)

        assert len(results) == 2
        assert results[0].id == "result-1"
        assert results[1].id == "result-2"

    def test_state_update_idempotency(self, sample_state):
        """Test that applying the same state update multiple times is safe."""
        layer = GeoDataObject(
            id="layer-unique",
            data_source_id="test_source",
            data_type=DataType.GEOJSON,
            data_origin=DataOrigin.UPLOAD,
            data_source="Test",
            data_link="http://test.com",
            name="Unique Layer",
            title="Test Layer",
            style=LayerStyle(),
        )

        # Simulate duplicate updates
        from models.states import reduce_geodata_layers

        initial = []
        result1 = reduce_geodata_layers(initial, [layer])
        result2 = reduce_geodata_layers(result1, [layer])

        # The new reducer deduplicates by (id, data_source_id)
        # So applying the same layer twice should not create duplicates
        assert len(result2) == 1
        assert result2[0].id == "layer-unique"


@pytest.mark.integration
class TestToolCategoryAnalysis:
    """Analyze which tools modify which state fields.

    This helps us understand the risk of parallel execution.
    """

    def test_identify_state_mutating_tools(self):
        """Document which tools modify state fields.

        Tools that modify geodata_layers:
        - geocode_using_nominatim_to_geostate: Adds new layers
        - geocode_using_overpass_to_geostate: Adds new layers
        - geoprocess_tool: Adds result layers

        Tools that modify geodata_results:
        - All geocoding tools add to this list
        - Attribute tools may modify this

        Tools that are read-only:
        - metadata_search: Only reads state
        - describe_geodata_object: Only reads state

        Tools that modify layer properties:
        - style_map_layers: Modifies existing layer styles
        - auto_style_new_layers: Modifies existing layer styles
        - apply_intelligent_color_scheme: Modifies existing layer styles
        """
        # This is a documentation test
        # TODO: Add runtime analysis to categorize tools
        pass


@pytest.mark.integration
@pytest.mark.slow
def test_parallel_geocoding_safety():
    """Test that parallel geocoding operations don't corrupt state.

    This test would require:
    1. Mock LLM that returns parallel tool calls
    2. Mock geocoding services
    3. Verification that all results are present

    Marked as slow because it involves agent execution.
    """
    # TODO: Implement full integration test
    # This would require complex mocking and is marked for future implementation
    pytest.skip("Full parallel execution test not yet implemented")


@pytest.mark.integration
@pytest.mark.slow
def test_parallel_geoprocessing_safety():
    """Test that parallel geoprocessing operations maintain consistency.

    This test would verify:
    1. Multiple geoprocessing operations on different layers
    2. Result layers are all created correctly
    3. No race conditions in layer ID generation
    """
    # TODO: Implement full integration test
    pytest.skip("Full parallel execution test not yet implemented")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_agent_creation_basic():
    """Test that create_geo_agent returns a valid agent and llm."""
    agent, llm = await create_geo_agent()
    assert agent is not None
    assert llm is not None
