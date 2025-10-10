"""Tests for model selection in geo agent."""

import os
from unittest.mock import MagicMock, patch

import pytest

from models.settings_model import ModelSettings
from services.single_agent import create_geo_agent


def _is_google_provider_available() -> bool:
    """Check if Google provider is available."""
    try:
        from services.ai.provider_interface import get_provider_by_name

        provider_info = get_provider_by_name("google")
        return provider_info.available
    except Exception:
        return False


class TestAgentModelSelection:
    """Test that geo agent uses correct model based on settings."""

    @patch("services.single_agent.create_react_agent")
    def test_create_agent_with_openai_model_settings(self, mock_create_react):
        """Test creating agent with specific OpenAI model."""
        # Mock the create_react_agent to avoid actual LangGraph setup
        mock_agent = MagicMock()
        mock_create_react.return_value = mock_agent

        model_settings = ModelSettings(
            model_provider="openai",
            model_name="gpt-5-nano",
            max_tokens=4000,
            system_prompt="Test prompt",
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}):
            agent = create_geo_agent(model_settings=model_settings)

        assert agent is not None
        # Verify that create_react_agent was called
        assert mock_create_react.called

        # Get the call arguments
        call_kwargs = mock_create_react.call_args[1]
        assert call_kwargs["prompt"] == "Test prompt"

    @pytest.mark.skipif(
        not _is_google_provider_available(),
        reason="Google Gemini provider not available (missing langchain_google_genai)",
    )
    @patch("services.single_agent.create_react_agent")
    def test_create_agent_with_google_model_settings(self, mock_create_react):
        """Test creating agent with Google Gemini model."""
        mock_agent = MagicMock()
        mock_create_react.return_value = mock_agent

        model_settings = ModelSettings(
            model_provider="google",
            model_name="gemini-1.5-flash",
            max_tokens=8192,
            system_prompt="",
        )

        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            agent = create_geo_agent(model_settings=model_settings)

        assert agent is not None
        assert mock_create_react.called

    @patch("services.single_agent.create_react_agent")
    def test_create_agent_uses_default_prompt_when_empty(self, mock_create_react):
        """Test that default prompt is used when system_prompt is empty."""
        mock_agent = MagicMock()
        mock_create_react.return_value = mock_agent

        model_settings = ModelSettings(
            model_provider="openai",
            model_name="gpt-5-mini",
            max_tokens=6000,
            system_prompt="",  # Empty prompt
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}):
            agent = create_geo_agent(model_settings=model_settings)

        assert agent is not None
        call_kwargs = mock_create_react.call_args[1]
        # Should use default prompt, not empty string
        assert call_kwargs["prompt"] != ""

    @patch("services.single_agent.create_react_agent")
    def test_create_agent_without_model_settings_uses_env_default(self, mock_create_react):
        """Test that agent uses env-configured provider when no settings provided."""
        mock_agent = MagicMock()
        mock_create_react.return_value = mock_agent

        with patch.dict(
            os.environ,
            {"LLM_PROVIDER": "openai", "OPENAI_API_KEY": "sk-test-key"},
        ):
            agent = create_geo_agent(model_settings=None)

        assert agent is not None
        assert mock_create_react.called


class TestLLMConfigModelParameter:
    """Test that llm_config correctly passes model_name parameter."""

    @patch("services.ai.openai.ChatOpenAI")
    def test_get_llm_for_provider_openai_with_model_name(self, mock_chat_openai):
        """Test that specific model name is used when provided."""
        from services.ai.llm_config import get_llm_for_provider

        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}):
            llm = get_llm_for_provider("openai", max_tokens=4000, model_name="gpt-5-nano")

        assert llm is not None
        # Verify ChatOpenAI was called with the correct model
        mock_chat_openai.assert_called_once()
        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs["model"] == "gpt-5-nano"
        assert call_kwargs["max_tokens"] == 4000

    @pytest.mark.skipif(
        not _is_google_provider_available(),
        reason="Google Gemini provider not available (missing langchain_google_genai)",
    )
    @patch("services.ai.google_genai.ChatGoogleGenerativeAI")
    def test_get_llm_for_provider_google_with_model_name(self, mock_chat_google):
        """Test that specific Google model name is used when provided."""
        from services.ai.llm_config import get_llm_for_provider

        mock_instance = MagicMock()
        mock_chat_google.return_value = mock_instance

        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            llm = get_llm_for_provider("google", max_tokens=8000, model_name="gemini-1.5-flash")

        assert llm is not None
        mock_chat_google.assert_called_once()
        call_kwargs = mock_chat_google.call_args[1]
        assert call_kwargs["model"] == "gemini-1.5-flash"

    def test_get_llm_for_provider_invalid_provider_raises(self):
        """Test that invalid provider name raises ValueError."""
        from services.ai.llm_config import get_llm_for_provider

        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            get_llm_for_provider("invalid_provider")
