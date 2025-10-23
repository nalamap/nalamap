"""
In-memory metrics storage for performance monitoring.

Provides storage, retrieval, and aggregation of historical performance metrics.
"""

import time
import logging
from typing import Any, Dict, List, Optional, Union
from collections import defaultdict
from datetime import datetime
import statistics

logger = logging.getLogger(__name__)


class MetricsStorage:
    """In-memory storage for performance metrics.

    Stores metrics with automatic cleanup of old data.
    Provides aggregation and statistical analysis.

    Example:
        >>> storage = MetricsStorage(max_age_hours=24)
        >>> storage.store(session_id="abc123", metrics={...})
        >>> recent = storage.get_recent(hours=1)
        >>> stats = storage.get_statistics(hours=24)
    """

    def __init__(self, max_age_hours: Union[int, float] = 24, max_entries: int = 10000):
        """Initialize metrics storage.

        Args:
            max_age_hours: Maximum age of metrics to keep (hours)
            max_entries: Maximum number of metric entries to store
        """
        self.max_age_seconds = max_age_hours * 3600
        self.max_entries = max_entries
        self._metrics: List[Dict[str, Any]] = []
        self._last_cleanup = time.time()
        logger.info(
            f"Initialized metrics storage (max_age={max_age_hours}h, max_entries={max_entries})"
        )

    def store(self, session_id: str, metrics: Dict[str, Any]) -> None:
        """Store metrics for a session.

        Args:
            session_id: Unique session identifier
            metrics: Performance metrics dictionary
        """
        entry = {
            "session_id": session_id,
            "timestamp": time.time(),
            "datetime": datetime.utcnow().isoformat(),
            "metrics": metrics,
        }

        self._metrics.append(entry)

        # Periodic cleanup
        if len(self._metrics) > self.max_entries or (time.time() - self._last_cleanup > 3600):
            self._cleanup()

        logger.debug(
            f"Stored metrics for session {session_id} (total entries: {len(self._metrics)})"
        )

    def _cleanup(self) -> None:
        """Remove old metrics entries."""
        cutoff_time = time.time() - self.max_age_seconds
        original_count = len(self._metrics)

        self._metrics = [m for m in self._metrics if m["timestamp"] > cutoff_time]

        # If still too many, keep only the most recent
        if len(self._metrics) > self.max_entries:
            self._metrics = sorted(self._metrics, key=lambda x: x["timestamp"])[-self.max_entries :]

        removed = original_count - len(self._metrics)
        if removed > 0:
            logger.info(f"Cleaned up {removed} old metrics entries")

        self._last_cleanup = time.time()

    def get_recent(self, hours: int = 1, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent metrics entries.

        Args:
            hours: Number of hours to look back
            session_id: Optional filter by session ID

        Returns:
            List of metrics entries
        """
        cutoff_time = time.time() - (hours * 3600)
        recent = [m for m in self._metrics if m["timestamp"] > cutoff_time]

        if session_id:
            recent = [m for m in recent if m["session_id"] == session_id]

        return recent

    def get_all(self) -> List[Dict[str, Any]]:
        """Get all stored metrics entries.

        Returns:
            List of all metrics entries
        """
        return self._metrics.copy()

    def get_statistics(self, hours: int = 24, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Calculate aggregated statistics for recent metrics.

        Args:
            hours: Number of hours to analyze
            session_id: Optional filter by session ID

        Returns:
            Dictionary with aggregated statistics
        """
        recent = self.get_recent(hours=hours, session_id=session_id)

        if not recent:
            return {
                "period_hours": hours,
                "total_requests": 0,
                "error": "No metrics available for this period",
            }

        # Extract metric values
        total_times = []
        agent_times = []
        llm_calls = []
        llm_times = []
        tool_calls = []
        token_totals = []
        message_reductions = []
        errors_count = 0
        tool_stats_all = defaultdict(list)
        tool_usage_all = defaultdict(lambda: {"invocations": 0, "successes": 0, "failures": 0})
        tool_selector_metrics = {"selections": [], "tools_selected": [], "fallbacks": 0}

        for entry in recent:
            m = entry["metrics"]

            if "total_time" in m:
                total_times.append(m["total_time"])
            if "agent_execution" in m:
                agent_times.append(m["agent_execution"])
            if "llm_calls" in m:
                llm_calls.append(m["llm_calls"])
            if "llm_time" in m:
                llm_times.append(m["llm_time"])
            if "tool_calls" in m:
                tool_calls.append(m["tool_calls"])
            if "token_usage" in m and "total" in m["token_usage"]:
                token_totals.append(m["token_usage"]["total"])
            if "message_reduction" in m:
                message_reductions.append(m["message_reduction"])
            if "errors" in m:
                errors_count += len(m["errors"])

            # Tool statistics
            if "tool_stats" in m:
                for tool_name, stats in m["tool_stats"].items():
                    tool_stats_all[tool_name].append(stats)

            # Tool usage tracking (Week 3)
            if "tool_usage" in m:
                for tool_name, usage in m["tool_usage"].items():
                    tool_usage_all[tool_name]["invocations"] += usage.get("invocations", 0)
                    tool_usage_all[tool_name]["successes"] += usage.get("successes", 0)
                    tool_usage_all[tool_name]["failures"] += usage.get("failures", 0)

            # Tool selector metrics (Week 3)
            if "tool_selector" in m:
                sel = m["tool_selector"]
                if "total_selections" in sel and sel["total_selections"] > 0:
                    tool_selector_metrics["selections"].append(sel["avg_selection_time_ms"])
                    tool_selector_metrics["tools_selected"].append(sel["avg_tools_selected"])
                    tool_selector_metrics["fallbacks"] += sel.get("fallback_count", 0)

        # Calculate statistics
        stats = {
            "period_hours": hours,
            "total_requests": len(recent),
            "time_range": {
                "start": datetime.fromtimestamp(recent[0]["timestamp"]).isoformat(),
                "end": datetime.fromtimestamp(recent[-1]["timestamp"]).isoformat(),
            },
            "response_time": self._calculate_stats(total_times, "seconds"),
            "agent_execution_time": self._calculate_stats(agent_times, "seconds"),
            "llm": {
                "total_calls": sum(llm_calls) if llm_calls else 0,
                "avg_calls_per_request": (statistics.mean(llm_calls) if llm_calls else 0),
                "total_time": sum(llm_times) if llm_times else 0,
                "time_stats": self._calculate_stats(llm_times, "seconds"),
            },
            "tools": {
                "total_calls": sum(tool_calls) if tool_calls else 0,
                "avg_calls_per_request": (statistics.mean(tool_calls) if tool_calls else 0),
                "top_tools": self._get_top_tools(tool_stats_all),
            },
            "tool_usage": self._get_tool_usage_stats(tool_usage_all),
            "tool_selector": self._get_tool_selector_stats(tool_selector_metrics),
            "tokens": {
                "total": sum(token_totals) if token_totals else 0,
                "avg_per_request": (statistics.mean(token_totals) if token_totals else 0),
                "stats": self._calculate_stats(token_totals, "tokens"),
            },
            "message_pruning": {
                "total_reduction": (sum(message_reductions) if message_reductions else 0),
                "avg_reduction": (statistics.mean(message_reductions) if message_reductions else 0),
            },
            "errors": {"total": errors_count, "rate": errors_count / len(recent)},
        }

        return stats

    def _calculate_stats(self, values: List[float], unit: str = "") -> Dict[str, float]:
        """Calculate statistical measures for a list of values.

        Args:
            values: List of numeric values
            unit: Optional unit label

        Returns:
            Dictionary with min, max, avg, median, p50, p95, p99
        """
        if not values:
            return {
                "min": 0,
                "max": 0,
                "avg": 0,
                "median": 0,
                "p50": 0,
                "p95": 0,
                "p99": 0,
            }

        sorted_values = sorted(values)
        n = len(sorted_values)

        return {
            "min": round(min(values), 3),
            "max": round(max(values), 3),
            "avg": round(statistics.mean(values), 3),
            "median": round(statistics.median(values), 3),
            "p50": round(sorted_values[int(n * 0.5)], 3),
            "p95": round(sorted_values[int(n * 0.95)] if n > 1 else max(values), 3),
            "p99": round(sorted_values[int(n * 0.99)] if n > 1 else max(values), 3),
        }

    def _get_top_tools(
        self, tool_stats_all: Dict[str, List[Dict]], limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get top tools by call count.

        Args:
            tool_stats_all: Dictionary of tool statistics
            limit: Maximum number of tools to return

        Returns:
            List of top tools with aggregated statistics
        """
        top_tools = []

        for tool_name, stats_list in tool_stats_all.items():
            total_calls = sum(s["calls"] for s in stats_list)
            all_times = []
            for s in stats_list:
                all_times.extend([s["avg_time"]] * s["calls"])

            tool_info = {
                "name": tool_name,
                "total_calls": total_calls,
                "avg_time": round(statistics.mean(all_times), 3) if all_times else 0,
                "min_time": round(min(all_times), 3) if all_times else 0,
                "max_time": round(max(all_times), 3) if all_times else 0,
            }
            top_tools.append(tool_info)

        # Sort by total calls
        top_tools.sort(key=lambda x: x["total_calls"], reverse=True)
        return top_tools[:limit]

    def _get_tool_usage_stats(
        self, tool_usage_all: Dict[str, Dict[str, int]], limit: int = 20
    ) -> Dict[str, Any]:
        """Get tool usage statistics (Week 3 - Tool Usage Analytics).

        Args:
            tool_usage_all: Aggregated tool usage data
            limit: Maximum number of tools to return

        Returns:
            Dictionary with tool usage statistics
        """
        if not tool_usage_all:
            return {
                "top_tools": [],
                "total_invocations": 0,
                "success_rate": 0.0,
            }

        # Calculate total invocations and success rate
        total_invocations = sum(t["invocations"] for t in tool_usage_all.values())
        total_successes = sum(t["successes"] for t in tool_usage_all.values())
        total_failures = sum(t["failures"] for t in tool_usage_all.values())

        success_rate = (
            round(total_successes / total_invocations, 3) if total_invocations > 0 else 0.0
        )

        # Build top tools list
        top_tools = []
        for tool_name, usage in tool_usage_all.items():
            inv = usage["invocations"]
            tool_success_rate = round(usage["successes"] / inv, 3) if inv > 0 else 0.0
            top_tools.append(
                {
                    "name": tool_name,
                    "invocations": inv,
                    "successes": usage["successes"],
                    "failures": usage["failures"],
                    "success_rate": tool_success_rate,
                }
            )

        # Sort by invocation count
        top_tools.sort(key=lambda x: x["invocations"], reverse=True)

        return {
            "top_tools": top_tools[:limit],
            "total_invocations": total_invocations,
            "total_successes": total_successes,
            "total_failures": total_failures,
            "success_rate": success_rate,
        }

    def _get_tool_selector_stats(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Get tool selector statistics (Week 3 - Performance Monitoring).

        Args:
            metrics: Tool selector metrics data

        Returns:
            Dictionary with tool selector statistics
        """
        if not metrics["selections"]:
            return {
                "enabled": False,
                "avg_selection_time_ms": 0.0,
                "avg_tools_selected": 0.0,
                "fallback_count": 0,
                "fallback_rate": 0.0,
            }

        return {
            "enabled": True,
            "avg_selection_time_ms": round(statistics.mean(metrics["selections"]), 2),
            "avg_tools_selected": round(statistics.mean(metrics["tools_selected"]), 2),
            "fallback_count": metrics["fallbacks"],
            "fallback_rate": (
                round(metrics["fallbacks"] / len(metrics["selections"]), 3)
                if metrics["selections"]
                else 0.0
            ),
        }

    def clear(self) -> None:
        """Clear all stored metrics."""
        count = len(self._metrics)
        self._metrics = []
        logger.info(f"Cleared {count} metrics entries")

    def get_count(self) -> int:
        """Get current number of stored metrics entries.

        Returns:
            Number of entries
        """
        return len(self._metrics)


# Global storage instance
_storage: Optional[MetricsStorage] = None


def get_metrics_storage() -> MetricsStorage:
    """Get or create the global metrics storage instance.

    Returns:
        MetricsStorage instance
    """
    global _storage
    if _storage is None:
        _storage = MetricsStorage(max_age_hours=24, max_entries=10000)
    return _storage
