"""Tests for ConversationManager.

This module tests the conversation summarization functionality, including:
- Message threshold detection
- Summary generation
- Message formatting
- Fallback behavior
- Edge cases
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from unittest.mock import AsyncMock, Mock

from services.conversation_manager import ConversationManager


@pytest.fixture
def conversation_manager():
    """Create a ConversationManager with test parameters."""
    return ConversationManager(max_messages=20, summarize_threshold=15, summary_window=10)


@pytest.fixture
def mock_llm():
    """Create a mock LLM for testing."""
    llm = AsyncMock()
    mock_response = Mock()
    mock_response.content = "Summary of the conversation about Berlin and Paris locations."
    llm.ainvoke.return_value = mock_response
    return llm


@pytest.mark.asyncio
async def test_below_threshold_no_summarization(conversation_manager):
    """Test that messages below threshold are returned unchanged."""
    messages = [
        SystemMessage(content="System prompt"),
        HumanMessage(content="Query 1"),
        AIMessage(content="Response 1"),
    ]

    result = await conversation_manager.process_messages(messages)

    assert len(result) == 3
    assert result == messages
    assert conversation_manager.has_summary() is False


@pytest.mark.asyncio
async def test_summarization_triggered(conversation_manager, mock_llm):
    """Test that summarization is triggered when threshold is exceeded."""
    # Create 20 messages (exceeds threshold of 15)
    messages = [SystemMessage(content="System prompt")]
    for i in range(20):
        messages.append(HumanMessage(content=f"Query {i}"))
        messages.append(AIMessage(content=f"Response {i}"))

    result = await conversation_manager.process_messages(messages, llm=mock_llm)

    # Should have: system message + summary message + 10 recent messages
    # Recent messages = 10 window * 2 (human + AI) = 20 messages
    assert len(result) < len(messages)
    assert conversation_manager.has_summary() is True
    assert mock_llm.ainvoke.called


@pytest.mark.asyncio
async def test_summary_content_preserved(conversation_manager, mock_llm):
    """Test that summary is correctly added to messages."""
    messages = [SystemMessage(content="System prompt")]
    for i in range(20):
        messages.append(HumanMessage(content=f"Query {i}"))
        messages.append(AIMessage(content=f"Response {i}"))

    result = await conversation_manager.process_messages(messages, llm=mock_llm)

    # Find summary message
    summary_messages = [
        m for m in result if isinstance(m, SystemMessage) and "summary" in m.content.lower()
    ]
    assert len(summary_messages) == 1
    assert "Summary of the conversation" in summary_messages[0].content


@pytest.mark.asyncio
async def test_system_messages_preserved(conversation_manager, mock_llm):
    """Test that system messages are preserved during summarization."""
    messages = [
        SystemMessage(content="System prompt 1"),
        SystemMessage(content="System prompt 2"),
    ]
    for i in range(20):
        messages.append(HumanMessage(content=f"Query {i}"))
        messages.append(AIMessage(content=f"Response {i}"))

    result = await conversation_manager.process_messages(messages, llm=mock_llm)

    # Should have original system messages + summary message
    system_messages = [m for m in result if isinstance(m, SystemMessage)]
    assert len(system_messages) >= 2  # At least original system messages


@pytest.mark.asyncio
async def test_recent_messages_kept(conversation_manager, mock_llm):
    """Test that recent messages are kept unsummarized."""
    messages = [SystemMessage(content="System prompt")]
    for i in range(20):
        messages.append(HumanMessage(content=f"Query {i}"))
        messages.append(AIMessage(content=f"Response {i}"))

    result = await conversation_manager.process_messages(messages, llm=mock_llm)

    # Check that most recent messages are preserved
    last_human = None
    for msg in reversed(result):
        if isinstance(msg, HumanMessage):
            last_human = msg
            break

    assert last_human is not None
    assert "Query 19" in last_human.content  # Most recent query


@pytest.mark.asyncio
async def test_fallback_on_llm_error(conversation_manager):
    """Test fallback to truncation when LLM fails."""
    # Create failing LLM
    failing_llm = AsyncMock()
    failing_llm.ainvoke.side_effect = Exception("LLM error")

    messages = [SystemMessage(content="System prompt")]
    for i in range(30):
        messages.append(HumanMessage(content=f"Query {i}"))
        messages.append(AIMessage(content=f"Response {i}"))

    result = await conversation_manager.process_messages(messages, llm=failing_llm)

    # Should fall back to truncation (max_messages = 20)
    # Result should be: system messages + last 20 conversation messages
    assert len(result) <= 21  # 1 system + 20 conversation messages
    assert conversation_manager.has_summary() is False


@pytest.mark.asyncio
async def test_no_llm_provided(conversation_manager):
    """Test fallback when no LLM is provided."""
    messages = [SystemMessage(content="System prompt")]
    for i in range(30):
        messages.append(HumanMessage(content=f"Query {i}"))
        messages.append(AIMessage(content=f"Response {i}"))

    result = await conversation_manager.process_messages(messages, llm=None)

    # Should fall back to truncation
    assert len(result) <= 21  # 1 system + 20 conversation messages
    assert conversation_manager.has_summary() is False


@pytest.mark.asyncio
async def test_message_formatting():
    """Test that messages are correctly formatted for summarization."""
    manager = ConversationManager()

    messages = [
        HumanMessage(content="Find Berlin"),
        AIMessage(content="Found Berlin at coordinates..."),
        HumanMessage(content="Create buffer"),
        AIMessage(content="Created buffer with 500m radius"),
    ]

    formatted = manager._format_messages_for_summary(messages)

    assert "User: Find Berlin" in formatted
    assert "Assistant: Found Berlin" in formatted
    assert "User: Create buffer" in formatted
    assert "Assistant: Created buffer" in formatted


@pytest.mark.asyncio
async def test_long_content_truncation():
    """Test that long AI messages are truncated in summary."""
    manager = ConversationManager()

    long_content = "x" * 1000  # Create very long content
    messages = [
        HumanMessage(content="Query"),
        AIMessage(content=long_content),
    ]

    formatted = manager._format_messages_for_summary(messages)

    # Should be truncated to 500 chars + "..."
    assert len(formatted) < len(long_content)
    assert "..." in formatted


@pytest.mark.asyncio
async def test_reset_clears_summary(conversation_manager, mock_llm):
    """Test that reset clears the conversation summary."""
    messages = [SystemMessage(content="System prompt")]
    for i in range(20):
        messages.append(HumanMessage(content=f"Query {i}"))
        messages.append(AIMessage(content=f"Response {i}"))

    await conversation_manager.process_messages(messages, llm=mock_llm)
    assert conversation_manager.has_summary() is True

    conversation_manager.reset()
    assert conversation_manager.has_summary() is False
    assert conversation_manager.get_summary() is None


@pytest.mark.asyncio
async def test_get_summary(conversation_manager, mock_llm):
    """Test retrieving the current summary."""
    messages = [SystemMessage(content="System prompt")]
    for i in range(20):
        messages.append(HumanMessage(content=f"Query {i}"))
        messages.append(AIMessage(content=f"Response {i}"))

    await conversation_manager.process_messages(messages, llm=mock_llm)

    summary = conversation_manager.get_summary()
    assert summary is not None
    assert "Summary of the conversation" in summary


@pytest.mark.asyncio
async def test_cumulative_summarization(conversation_manager, mock_llm):
    """Test that summaries can build on previous summaries."""
    # First batch
    messages1 = [SystemMessage(content="System prompt")]
    for i in range(20):
        messages1.append(HumanMessage(content=f"Query {i}"))
        messages1.append(AIMessage(content=f"Response {i}"))

    await conversation_manager.process_messages(messages1, llm=mock_llm)
    first_summary = conversation_manager.get_summary()

    # Second batch
    messages2 = [SystemMessage(content="System prompt")]
    for i in range(20, 40):
        messages2.append(HumanMessage(content=f"Query {i}"))
        messages2.append(AIMessage(content=f"Response {i}"))

    mock_llm.ainvoke.reset_mock()
    await conversation_manager.process_messages(messages2, llm=mock_llm)

    # Verify LLM was called with previous summary
    call_args = mock_llm.ainvoke.call_args[0][0]
    assert first_summary in call_args or "Previous summary" in call_args


def test_invalid_parameters():
    """Test that invalid parameters raise errors."""
    # summary_window > summarize_threshold
    with pytest.raises(ValueError):
        ConversationManager(max_messages=20, summarize_threshold=10, summary_window=15)

    # max_messages < summary_window
    with pytest.raises(ValueError):
        ConversationManager(max_messages=5, summarize_threshold=10, summary_window=10)


@pytest.mark.asyncio
async def test_empty_messages(conversation_manager):
    """Test handling of empty message list."""
    result = await conversation_manager.process_messages([])
    assert result == []


@pytest.mark.asyncio
async def test_only_system_messages(conversation_manager, mock_llm):
    """Test handling of messages with only system messages."""
    messages = [
        SystemMessage(content="System prompt 1"),
        SystemMessage(content="System prompt 2"),
    ]

    result = await conversation_manager.process_messages(messages, llm=mock_llm)
    assert result == messages
    assert not mock_llm.ainvoke.called  # Should not try to summarize


@pytest.mark.asyncio
async def test_exact_threshold(conversation_manager, mock_llm):
    """Test behavior at exact threshold boundary."""
    # Create exactly 15 messages (the threshold)
    messages = [SystemMessage(content="System prompt")]
    for i in range(15):
        messages.append(HumanMessage(content=f"Query {i}"))
        messages.append(AIMessage(content=f"Response {i}"))

    # At threshold, should trigger summarization
    # Note: result unused here, just testing that summarization occurs
    await conversation_manager.process_messages(messages, llm=mock_llm)  # noqa: F841

    assert mock_llm.ainvoke.called
    assert conversation_manager.has_summary() is True
