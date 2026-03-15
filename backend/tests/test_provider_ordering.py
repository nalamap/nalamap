"""Tests for provider ordering based on environment variables."""

import os
from unittest.mock import patch

import pytest


class TestProviderOrdering:
    """Test suite for LLM provider ordering based on DEFAULT_LLM_PROVIDER."""

    @pytest.mark.unit
    def test_default_llm_provider_puts_provider_first(self):
        """Test that DEFAULT_LLM_PROVIDER puts specified provider first in dict."""
        with patch.dict(os.environ, {"DEFAULT_LLM_PROVIDER": "azure"}, clear=False):
            from services.ai.provider_interface import get_all_providers

            providers = get_all_providers()
            provider_names = list(providers.keys())

            # Azure should be first
            assert provider_names[0] == "azure"

    @pytest.mark.unit
    def test_llm_provider_fallback(self):
        """Test that LLM_PROVIDER is used when DEFAULT_LLM_PROVIDER not set."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "google"}, clear=True):
            # Ensure DEFAULT_LLM_PROVIDER is not set
            os.environ.pop("DEFAULT_LLM_PROVIDER", None)

            from services.ai.provider_interface import get_all_providers

            providers = get_all_providers()
            provider_names = list(providers.keys())

            # Google should be first
            assert provider_names[0] == "google"

    @pytest.mark.unit
    def test_no_env_var_uses_default_order(self):
        """Test that without env vars, providers use their natural order."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove both env vars
            os.environ.pop("DEFAULT_LLM_PROVIDER", None)
            os.environ.pop("LLM_PROVIDER", None)

            from services.ai.provider_interface import get_all_providers

            providers = get_all_providers()
            provider_names = list(providers.keys())

            # Should be in natural order (openai first in code)
            assert provider_names[0] == "openai"

    @pytest.mark.unit
    def test_invalid_provider_ignored(self):
        """Test that invalid provider name doesn't break ordering."""
        with patch.dict(os.environ, {"DEFAULT_LLM_PROVIDER": "nonexistent"}, clear=False):
            from services.ai.provider_interface import get_all_providers

            providers = get_all_providers()
            provider_names = list(providers.keys())

            # Should fall back to natural order
            assert provider_names[0] == "openai"
            assert "nonexistent" not in provider_names

    @pytest.mark.unit
    def test_case_insensitive_provider_name(self):
        """Test that provider names are case-insensitive."""
        with patch.dict(os.environ, {"DEFAULT_LLM_PROVIDER": "AZURE"}, clear=False):
            from services.ai.provider_interface import get_all_providers

            providers = get_all_providers()
            provider_names = list(providers.keys())

            # Azure should be first (case-insensitive match)
            assert provider_names[0] == "azure"

    @pytest.mark.unit
    def test_all_providers_still_included(self):
        """Test that reordering doesn't exclude any providers."""
        with patch.dict(os.environ, {"DEFAULT_LLM_PROVIDER": "mistral"}, clear=False):
            from services.ai.provider_interface import get_all_providers

            providers = get_all_providers()
            provider_names = list(providers.keys())

            # All providers should be present
            expected_providers = {
                "openai",
                "azure",
                "google",
                "mistral",
                "deepseek",
                "anthropic",
                "moonshot",
                "xai",
            }
            assert set(provider_names) == expected_providers

            # Mistral should be first
            assert provider_names[0] == "mistral"
