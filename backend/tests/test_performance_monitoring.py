"""
Tests for performance monitoring functionality.

Tests the PerformanceMetrics and PerformanceCallbackHandler classes
to ensure proper metric collection and timing.
"""

import time
from unittest.mock import Mock
from langchain_core.messages import AIMessage, HumanMessage

from utility.performance_metrics import (
    PerformanceMetrics,
    PerformanceCallbackHandler,
    extract_token_usage_from_messages,
)


class TestPerformanceMetrics:
    """Test suite for PerformanceMetrics class."""

    def test_initialization(self):
        """Test metrics initialization."""
        metrics = PerformanceMetrics()
        assert "total_time" in metrics.metrics
        assert "agent_time" in metrics.metrics
        assert "message_count_before" in metrics.metrics
        assert metrics.metrics["total_time"] == 0.0

    def test_record_metric(self):
        """Test recording a simple metric."""
        metrics = PerformanceMetrics()
        metrics.record("test_value", 42)
        assert metrics.metrics["test_value"] == 42

    def test_record_string_metric(self):
        """Test recording a string metric."""
        metrics = PerformanceMetrics()
        metrics.record("test_string", "hello")
        assert metrics.metrics["test_string"] == "hello"

    def test_timer_basic(self):
        """Test basic timer functionality."""
        metrics = PerformanceMetrics()
        metrics.start_timer("test")
        time.sleep(0.1)
        metrics.end_timer("test")

        assert "test" in metrics.metrics
        # Should be around 0.1 seconds (allow some variance)
        assert 0.09 < metrics.metrics["test"] < 0.15

    def test_multiple_timers(self):
        """Test multiple concurrent timers."""
        metrics = PerformanceMetrics()

        metrics.start_timer("timer1")
        time.sleep(0.05)
        metrics.start_timer("timer2")
        time.sleep(0.05)
        metrics.end_timer("timer1")
        time.sleep(0.05)
        metrics.end_timer("timer2")

        assert "timer1" in metrics.metrics
        assert "timer2" in metrics.metrics
        # timer1 should be ~0.1s, timer2 should be ~0.1s
        assert 0.08 < metrics.metrics["timer1"] < 0.15
        assert 0.08 < metrics.metrics["timer2"] < 0.15

    def test_end_timer_without_start(self):
        """Test ending a timer that was never started."""
        metrics = PerformanceMetrics()
        metrics.end_timer("nonexistent")  # Should not raise, just log warning
        assert "nonexistent" not in metrics.metrics

    def test_increment_counter(self):
        """Test incrementing a counter metric."""
        metrics = PerformanceMetrics()
        metrics.increment("counter")
        assert metrics.metrics["counter"] == 1

        metrics.increment("counter")
        assert metrics.metrics["counter"] == 2

        metrics.increment("counter", 5)
        assert metrics.metrics["counter"] == 7

    def test_finalize(self):
        """Test finalizing metrics calculates total time."""
        metrics = PerformanceMetrics()
        time.sleep(0.1)
        final = metrics.finalize()

        assert "total_time" in final
        assert final["total_time"] > 0.09
        assert final["total_time"] < 0.2

    def test_finalize_rounds_time(self):
        """Test that finalize rounds times to 3 decimal places."""
        metrics = PerformanceMetrics()
        time.sleep(0.0123)
        final = metrics.finalize()

        # Should be rounded to 3 decimals
        assert len(str(final["total_time"]).split(".")[-1]) <= 3


class TestPerformanceCallbackHandler:
    """Test suite for PerformanceCallbackHandler class."""

    def test_initialization(self):
        """Test callback handler initialization."""
        handler = PerformanceCallbackHandler()
        metrics = handler.get_metrics()

        assert metrics["llm_calls"] == 0
        assert metrics["tool_calls"] == 0
        assert metrics["llm_time"] == 0.0
        assert metrics["token_usage"]["total"] == 0

    def test_llm_call_tracking(self):
        """Test LLM call counting and timing."""
        handler = PerformanceCallbackHandler()

        handler.on_llm_start({}, ["test prompt"])
        time.sleep(0.05)

        # Mock LLMResult with no token usage
        response = Mock()
        response.llm_output = None
        response.generations = []
        handler.on_llm_end(response)

        metrics = handler.get_metrics()
        assert metrics["llm_calls"] == 1
        assert 0.04 < metrics["llm_time"] < 0.1

    def test_multiple_llm_calls(self):
        """Test tracking multiple LLM calls."""
        handler = PerformanceCallbackHandler()

        # First call
        handler.on_llm_start({}, ["prompt 1"])
        time.sleep(0.03)
        response1 = Mock()
        response1.llm_output = None
        response1.generations = []
        handler.on_llm_end(response1)

        # Second call
        handler.on_llm_start({}, ["prompt 2"])
        time.sleep(0.03)
        response2 = Mock()
        response2.llm_output = None
        response2.generations = []
        handler.on_llm_end(response2)

        metrics = handler.get_metrics()
        assert metrics["llm_calls"] == 2
        assert 0.05 < metrics["llm_time"] < 0.15

    def test_llm_token_usage_from_llm_output(self):
        """Test extracting token usage from LLM output."""
        handler = PerformanceCallbackHandler()

        handler.on_llm_start({}, ["test"])

        # Mock response with token usage in llm_output
        response = Mock()
        response.llm_output = {
            "token_usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
        }
        response.generations = []
        handler.on_llm_end(response)

        metrics = handler.get_metrics()
        assert metrics["token_usage"]["input"] == 100
        assert metrics["token_usage"]["output"] == 50
        assert metrics["token_usage"]["total"] == 150

    def test_llm_token_usage_accumulation(self):
        """Test that token usage accumulates across multiple calls."""
        handler = PerformanceCallbackHandler()

        # First call
        handler.on_llm_start({}, ["test"])
        response1 = Mock()
        response1.llm_output = {"token_usage": {"prompt_tokens": 100, "completion_tokens": 50}}
        response1.generations = []
        handler.on_llm_end(response1)

        # Second call
        handler.on_llm_start({}, ["test"])
        response2 = Mock()
        response2.llm_output = {"token_usage": {"prompt_tokens": 200, "completion_tokens": 75}}
        response2.generations = []
        handler.on_llm_end(response2)

        metrics = handler.get_metrics()
        assert metrics["token_usage"]["input"] == 300
        assert metrics["token_usage"]["output"] == 125

    def test_tool_call_tracking(self):
        """Test tool call counting and timing."""
        handler = PerformanceCallbackHandler()

        handler.on_tool_start({"name": "test_tool"}, "input")
        time.sleep(0.05)
        handler.on_tool_end("output", name="test_tool")

        metrics = handler.get_metrics()
        assert metrics["tool_calls"] == 1
        assert "test_tool" in metrics["tool_times"]
        assert len(metrics["tool_times"]["test_tool"]) == 1
        assert 0.04 < metrics["tool_times"]["test_tool"][0] < 0.1

    def test_multiple_tool_calls_same_tool(self):
        """Test tracking multiple calls to the same tool."""
        handler = PerformanceCallbackHandler()

        # First call
        handler.on_tool_start({"name": "geocode"}, "Berlin")
        time.sleep(0.03)
        handler.on_tool_end("result", name="geocode")

        # Second call
        handler.on_tool_start({"name": "geocode"}, "Paris")
        time.sleep(0.03)
        handler.on_tool_end("result", name="geocode")

        metrics = handler.get_metrics()
        assert metrics["tool_calls"] == 2
        assert "geocode" in metrics["tool_times"]
        assert len(metrics["tool_times"]["geocode"]) == 2

    def test_multiple_different_tools(self):
        """Test tracking calls to different tools."""
        handler = PerformanceCallbackHandler()

        handler.on_tool_start({"name": "geocode"}, "input")
        time.sleep(0.02)
        handler.on_tool_end("output", name="geocode")

        handler.on_tool_start({"name": "style_map"}, "input")
        time.sleep(0.02)
        handler.on_tool_end("output", name="style_map")

        metrics = handler.get_metrics()
        assert metrics["tool_calls"] == 2
        assert "geocode" in metrics["tool_times"]
        assert "style_map" in metrics["tool_times"]

    def test_tool_stats_calculation(self):
        """Test that get_metrics calculates tool statistics."""
        handler = PerformanceCallbackHandler()

        # Make 3 calls to same tool with different durations
        for duration in [0.01, 0.02, 0.03]:
            handler.on_tool_start({"name": "test_tool"}, "input")
            time.sleep(duration)
            handler.on_tool_end("output", name="test_tool")

        metrics = handler.get_metrics()
        tool_stats = metrics["tool_stats"]["test_tool"]

        assert tool_stats["calls"] == 3
        assert tool_stats["min_time"] < tool_stats["avg_time"] < tool_stats["max_time"]
        assert tool_stats["total_time"] > 0.05

    def test_llm_error_handling(self):
        """Test that LLM errors are tracked."""
        handler = PerformanceCallbackHandler()

        handler.on_llm_start({}, ["test"])
        handler.on_llm_error(Exception("LLM failed"))

        metrics = handler.get_metrics()
        assert len(metrics["errors"]) == 1
        assert metrics["errors"][0]["type"] == "llm"
        assert "LLM failed" in metrics["errors"][0]["error"]

    def test_tool_error_handling(self):
        """Test that tool errors are tracked."""
        handler = PerformanceCallbackHandler()

        handler.on_tool_start({"name": "broken_tool"}, "input")
        handler.on_tool_error(Exception("Tool failed"), name="broken_tool")

        metrics = handler.get_metrics()
        assert len(metrics["errors"]) == 1
        assert metrics["errors"][0]["type"] == "tool"
        assert metrics["errors"][0]["tool"] == "broken_tool"


class TestExtractTokenUsage:
    """Test suite for extract_token_usage_from_messages function."""

    def test_extract_from_empty_list(self):
        """Test extracting from empty message list."""
        usage = extract_token_usage_from_messages([])
        assert usage["input_tokens"] == 0
        assert usage["output_tokens"] == 0
        assert usage["total_tokens"] == 0

    def test_extract_from_messages_with_response_metadata(self):
        """Test extracting from messages with response_metadata."""
        msg = AIMessage(
            content="Hello",
            response_metadata={
                "token_usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
            },
        )

        usage = extract_token_usage_from_messages([msg])
        assert usage["input_tokens"] == 10
        assert usage["output_tokens"] == 20
        assert usage["total_tokens"] == 30

    def test_extract_from_multiple_messages(self):
        """Test extracting from multiple messages."""
        msg1 = AIMessage(
            content="Hello",
            response_metadata={
                "token_usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
            },
        )
        msg2 = AIMessage(
            content="World",
            response_metadata={
                "token_usage": {"prompt_tokens": 15, "completion_tokens": 25, "total_tokens": 40}
            },
        )

        usage = extract_token_usage_from_messages([msg1, msg2])
        assert usage["input_tokens"] == 25
        assert usage["output_tokens"] == 45
        assert usage["total_tokens"] == 70

    def test_extract_ignores_human_messages(self):
        """Test that human messages without token data don't affect count."""
        msg1 = HumanMessage(content="Hello")
        msg2 = AIMessage(
            content="Hi",
            response_metadata={
                "token_usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
            },
        )

        usage = extract_token_usage_from_messages([msg1, msg2])
        assert usage["input_tokens"] == 10
        assert usage["output_tokens"] == 20

    def test_extract_from_additional_kwargs(self):
        """Test extracting from additional_kwargs."""
        msg = AIMessage(
            content="Hello",
            additional_kwargs={
                "token_usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
            },
        )

        usage = extract_token_usage_from_messages([msg])
        assert usage["input_tokens"] == 10
        assert usage["output_tokens"] == 20
        assert usage["total_tokens"] == 30


class TestPerformanceIntegration:
    """Integration tests for performance monitoring."""

    def test_metrics_and_callback_together(self):
        """Test using PerformanceMetrics and callback handler together."""
        metrics = PerformanceMetrics()
        callback = PerformanceCallbackHandler()

        # Simulate request flow
        metrics.record("message_count_before", 20)
        metrics.record("message_count_after", 10)

        # Simulate agent execution
        metrics.start_timer("agent_execution")

        # Simulate LLM call
        callback.on_llm_start({}, ["test"])
        time.sleep(0.02)
        response = Mock()
        response.llm_output = {"token_usage": {"total_tokens": 100}}
        response.generations = []
        callback.on_llm_end(response)

        # Simulate tool call
        callback.on_tool_start({"name": "geocode"}, "input")
        time.sleep(0.02)
        callback.on_tool_end("output", name="geocode")

        metrics.end_timer("agent_execution")

        # Merge metrics
        metrics.metrics.update(callback.get_metrics())

        final = metrics.finalize()

        # Verify merged metrics
        assert final["message_count_before"] == 20
        assert final["message_count_after"] == 10
        assert final["llm_calls"] == 1
        assert final["tool_calls"] == 1
        assert final["agent_execution"] > 0
        assert final["total_time"] > 0


class TestMetricsStorage:
    """Test suite for MetricsStorage class."""

    def test_initialization(self):
        """Test storage initialization."""
        from utility.metrics_storage import MetricsStorage

        storage = MetricsStorage(max_age_hours=24, max_entries=1000)
        assert storage.get_count() == 0

    def test_store_metrics(self):
        """Test storing metrics."""
        from utility.metrics_storage import MetricsStorage

        storage = MetricsStorage()
        metrics = {"total_time": 5.0, "llm_calls": 2}
        storage.store(session_id="test123", metrics=metrics)

        assert storage.get_count() == 1

    def test_get_recent(self):
        """Test retrieving recent metrics."""
        from utility.metrics_storage import MetricsStorage

        storage = MetricsStorage()

        # Store some metrics
        for i in range(5):
            storage.store(session_id=f"session{i}", metrics={"total_time": i + 1.0})

        recent = storage.get_recent(hours=1)
        assert len(recent) == 5

    def test_get_recent_with_session_filter(self):
        """Test filtering recent metrics by session ID."""
        from utility.metrics_storage import MetricsStorage

        storage = MetricsStorage()

        # Store metrics for different sessions
        storage.store(session_id="session1", metrics={"total_time": 1.0})
        storage.store(session_id="session1", metrics={"total_time": 2.0})
        storage.store(session_id="session2", metrics={"total_time": 3.0})

        recent = storage.get_recent(hours=1, session_id="session1")
        assert len(recent) == 2

    def test_cleanup_old_entries(self):
        """Test cleanup of old metrics entries."""
        from utility.metrics_storage import MetricsStorage

        # Use very short max_age (0.0001 hours = 0.36 seconds)
        storage = MetricsStorage(max_age_hours=0.0001, max_entries=1000)

        # Store metrics
        storage.store(session_id="test", metrics={"total_time": 1.0})
        assert storage.get_count() == 1

        # Wait for expiry (0.5 seconds > 0.36 seconds max_age)
        time.sleep(0.5)

        # Trigger cleanup
        storage._cleanup()

        # Old entry should be removed
        assert storage.get_count() == 0

    def test_max_entries_limit(self):
        """Test that max_entries limit is enforced."""
        from utility.metrics_storage import MetricsStorage

        storage = MetricsStorage(max_entries=10)

        # Store more than max_entries
        for i in range(15):
            storage.store(session_id=f"session{i}", metrics={"total_time": i + 1.0})

        # Should only keep most recent 10
        assert storage.get_count() == 10

    def test_clear(self):
        """Test clearing all metrics."""
        from utility.metrics_storage import MetricsStorage

        storage = MetricsStorage()
        storage.store(session_id="test", metrics={"total_time": 1.0})
        assert storage.get_count() == 1

        storage.clear()
        assert storage.get_count() == 0

    def test_get_statistics_empty(self):
        """Test statistics with no data."""
        from utility.metrics_storage import MetricsStorage

        storage = MetricsStorage()
        stats = storage.get_statistics(hours=1)

        assert stats["total_requests"] == 0
        assert "error" in stats

    def test_get_statistics_with_data(self):
        """Test statistics calculation."""
        from utility.metrics_storage import MetricsStorage

        storage = MetricsStorage()

        # Store test metrics
        for i in range(3):
            metrics = {
                "total_time": (i + 1) * 1.0,
                "agent_execution": (i + 1) * 0.8,
                "llm_calls": 2,
                "llm_time": (i + 1) * 0.5,
                "tool_calls": 1,
                "token_usage": {"total": (i + 1) * 100},
                "message_reduction": i * 5,
                "errors": [],
            }
            storage.store(session_id=f"session{i}", metrics=metrics)

        stats = storage.get_statistics(hours=1)

        assert stats["total_requests"] == 3
        assert stats["response_time"]["min"] == 1.0
        assert stats["response_time"]["max"] == 3.0
        assert stats["llm"]["total_calls"] == 6
        assert stats["tools"]["total_calls"] == 3
        assert stats["tokens"]["total"] == 600

    def test_calculate_stats(self):
        """Test statistical calculations."""
        from utility.metrics_storage import MetricsStorage

        storage = MetricsStorage()
        values = [1.0, 2.0, 3.0, 4.0, 5.0]

        stats = storage._calculate_stats(values)

        assert stats["min"] == 1.0
        assert stats["max"] == 5.0
        assert stats["avg"] == 3.0
        assert stats["median"] == 3.0

    def test_get_top_tools(self):
        """Test top tools calculation."""
        from utility.metrics_storage import MetricsStorage

        storage = MetricsStorage()

        # Store metrics with tool stats
        for i in range(3):
            metrics = {
                "tool_stats": {
                    "geocode": {"calls": 2, "avg_time": 0.5, "total_time": 1.0},
                    "buffer": {"calls": 1, "avg_time": 1.0, "total_time": 1.0},
                }
            }
            storage.store(session_id=f"session{i}", metrics=metrics)

        stats = storage.get_statistics(hours=1)
        top_tools = stats["tools"]["top_tools"]

        assert len(top_tools) == 2
        assert top_tools[0]["name"] == "geocode"  # Most calls
        assert top_tools[0]["total_calls"] == 6

    def test_get_metrics_storage_singleton(self):
        """Test that get_metrics_storage returns singleton."""
        from utility.metrics_storage import get_metrics_storage

        storage1 = get_metrics_storage()
        storage2 = get_metrics_storage()

        assert storage1 is storage2
