"""Tests for Azure AI provider with multi-model configuration."""

import json
from unittest.mock import patch

from services.ai import azureai


class TestAzureAIConfiguration:
    """Test Azure AI configuration parsing and model creation."""

    def test_single_deployment_legacy_format(self, monkeypatch):
        """Test legacy single deployment configuration."""
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
        monkeypatch.delenv("AZURE_MODELS_CONFIG", raising=False)

        assert azureai.is_available()
        models = azureai.get_available_models()

        assert len(models) == 1
        assert models[0].name == "gpt-4o"
        assert models[0].max_tokens == 6000
        assert models[0].context_window == 128000
        assert models[0].supports_tools is True

    def test_multi_model_config_parsing(self, monkeypatch):
        """Test parsing AZURE_MODELS_CONFIG JSON array."""
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")

        config = [
            {
                "deployment": "gpt-4o",
                "model_name": "gpt-4o",
                "max_tokens": 4096,
                "context_window": 128000,
                "input_cost": 5.00,
                "output_cost": 15.00,
                "cache_cost": 1.25,
                "description": "GPT-4o test",
                "supports_tools": True,
                "supports_vision": True,
                "parallel_tools": True,
                "tool_quality": "excellent",
                "reasoning": "expert",
            },
            {
                "deployment": "llama-3-2-90b",
                "model_name": "meta-llama-3.2-90b",
                "max_tokens": 4096,
                "input_cost": 0.80,
                "output_cost": 0.80,
            },
        ]

        monkeypatch.setenv("AZURE_MODELS_CONFIG", json.dumps(config))

        models = azureai.get_available_models()

        assert len(models) == 2

        # Check first model (full config)
        assert models[0].name == "gpt-4o"
        assert models[0].max_tokens == 4096
        assert models[0].context_window == 128000
        assert models[0].input_cost_per_million == 5.00
        assert models[0].output_cost_per_million == 15.00
        assert models[0].cache_cost_per_million == 1.25
        assert models[0].supports_tools is True
        assert models[0].supports_vision is True
        assert models[0].supports_parallel_tool_calls is True
        assert models[0].tool_calling_quality == "excellent"
        assert models[0].reasoning_capability == "expert"

        # Check second model (minimal config with defaults)
        assert models[1].name == "meta-llama-3.2-90b"
        assert models[1].max_tokens == 4096
        assert models[1].context_window == 128000  # default
        assert models[1].supports_tools is True  # default
        assert models[1].tool_calling_quality == "good"  # default
        assert models[1].reasoning_capability == "advanced"  # default

    def test_invalid_json_config(self, monkeypatch):
        """Test that invalid JSON in AZURE_MODELS_CONFIG falls back gracefully."""
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
        monkeypatch.setenv("AZURE_MODELS_CONFIG", "invalid json {")

        # Should fall back to single deployment
        models = azureai.get_available_models()
        assert len(models) == 1
        assert models[0].name == "gpt-4o"

    def test_non_array_json_config(self, monkeypatch):
        """Test that non-array JSON is rejected."""
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
        monkeypatch.setenv("AZURE_MODELS_CONFIG", '{"deployment": "test"}')

        # Should fall back to single deployment
        models = azureai.get_available_models()
        assert len(models) == 1
        assert models[0].name == "gpt-4o"

    def test_azure_ai_foundry_models(self, monkeypatch):
        """Test configuration for Azure AI Foundry models (Meta, DeepSeek, etc.)."""
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")

        config = [
            {
                "deployment": "llama-3-2-90b",
                "model_name": "meta-llama-3.2-90b-instruct",
                "max_tokens": 4096,
                "context_window": 128000,
                "input_cost": 0.80,
                "output_cost": 0.80,
                "description": "Meta Llama 3.2 90B",
                "supports_tools": True,
                "parallel_tools": True,
                "tool_quality": "good",
                "reasoning": "advanced",
            },
            {
                "deployment": "deepseek-coder",
                "model_name": "deepseek-coder-v2",
                "max_tokens": 8192,
                "context_window": 128000,
                "input_cost": 0.14,
                "output_cost": 0.28,
                "description": "DeepSeek Coder V2",
                "supports_tools": True,
                "tool_quality": "basic",
                "reasoning": "intermediate",
            },
        ]

        monkeypatch.setenv("AZURE_MODELS_CONFIG", json.dumps(config))

        models = azureai.get_available_models()

        assert len(models) == 2
        assert models[0].name == "meta-llama-3.2-90b-instruct"
        assert models[1].name == "deepseek-coder-v2"

    def test_is_available_with_models_config(self, monkeypatch):
        """Test is_available() returns True with AZURE_MODELS_CONFIG."""
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
        monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT", raising=False)
        monkeypatch.setenv("AZURE_MODELS_CONFIG", '[{"deployment": "test"}]')

        assert azureai.is_available()

    def test_is_available_missing_credentials(self, monkeypatch):
        """Test is_available() returns False when credentials missing."""
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)

        assert not azureai.is_available()

    @patch("services.ai.azureai.AzureChatOpenAI")
    def test_get_llm_with_model_name(self, mock_azure_chat, monkeypatch):
        """Test get_llm() selects correct deployment when model_name provided."""
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-02-01")

        config = [
            {"deployment": "gpt-4o-deploy", "model_name": "gpt-4o"},
            {"deployment": "llama-deploy", "model_name": "meta-llama-3.2-90b"},
        ]

        monkeypatch.setenv("AZURE_MODELS_CONFIG", json.dumps(config))

        azureai.get_llm(max_tokens=4000, model_name="meta-llama-3.2-90b")

        # Verify correct deployment was used
        mock_azure_chat.assert_called_once()
        call_kwargs = mock_azure_chat.call_args[1]
        assert call_kwargs["azure_deployment"] == "llama-deploy"
        assert call_kwargs["max_tokens"] == 4000

    @patch("services.ai.azureai.AzureChatOpenAI")
    def test_get_llm_fallback_to_default(self, mock_azure_chat, monkeypatch):
        """Test get_llm() falls back to default deployment when model not found."""
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "default-deployment")

        config = [{"deployment": "gpt-4o-deploy", "model_name": "gpt-4o"}]

        monkeypatch.setenv("AZURE_MODELS_CONFIG", json.dumps(config))

        azureai.get_llm(max_tokens=4000, model_name="unknown-model")

        # Should fall back to AZURE_OPENAI_DEPLOYMENT
        mock_azure_chat.assert_called_once()
        call_kwargs = mock_azure_chat.call_args[1]
        assert call_kwargs["azure_deployment"] == "default-deployment"


class TestAzureModelCapabilities:
    """Test Azure model capability configurations."""

    def test_vision_model_configuration(self, monkeypatch):
        """Test vision-enabled model configuration."""
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")

        config = [
            {
                "deployment": "gpt-4o-vision",
                "model_name": "gpt-4o",
                "supports_vision": True,
                "supports_tools": True,
            }
        ]

        monkeypatch.setenv("AZURE_MODELS_CONFIG", json.dumps(config))

        models = azureai.get_available_models()
        assert models[0].supports_vision is True
        assert models[0].supports_tools is True

    def test_tool_quality_levels(self, monkeypatch):
        """Test different tool calling quality levels."""
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")

        config = [
            {
                "deployment": "excellent-tools",
                "model_name": "model-1",
                "tool_quality": "excellent",
            },
            {"deployment": "good-tools", "model_name": "model-2", "tool_quality": "good"},
            {
                "deployment": "basic-tools",
                "model_name": "model-3",
                "tool_quality": "basic",
            },
            {"deployment": "no-tools", "model_name": "model-4", "tool_quality": "none"},
        ]

        monkeypatch.setenv("AZURE_MODELS_CONFIG", json.dumps(config))

        models = azureai.get_available_models()
        assert models[0].tool_calling_quality == "excellent"
        assert models[1].tool_calling_quality == "good"
        assert models[2].tool_calling_quality == "basic"
        assert models[3].tool_calling_quality == "none"

    def test_reasoning_capability_levels(self, monkeypatch):
        """Test different reasoning capability levels."""
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")

        config = [
            {"deployment": "expert", "model_name": "model-1", "reasoning": "expert"},
            {"deployment": "advanced", "model_name": "model-2", "reasoning": "advanced"},
            {
                "deployment": "intermediate",
                "model_name": "model-3",
                "reasoning": "intermediate",
            },
            {"deployment": "basic", "model_name": "model-4", "reasoning": "basic"},
        ]

        monkeypatch.setenv("AZURE_MODELS_CONFIG", json.dumps(config))

        models = azureai.get_available_models()
        assert models[0].reasoning_capability == "expert"
        assert models[1].reasoning_capability == "advanced"
        assert models[2].reasoning_capability == "intermediate"
        assert models[3].reasoning_capability == "basic"
