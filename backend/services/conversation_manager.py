"""Conversation Manager for handling message history with automatic summarization.

This module provides the ConversationManager class which intelligently manages
conversation history by automatically summarizing older messages when the
conversation exceeds a certain threshold. This helps maintain context while
reducing token count for long conversations.
"""

import logging
from typing import Any, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import PromptTemplate

logger = logging.getLogger(__name__)


class ConversationManager:
    """Manages conversation history with automatic summarization.

    This class monitors conversation length and automatically generates
    summaries of older messages when the conversation exceeds a threshold.
    It preserves recent messages for immediate context while condensing
    older messages into a summary to save tokens.

    Attributes:
        max_messages: Maximum messages to keep without summarization
        summarize_threshold: Trigger summarization at this message count
        summary_window: Number of recent messages to keep unsummarized
        current_summary: Current conversation summary (None if not yet generated)
    """

    SUMMARY_PROMPT = PromptTemplate.from_template(
        """Summarize the following conversation between a user and a geospatial AI assistant.
Focus on:
- Locations and areas discussed
- Layers created or loaded
- Operations performed (geocoding, geoprocessing, styling)
- Important results or decisions

Previous summary (if any): {previous_summary}

Recent conversation:
{conversation}

Provide a concise summary that preserves geographic context and key actions:"""
    )

    def __init__(
        self,
        max_messages: int = 20,
        summarize_threshold: int = 15,
        summary_window: int = 10,
    ):
        """Initialize conversation manager.

        Args:
            max_messages: Maximum messages to keep without summarization
            summarize_threshold: Trigger summarization at this message count
            summary_window: Number of recent messages to keep unsummarized

        Raises:
            ValueError: If parameters are invalid (e.g., summary_window > summarize_threshold)
        """
        if summary_window > summarize_threshold:
            raise ValueError("summary_window cannot be greater than summarize_threshold")

        if max_messages < summary_window:
            raise ValueError("max_messages should be >= summary_window")

        self.max_messages = max_messages
        self.summarize_threshold = summarize_threshold
        self.summary_window = summary_window
        self.current_summary: Optional[str] = None

    def _format_messages_for_summary(self, messages: List[BaseMessage]) -> str:
        """Format messages into readable conversation text.

        Converts a list of BaseMessage objects into a human-readable conversation
        format suitable for LLM summarization. Truncates long tool outputs.

        Args:
            messages: List of messages to format

        Returns:
            Formatted conversation string
        """
        conversation_parts = []

        for msg in messages:
            if isinstance(msg, HumanMessage):
                conversation_parts.append(f"User: {msg.content}")
            elif isinstance(msg, AIMessage):
                # Truncate long tool outputs
                content = str(msg.content)
                if len(content) > 500:
                    content = content[:500] + "..."
                conversation_parts.append(f"Assistant: {content}")

        return "\n".join(conversation_parts)

    async def process_messages(
        self, messages: List[BaseMessage], llm: Optional[Any] = None
    ) -> List[BaseMessage]:
        """Process messages with automatic summarization if needed.

        Analyzes the message count and triggers summarization if the threshold
        is exceeded. Preserves system messages and recent conversation context
        while condensing older messages into a summary.

        Args:
            messages: Full conversation history
            llm: Language model for generating summaries (optional)

        Returns:
            Processed message list with summary if applicable

        Note:
            If no LLM is provided or summarization fails, falls back to simple
            message truncation to prevent unbounded context growth.
        """
        # If below threshold, return as-is
        if len(messages) < self.summarize_threshold:
            return messages

        # Extract system messages (preserve)
        system_messages = [m for m in messages if isinstance(m, SystemMessage)]
        non_system_messages = [m for m in messages if not isinstance(m, SystemMessage)]

        # Keep recent messages, summarize older ones
        recent_messages = non_system_messages[-self.summary_window :]
        older_messages = non_system_messages[: -self.summary_window]

        if not older_messages:
            return messages

        # Generate summary of older messages
        if llm:
            try:
                conversation_text = self._format_messages_for_summary(older_messages)

                summary_prompt = self.SUMMARY_PROMPT.format(
                    previous_summary=self.current_summary or "None",
                    conversation=conversation_text,
                )

                # Generate summary
                summary = await llm.ainvoke(summary_prompt)
                self.current_summary = (
                    summary.content if hasattr(summary, "content") else str(summary)
                )

                logger.info(
                    f"Generated conversation summary ({len(older_messages)} messages -> "
                    f"{len(self.current_summary)} chars)"
                )

                # Build condensed message list
                condensed_messages = system_messages.copy()
                condensed_messages.append(
                    SystemMessage(content=f"Conversation summary: {self.current_summary}")
                )
                condensed_messages.extend(recent_messages)

                return condensed_messages

            except Exception as e:
                logger.error(f"Failed to generate summary: {e}")
                # Fall back to simple truncation
                return system_messages + non_system_messages[-self.max_messages :]

        # No LLM provided, fall back to simple truncation
        logger.warning(
            f"No LLM provided for summarization, falling back to truncation "
            f"(keeping last {self.max_messages} messages)"
        )
        return system_messages + non_system_messages[-self.max_messages :]

    def reset(self):
        """Reset conversation state.

        Clears the current summary. Use this when starting a new conversation
        or when you want to reset the conversation context.
        """
        self.current_summary = None

    def get_summary(self) -> Optional[str]:
        """Get the current conversation summary.

        Returns:
            Current summary string if available, None otherwise
        """
        return self.current_summary

    def has_summary(self) -> bool:
        """Check if a summary has been generated.

        Returns:
            True if a summary exists, False otherwise
        """
        return self.current_summary is not None
