"""
Performance monitoring utilities for agent execution.

Provides timing metrics, token tracking, and tool execution monitoring
through both manual tracking and LangChain callback handlers.
"""

import time
import logging
from typing import Any, Dict, List, Optional
from langchain.callbacks.base import BaseCallbackHandler

logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """Track performance metrics for agent execution.

    Provides simple timing and metric recording functionality.
    Use this for high-level request metrics.

    Example:
        >>> metrics = PerformanceMetrics()
        >>> metrics.record("message_count", 10)
        >>> metrics.start_timer("agent_execution")
        >>> # ... do work ...
        >>> metrics.end_timer("agent_execution")
        >>> final_metrics = metrics.finalize()
    """

    def __init__(self):
        """Initialize metrics tracker."""
        self.start_time = time.time()
        self.metrics: Dict[str, Any] = {
            "total_time": 0.0,
            "agent_time": 0.0,
            "message_count_before": 0,
            "message_count_after": 0,
            "message_count_final": 0,
            "message_reduction": 0,
            "token_usage": {},
            "state_size": 0,
        }
        self._timers: Dict[str, float] = {}

    def record(self, key: str, value: Any) -> None:
        """Record a metric value.

        Args:
            key: Metric name
            value: Metric value
        """
        self.metrics[key] = value

    def start_timer(self, name: str) -> None:
        """Start a named timer.

        Args:
            name: Timer name
        """
        self._timers[f"{name}_start"] = time.time()

    def end_timer(self, name: str) -> None:
        """End a named timer and calculate duration.

        Args:
            name: Timer name (must match start_timer call)
        """
        start_key = f"{name}_start"
        start_time = self._timers.get(start_key)
        if start_time:
            duration = time.time() - start_time
            self.metrics[name] = round(duration, 3)
            del self._timers[start_key]
        else:
            logger.warning(f"Timer '{name}' was not started")

    def increment(self, key: str, value: int = 1) -> None:
        """Increment a counter metric.

        Args:
            key: Metric name
            value: Amount to increment (default: 1)
        """
        self.metrics[key] = self.metrics.get(key, 0) + value

    def finalize(self) -> Dict[str, Any]:
        """Finalize and return all metrics.

        Calculates total time and returns the complete metrics dict.

        Returns:
            Dictionary of all collected metrics
        """
        self.metrics["total_time"] = round(time.time() - self.start_time, 3)
        return self.metrics


class PerformanceCallbackHandler(BaseCallbackHandler):
    """LangChain callback handler for detailed performance tracking.

    Automatically tracks:
    - LLM call timing and frequency
    - Tool execution timing (per tool)
    - Token usage (input/output/total)

    Works with both LangChain and LangGraph agents.

    Example:
        >>> callback = PerformanceCallbackHandler()
        >>> result = agent.invoke(state, config={"callbacks": [callback]})
        >>> metrics = callback.get_metrics()
    """

    def __init__(self):
        """Initialize callback handler."""
        super().__init__()
        self.metrics: Dict[str, Any] = {
            "llm_calls": 0,
            "llm_time": 0.0,
            "tool_calls": 0,
            "tool_times": {},
            "token_usage": {"input": 0, "output": 0, "total": 0},
            "errors": [],
        }
        self._llm_start_time: Optional[float] = None
        self._tool_start_times: Dict[str, float] = {}

    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any) -> None:
        """Called when LLM starts.

        Args:
            serialized: Serialized LLM
            prompts: List of prompts
            **kwargs: Additional arguments
        """
        self._llm_start_time = time.time()
        self.metrics["llm_calls"] += 1

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """Called when LLM finishes.

        Extracts token usage and calculates duration.

        Args:
            response: LLM response
            **kwargs: Additional arguments
        """
        if self._llm_start_time:
            duration = time.time() - self._llm_start_time
            self.metrics["llm_time"] += duration
            self._llm_start_time = None

        # Extract token usage from response
        if hasattr(response, "llm_output") and response.llm_output:
            token_usage = response.llm_output.get("token_usage", {})
            if token_usage:
                self.metrics["token_usage"]["input"] += token_usage.get("prompt_tokens", 0)
                self.metrics["token_usage"]["output"] += token_usage.get("completion_tokens", 0)
                self.metrics["token_usage"]["total"] += token_usage.get("total_tokens", 0)

        # Also try to get from generations if available
        if hasattr(response, "generations") and response.generations:
            for gen_list in response.generations:
                for gen in gen_list:
                    if hasattr(gen, "generation_info") and gen.generation_info:
                        token_usage = gen.generation_info.get("token_usage", {})
                        if token_usage:
                            self.metrics["token_usage"]["input"] += token_usage.get(
                                "prompt_tokens", 0
                            )
                            self.metrics["token_usage"]["output"] += token_usage.get(
                                "completion_tokens", 0
                            )
                            self.metrics["token_usage"]["total"] += token_usage.get(
                                "total_tokens", 0
                            )

    def on_llm_error(self, error: Exception, **kwargs: Any) -> None:
        """Called when LLM encounters an error.

        Args:
            error: The error that occurred
            **kwargs: Additional arguments
        """
        self.metrics["errors"].append({"type": "llm", "error": str(error)})
        if self._llm_start_time:
            self._llm_start_time = None

    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs: Any) -> None:
        """Called when tool execution starts.

        Args:
            serialized: Serialized tool
            input_str: Tool input
            **kwargs: Additional arguments
        """
        tool_name = serialized.get("name", "unknown")
        self._tool_start_times[tool_name] = time.time()
        self.metrics["tool_calls"] += 1

    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        """Called when tool execution finishes.

        Args:
            output: Tool output
            **kwargs: Additional arguments
        """
        # Try to get tool name from kwargs or use last started tool
        tool_name = kwargs.get("name")
        if not tool_name and self._tool_start_times:
            # Use the most recently started tool
            tool_name = list(self._tool_start_times.keys())[-1]

        if tool_name:
            start_time = self._tool_start_times.pop(tool_name, None)
            if start_time:
                duration = round(time.time() - start_time, 3)
                if tool_name not in self.metrics["tool_times"]:
                    self.metrics["tool_times"][tool_name] = []
                self.metrics["tool_times"][tool_name].append(duration)

    def on_tool_error(self, error: Exception, **kwargs: Any) -> None:
        """Called when tool execution encounters an error.

        Args:
            error: The error that occurred
            **kwargs: Additional arguments
        """
        tool_name = kwargs.get("name", "unknown")
        self.metrics["errors"].append({"type": "tool", "tool": tool_name, "error": str(error)})

        # Clean up timer
        if tool_name in self._tool_start_times:
            del self._tool_start_times[tool_name]

    def get_metrics(self) -> Dict[str, Any]:
        """Get all collected metrics.

        Returns:
            Dictionary of performance metrics including:
            - llm_calls: Number of LLM calls
            - llm_time: Total time spent in LLM calls
            - tool_calls: Number of tool executions
            - tool_times: Dict of tool name -> list of execution times
            - token_usage: Dict with input/output/total tokens
            - errors: List of errors encountered
        """
        # Round LLM time
        self.metrics["llm_time"] = round(self.metrics["llm_time"], 3)

        # Calculate average tool times for better readability
        tool_stats = {}
        for tool_name, times in self.metrics["tool_times"].items():
            tool_stats[tool_name] = {
                "calls": len(times),
                "total_time": round(sum(times), 3),
                "avg_time": round(sum(times) / len(times), 3) if times else 0,
                "min_time": round(min(times), 3) if times else 0,
                "max_time": round(max(times), 3) if times else 0,
            }

        return {
            "llm_calls": self.metrics["llm_calls"],
            "llm_time": self.metrics["llm_time"],
            "tool_calls": self.metrics["tool_calls"],
            "tool_times": self.metrics["tool_times"],
            "tool_stats": tool_stats,
            "token_usage": self.metrics["token_usage"],
            "errors": self.metrics["errors"],
        }


def extract_token_usage_from_messages(messages: List[Any]) -> Dict[str, int]:
    """Extract token usage from AI messages.

    Scans message list for AIMessage instances with token usage metadata.

    Args:
        messages: List of messages (BaseMessage instances)

    Returns:
        Dict with input_tokens, output_tokens, total_tokens
    """
    token_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    for msg in messages:
        # Check if it's an AI message with response_metadata
        if hasattr(msg, "response_metadata") and msg.response_metadata:
            usage = msg.response_metadata.get("token_usage", {})
            if usage:
                token_usage["input_tokens"] += usage.get("prompt_tokens", 0)
                token_usage["output_tokens"] += usage.get("completion_tokens", 0)
                token_usage["total_tokens"] += usage.get("total_tokens", 0)

        # Also check additional_kwargs (some LLMs store it there)
        if hasattr(msg, "additional_kwargs") and msg.additional_kwargs:
            usage = msg.additional_kwargs.get("token_usage", {})
            if usage:
                token_usage["input_tokens"] += usage.get("prompt_tokens", 0)
                token_usage["output_tokens"] += usage.get("completion_tokens", 0)
                token_usage["total_tokens"] += usage.get("total_tokens", 0)

    return token_usage
