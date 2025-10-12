"""Tests for max_tokens validation in LLM configuration."""

import os
import pytest
from services.ai.llm_config import _validate_max_tokens, get_llm_for_provider


class TestMaxTokensValidation:
    """Test max_tokens validation logic."""

    def test_validate_max_tokens_within_limit(self):
        """Test that valid max_tokens within model limit is accepted."""
        # OpenAI gpt-5-mini has max_tokens=100000
        result = _validate_max_tokens("openai", 5000, "gpt-5-mini")
        assert result == 5000

    def test_validate_max_tokens_exceeds_limit(self):
        """Test clamping when max_tokens exceeds model's limit"""
        # gpt-5-mini has max_tokens=128000
        result = _validate_max_tokens("openai", 200000, "gpt-5-mini")
        assert result == 128000  # Should be clamped to model's limit

    def test_validate_max_tokens_zero_uses_model_default(self):
        """Test that zero or negative max_tokens uses model's max_tokens"""
        # gpt-5-mini has max_tokens=128000
        result = _validate_max_tokens("openai", 0, "gpt-5-mini")
        assert result == 128000  # Should use model's max_tokens

        result = _validate_max_tokens("openai", -100, "gpt-5-mini")
        assert result == 128000  # Should use model's max_tokens

    def test_validate_max_tokens_no_model_name_uses_first_model(self):
        """Test that validation works when no model name is specified."""
        # Should use first available model's limit
        result = _validate_max_tokens("openai", 5000, None)
        assert result == 5000  # Within reasonable limits

    def test_validate_max_tokens_unknown_provider_returns_original(self):
        """Test that unknown provider returns original max_tokens."""
        result = _validate_max_tokens("unknown_provider", 5000, None)
        assert result == 5000  # Should return original value

    def test_validate_max_tokens_google_gemini(self):
        """Test validation with Google Gemini models."""
        # Gemini 1.5 Flash has max_tokens=8192
        result = _validate_max_tokens("google", 5000, "gemini-1.5-flash")
        assert result == 5000

        # Exceeding limit
        result = _validate_max_tokens("google", 20000, "gemini-1.5-flash")
        assert result == 8192  # Should be clamped

    def test_validate_max_tokens_deepseek(self):
        """Test validation with DeepSeek models."""
        # DeepSeek chat has max_tokens=4096
        result = _validate_max_tokens("deepseek", 3000, "deepseek-chat")
        assert result == 3000

        # Exceeding limit
        result = _validate_max_tokens("deepseek", 10000, "deepseek-chat")
        assert result == 4096  # Should be clamped


class TestGetLLMWithValidation:
    """Test that get_llm_for_provider applies validation."""

    def test_get_llm_for_provider_validates_max_tokens(self):
        """Test that get_llm_for_provider validates and clamps max_tokens."""
        # This should not raise an error even with excessive max_tokens
        llm = get_llm_for_provider("openai", max_tokens=999999, model_name="gpt-5-mini")
        assert llm is not None

        # Verify it's using OpenAI
        assert llm.__class__.__name__ == "ChatOpenAI"

    def test_get_llm_for_provider_with_valid_max_tokens(self):
        """Test that valid max_tokens passes through unchanged."""
        llm = get_llm_for_provider("openai", max_tokens=5000, model_name="gpt-5-mini")
        assert llm is not None
        assert llm.max_tokens == 5000

    def test_get_llm_for_provider_clamps_excessive_tokens(self):
        """Test that get_llm_for_provider clamps excessive max_tokens"""
        # gpt-4o-mini has max_tokens=16384
        llm = get_llm_for_provider("openai", max_tokens=50000, model_name="gpt-4o-mini")
        assert llm.max_tokens == 16384

    def test_get_llm_for_provider_handles_zero_tokens(self):
        """Test that zero max_tokens uses model's default."""
        llm = get_llm_for_provider("openai", max_tokens=0, model_name="gpt-5-mini")
        assert llm is not None
        # Should use model's max_tokens (gpt-5-mini has max_tokens=128000)
        assert llm.max_tokens == 128000

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_VERSION") or not os.getenv("AZURE_OPENAI_ENDPOINT"),
        reason="Azure environment variables not configured",
    )
    def test_get_llm_for_provider_azure(self):
        """Test validation works with Azure provider."""
        # Azure has max_tokens=6000 by default
        llm = get_llm_for_provider("azure", max_tokens=5000)
        assert llm is not None

        # Exceeding Azure's limit
        llm = get_llm_for_provider("azure", max_tokens=20000)
        assert llm is not None
        assert llm.max_tokens == 6000  # Should be clamped to Azure's limit
