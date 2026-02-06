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

    @pytest.mark.asyncio
    @patch("services.single_agent.create_react_agent")
    async def test_create_agent_with_openai_model_settings(self, mock_create_react):
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
            agent, llm = await create_geo_agent(model_settings=model_settings)

        assert agent is not None
        # Verify that create_react_agent was called
        assert mock_create_react.called

        # Get the call arguments
        call_kwargs = mock_create_react.call_args[1]
        assert call_kwargs["prompt"] == "Test prompt"

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not _is_google_provider_available(),
        reason="Google Gemini provider not available (missing langchain_google_genai)",
    )
    @patch("services.single_agent.create_react_agent")
    async def test_create_agent_with_google_model_settings(self, mock_create_react):
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
            agent, llm = await create_geo_agent(model_settings=model_settings)

        assert agent is not None
        assert mock_create_react.called

    @pytest.mark.asyncio
    @patch("services.single_agent.create_react_agent")
    async def test_create_agent_uses_default_prompt_when_empty(self, mock_create_react):
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
            agent, llm = await create_geo_agent(model_settings=model_settings)

        assert agent is not None
        call_kwargs = mock_create_react.call_args[1]
        # Should use default prompt, not empty string
        assert call_kwargs["prompt"] != ""

    @pytest.mark.asyncio
    @patch("services.single_agent.create_react_agent")
    async def test_create_agent_without_model_settings_uses_env_default(self, mock_create_react):
        """Test that agent uses env-configured provider when no settings provided."""
        mock_agent = MagicMock()
        mock_create_react.return_value = mock_agent

        with patch.dict(
            os.environ,
            {"LLM_PROVIDER": "openai", "OPENAI_API_KEY": "sk-test-key"},
        ):
            agent, llm = await create_geo_agent(model_settings=None)

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
            llm, capabilities = get_llm_for_provider(
                "openai", max_tokens=4000, model_name="gpt-5-nano"
            )

        assert llm is not None
        assert capabilities is not None
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
            llm, capabilities = get_llm_for_provider(
                "google", max_tokens=8000, model_name="gemini-1.5-flash"
            )

        assert llm is not None
        mock_chat_google.assert_called_once()
        call_kwargs = mock_chat_google.call_args[1]
        assert call_kwargs["model"] == "gemini-1.5-flash"

    def test_get_llm_for_provider_invalid_provider_raises(self):
        """Test that invalid provider name raises ValueError."""
        from services.ai.llm_config import get_llm_for_provider

        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            get_llm_for_provider("invalid_provider")


class TestConversationSummarization:
    """Integration tests for conversation summarization feature."""

    @pytest.mark.asyncio
    @patch("services.single_agent.create_react_agent")
    async def test_create_agent_with_session_id(self, mock_create_react):
        """Test creating agent with session_id creates conversation manager."""
        from unittest.mock import MagicMock

        mock_agent = MagicMock()
        mock_create_react.return_value = mock_agent

        model_settings = ModelSettings(
            model_provider="openai",
            model_name="gpt-4o-mini",
            max_tokens=4000,
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}):
            agent, llm = await create_geo_agent(
                model_settings=model_settings,
                session_id="test-session-123",
            )

        assert agent is not None
        assert llm is not None

    @pytest.mark.asyncio
    @patch("services.single_agent.create_react_agent")
    async def test_conversation_manager_session_reuse(self, mock_create_react):
        """Test that conversation manager is reused for same session."""
        from services.single_agent import conversation_managers

        mock_agent = MagicMock()
        mock_create_react.return_value = mock_agent

        session_id = "test-session-reuse"

        # Clear any existing session
        if session_id in conversation_managers:
            del conversation_managers[session_id]

        with patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "sk-test-key", "MESSAGE_MANAGEMENT_MODE": "summarize"},
        ):
            from services.single_agent import get_conversation_manager

            # Create managers for same session
            first_manager = get_conversation_manager(session_id, 20)
            second_manager = get_conversation_manager(session_id, 20)

            # Should be same manager instance
            assert first_manager is second_manager

    @pytest.mark.asyncio
    @patch("services.single_agent.create_react_agent")
    async def test_prepare_messages_prune_mode(self, mock_create_react):
        """Test that prepare_messages uses pruning in 'prune' mode."""
        from services.single_agent import prepare_messages
        from langchain_core.messages import HumanMessage

        messages = [HumanMessage(content=f"msg-{i}") for i in range(30)]

        with patch.dict(os.environ, {"MESSAGE_MANAGEMENT_MODE": "prune"}):
            result = await prepare_messages(
                messages=messages,
                message_window_size=10,
                session_id="test-session",
            )

        # Should be pruned to window size
        assert len(result) == 10

    @pytest.mark.asyncio
    @patch("services.single_agent.create_react_agent")
    async def test_prepare_messages_summarize_mode_without_session(self, mock_create_react):
        """Test that summarization falls back to pruning without session_id."""
        from services.single_agent import prepare_messages
        from langchain_core.messages import HumanMessage

        messages = [HumanMessage(content=f"msg-{i}") for i in range(30)]

        with patch.dict(os.environ, {"MESSAGE_MANAGEMENT_MODE": "summarize"}):
            result = await prepare_messages(
                messages=messages,
                message_window_size=10,
                session_id=None,  # No session ID
            )

        # Should fall back to pruning
        assert len(result) == 10

    @pytest.mark.asyncio
    @patch("services.single_agent.create_react_agent")
    async def test_session_cleanup_on_ttl(self, mock_create_react):
        """Test that expired sessions are cleaned up."""
        import time
        from services.single_agent import SESSION_TTL, conversation_managers

        mock_agent = MagicMock()
        mock_create_react.return_value = mock_agent

        session_id = "test-session-cleanup"

        # Clear any existing session
        if session_id in conversation_managers:
            del conversation_managers[session_id]

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}):
            from services.single_agent import get_conversation_manager

            # Create session via get_conversation_manager
            get_conversation_manager(session_id, 20)
            assert session_id in conversation_managers

            # Manually set last_access to expired time
            conversation_managers[session_id]["last_access"] = time.time() - SESSION_TTL - 1

            # Create another session, which should trigger cleanup
            get_conversation_manager("test-session-new", 20)

            # Old session should be cleaned up
            assert session_id not in conversation_managers
            assert "test-session-new" in conversation_managers

    def test_conversation_manager_parameters(self):
        """Test conversation manager creation with correct parameters."""
        from services.single_agent import get_conversation_manager

        session_id = "test-params"
        message_window_size = 15

        manager = get_conversation_manager(session_id, message_window_size)

        assert manager.max_messages == message_window_size * 2  # 30
        assert manager.summarize_threshold == message_window_size + 5  # 20
        assert manager.summary_window == message_window_size  # 15
