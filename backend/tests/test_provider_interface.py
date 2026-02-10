"""Tests for LLM provider interface and model discovery."""

import os
from unittest.mock import patch

import pytest

from models.model_info import ModelInfo, ProviderInfo
from services.ai.provider_interface import get_all_providers, get_provider_by_name


def _is_provider_available(provider_name: str) -> bool:
    """Check if a provider is available (dependencies installed and configured)."""
    try:
        provider_info = get_provider_by_name(provider_name)
        return provider_info.available
    except (ValueError, Exception):
        return False


class TestProviderAvailability:
    """Test provider availability checks."""

    def test_openai_available_with_api_key(self):
        """Test that OpenAI is available when API key is set."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}):
            from services.ai import openai

            assert openai.is_available() is True

    def test_openai_unavailable_without_api_key(self):
        """Test that OpenAI is unavailable without API key."""
        with patch.dict(os.environ, {}, clear=True):
            from services.ai import openai

            assert openai.is_available() is False

    def test_azure_available_with_credentials(self):
        """Test that Azure is available when all credentials are set."""
        with patch.dict(
            os.environ,
            {
                "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
                "AZURE_OPENAI_API_KEY": "test-key",
                "AZURE_OPENAI_DEPLOYMENT": "test-deployment",
            },
        ):
            from services.ai import azureai

            assert azureai.is_available() is True

    def test_azure_unavailable_without_credentials(self):
        """Test that Azure is unavailable without credentials."""
        with patch.dict(os.environ, {}, clear=True):
            from services.ai import azureai

            assert azureai.is_available() is False


class TestModelListing:
    """Test model listing for each provider."""

    def test_openai_models_have_required_fields(self):
        """Test that OpenAI models have all required fields."""
        from services.ai import openai

        models = openai.get_available_models()

        assert len(models) > 0, "OpenAI should return at least one model"

        for model in models:
            assert isinstance(model, ModelInfo)
            assert model.name, "Model must have a name"
            assert model.max_tokens > 0, "Model must have positive max_tokens"
            # Most models should have cost info (some might not)
            assert isinstance(model.input_cost_per_million, (float, type(None)))
            assert isinstance(model.output_cost_per_million, (float, type(None)))

    def test_openai_models_include_expected_models(self):
        """Test that OpenAI returns expected models."""
        from services.ai import openai

        models = openai.get_available_models()
        model_names = [m.name for m in models]

        # Check for key models mentioned in requirements
        expected_models = [
            "gpt-5",
            "gpt-5.5-mini",
            "gpt-4.1",
            "gpt-4o",
            "gpt-4o-mini-realtime-preview",
        ]

        for expected in expected_models:
            assert expected in model_names, f"Expected model {expected} not found"

    @pytest.mark.skipif(
        not _is_provider_available("google"),
        reason="Google Gemini provider not available (missing langchain_google_genai)",
    )
    def test_google_models_have_required_fields(self):
        """Test that Google models have all required fields."""
        from services.ai import google_genai

        models = google_genai.get_available_models()

        assert len(models) > 0, "Google should return at least one model"

        for model in models:
            assert isinstance(model, ModelInfo)
            assert model.name, "Model must have a name"
            assert model.max_tokens > 0, "Model must have positive max_tokens"

    @pytest.mark.skipif(
        not _is_provider_available("mistral"),
        reason="Mistral AI provider not available (missing langchain_mistralai)",
    )
    def test_mistral_models_have_required_fields(self):
        """Test that Mistral models have all required fields."""
        from services.ai import mistralai

        models = mistralai.get_available_models()

        assert len(models) > 0, "Mistral should return at least one model"

        for model in models:
            assert isinstance(model, ModelInfo)
            assert model.name, "Model must have a name"
            assert model.max_tokens > 0, "Model must have positive max_tokens"

    def test_deepseek_models_have_required_fields(self):
        """Test that DeepSeek models have all required fields."""
        from services.ai import deepseek

        models = deepseek.get_available_models()

        assert len(models) > 0, "DeepSeek should return at least one model"

        for model in models:
            assert isinstance(model, ModelInfo)
            assert model.name, "Model must have a name"
            assert model.max_tokens > 0, "Model must have positive max_tokens"


class TestProviderInterface:
    """Test the unified provider interface."""

    def test_get_all_providers_returns_all_providers(self):
        """Test that get_all_providers returns all expected providers."""
        providers = get_all_providers()

        expected_providers = ["openai", "azure", "google", "mistral", "deepseek"]

        for provider_name in expected_providers:
            assert provider_name in providers, f"Provider {provider_name} not found"
            assert isinstance(providers[provider_name], ProviderInfo)

    def test_get_all_providers_includes_availability(self):
        """Test that each provider includes availability status."""
        providers = get_all_providers()

        for provider_name, provider_info in providers.items():
            assert isinstance(provider_info.available, bool)
            assert provider_info.display_name, "Provider must have display name"

            if provider_info.available:
                assert (
                    len(provider_info.models) > 0
                ), f"Available provider {provider_name} should have models"
            else:
                assert (
                    provider_info.error_message
                ), f"Unavailable provider {provider_name} should have error message"

    def test_get_provider_by_name_openai(self):
        """Test getting OpenAI provider by name."""
        provider = get_provider_by_name("openai")

        assert provider.name == "openai"
        assert provider.display_name == "OpenAI"

    def test_get_provider_by_name_invalid_raises(self):
        """Test that invalid provider name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider_by_name("invalid_provider")


class TestModelCosts:
    """Test model cost information."""

    def test_openai_costs_are_reasonable(self):
        """Test that OpenAI model costs are in reasonable range."""
        from services.ai import openai

        models = openai.get_available_models()

        for model in models:
            if model.input_cost_per_million is not None:
                # Costs should be between $0 and $100 per million tokens
                assert 0 <= model.input_cost_per_million <= 100
            if model.output_cost_per_million is not None:
                assert 0 <= model.output_cost_per_million <= 100
            if model.cache_cost_per_million is not None:
                assert 0 <= model.cache_cost_per_million <= 150

    def test_model_costs_comparison(self):
        """Test that nano models are cheaper than mini, which are cheaper than full models."""
        from services.ai import openai

        models = openai.get_available_models()
        model_dict = {m.name: m for m in models}

        # Check gpt-5 family pricing
        if all(k in model_dict for k in ["gpt-5-nano", "gpt-5-mini", "gpt-5"]):
            nano = model_dict["gpt-5-nano"]
            mini = model_dict["gpt-5-mini"]
            full = model_dict["gpt-5"]

            if all(m.input_cost_per_million is not None for m in [nano, mini, full]):
                assert nano.input_cost_per_million < mini.input_cost_per_million  # type: ignore
                assert mini.input_cost_per_million < full.input_cost_per_million  # type: ignore
