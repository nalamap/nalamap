"""
Tests for message window management and pruning functionality.

Tests the prune_messages() function to ensure proper message history
management while preserving system context.
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from services.single_agent import prune_messages


class TestMessagePruning:
    """Test suite for message pruning functionality."""

    def test_prune_empty_messages(self):
        """Test pruning with empty message list."""
        result = prune_messages([], window_size=10)
        assert result == []

    def test_prune_zero_window_size(self):
        """Test that window_size=0 returns original messages unchanged."""
        messages = [
            SystemMessage(content="System prompt"),
            HumanMessage(content="Hello"),
            AIMessage(content="Hi"),
        ]
        result = prune_messages(messages, window_size=0)
        assert result == messages

    def test_prune_messages_below_window(self):
        """Test that messages below window size are not pruned."""
        messages = [
            SystemMessage(content="System prompt"),
            HumanMessage(content="Message 1"),
            AIMessage(content="Response 1"),
            HumanMessage(content="Message 2"),
            AIMessage(content="Response 2"),
        ]
        result = prune_messages(messages, window_size=10)
        assert len(result) == 5
        assert result == messages

    def test_prune_preserves_system_message(self):
        """Test that system messages are always preserved."""
        messages = [
            SystemMessage(content="System prompt"),
            HumanMessage(content="Message 1"),
            AIMessage(content="Response 1"),
            HumanMessage(content="Message 2"),
            AIMessage(content="Response 2"),
            HumanMessage(content="Message 3"),
            AIMessage(content="Response 3"),
        ]
        result = prune_messages(messages, window_size=2)

        # Should have 1 system message + 2 most recent conversation messages
        assert len(result) == 3
        assert isinstance(result[0], SystemMessage)
        assert result[0].content == "System prompt"
        assert result[1].content == "Message 3"
        assert result[2].content == "Response 3"

    def test_prune_multiple_system_messages(self):
        """Test pruning with multiple system messages."""
        messages = [
            SystemMessage(content="System prompt 1"),
            SystemMessage(content="System prompt 2"),
            HumanMessage(content="Message 1"),
            AIMessage(content="Response 1"),
            HumanMessage(content="Message 2"),
            AIMessage(content="Response 2"),
        ]
        result = prune_messages(messages, window_size=2)

        # Both system messages should be preserved
        assert len(result) == 4  # 2 system + 2 conversation
        assert isinstance(result[0], SystemMessage)
        assert isinstance(result[1], SystemMessage)
        assert result[2].content == "Message 2"
        assert result[3].content == "Response 2"

    def test_prune_no_system_messages(self):
        """Test pruning when there are no system messages."""
        messages = [
            HumanMessage(content="Message 1"),
            AIMessage(content="Response 1"),
            HumanMessage(content="Message 2"),
            AIMessage(content="Response 2"),
            HumanMessage(content="Message 3"),
            AIMessage(content="Response 3"),
        ]
        result = prune_messages(messages, window_size=2)

        # Should keep only the last 2 messages
        assert len(result) == 2
        assert result[0].content == "Message 3"
        assert result[1].content == "Response 3"

    def test_prune_exact_window_size(self):
        """Test pruning when messages equal window size."""
        messages = [
            SystemMessage(content="System prompt"),
            HumanMessage(content="Message 1"),
            AIMessage(content="Response 1"),
            HumanMessage(content="Message 2"),
            AIMessage(content="Response 2"),
        ]
        result = prune_messages(messages, window_size=4)

        # 1 system + 4 conversation messages = 5 total
        assert len(result) == 5
        assert result == messages

    def test_prune_large_conversation(self):
        """Test pruning a large conversation (20+ messages)."""
        messages = [SystemMessage(content="System prompt")]

        # Add 20 conversation turns (40 messages)
        for i in range(1, 21):
            messages.append(HumanMessage(content=f"Message {i}"))
            messages.append(AIMessage(content=f"Response {i}"))

        result = prune_messages(messages, window_size=10)

        # Should have 1 system + 10 most recent conversation messages
        assert len(result) == 11
        assert isinstance(result[0], SystemMessage)

        # Verify we kept the last 10 messages (messages 16-20, 5 turns)
        assert result[1].content == "Message 16"
        assert result[-2].content == "Message 20"
        assert result[-1].content == "Response 20"

    def test_prune_preserves_message_types(self):
        """Test that message types are preserved correctly."""
        messages = [
            SystemMessage(content="System"),
            HumanMessage(content="Human 1"),
            AIMessage(content="AI 1"),
            HumanMessage(content="Human 2"),
            AIMessage(content="AI 2"),
        ]
        result = prune_messages(messages, window_size=2)

        assert isinstance(result[0], SystemMessage)
        assert isinstance(result[1], HumanMessage)
        assert isinstance(result[2], AIMessage)

    def test_prune_without_preserve_system(self):
        """Test pruning with preserve_system=False."""
        messages = [
            SystemMessage(content="System prompt"),
            HumanMessage(content="Message 1"),
            AIMessage(content="Response 1"),
            HumanMessage(content="Message 2"),
            AIMessage(content="Response 2"),
        ]
        result = prune_messages(messages, window_size=2, preserve_system=False)

        # Should only keep last 2 messages, no system message
        assert len(result) == 2
        assert result[0].content == "Message 2"
        assert result[1].content == "Response 2"
        # Verify no system messages
        assert all(not isinstance(msg, SystemMessage) for msg in result)

    def test_prune_window_size_one(self):
        """Test pruning with window_size=1 keeps only most recent message."""
        messages = [
            SystemMessage(content="System prompt"),
            HumanMessage(content="Message 1"),
            AIMessage(content="Response 1"),
            HumanMessage(content="Message 2"),
            AIMessage(content="Response 2"),
        ]
        result = prune_messages(messages, window_size=1)

        assert len(result) == 2  # 1 system + 1 conversation
        assert isinstance(result[0], SystemMessage)
        assert result[1].content == "Response 2"

    def test_prune_negative_window_size(self):
        """Test that negative window size returns original messages."""
        messages = [
            HumanMessage(content="Message 1"),
            AIMessage(content="Response 1"),
        ]
        result = prune_messages(messages, window_size=-1)
        assert result == messages

    @pytest.mark.parametrize("window_size", [5, 10, 15, 20])
    def test_prune_various_window_sizes(self, window_size):
        """Test pruning with various window sizes."""
        # Create 30 messages
        messages = [SystemMessage(content="System")]
        for i in range(1, 16):
            messages.append(HumanMessage(content=f"H{i}"))
            messages.append(AIMessage(content=f"A{i}"))

        result = prune_messages(messages, window_size=window_size)

        # Should have 1 system + window_size conversation messages
        expected_length = 1 + window_size
        assert len(result) == expected_length
        assert isinstance(result[0], SystemMessage)


class TestMessagePruningIntegration:
    """Integration tests for message pruning with agent state."""

    def test_prune_maintains_conversation_flow(self):
        """Test that pruning maintains logical conversation flow."""
        messages = [
            SystemMessage(content="You are a helpful assistant."),
            HumanMessage(content="What is 2+2?"),
            AIMessage(content="2+2 equals 4."),
            HumanMessage(content="What is 3+3?"),
            AIMessage(content="3+3 equals 6."),
            HumanMessage(content="What is 5+5?"),
            AIMessage(content="5+5 equals 10."),
        ]

        result = prune_messages(messages, window_size=4)

        # Verify we have system + last 2 Q&A pairs
        assert len(result) == 5
        assert result[0].content == "You are a helpful assistant."
        assert result[1].content == "What is 3+3?"
        assert result[4].content == "5+5 equals 10."

    def test_prune_with_mixed_message_types(self):
        """Test pruning with realistic mixed message types."""
        messages = [
            SystemMessage(content="System context"),
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there! How can I help?"),
            HumanMessage(content="Show me a map"),
            AIMessage(content="Tool call: geocode_location"),
            AIMessage(content="Here's the map you requested"),
            HumanMessage(content="Thanks!"),
            AIMessage(content="You're welcome!"),
        ]

        result = prune_messages(messages, window_size=4)

        # Should preserve system + last 4 messages
        assert len(result) == 5
        assert isinstance(result[0], SystemMessage)
        # Last 4 should be the final exchange
        assert result[-1].content == "You're welcome!"
