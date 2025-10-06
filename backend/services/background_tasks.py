"""Background task manager with priority-based thread pools for GeoServer processing.

This module provides a thread pool system that prioritizes user queries over
preprocessing tasks. It automatically configures itself based on available CPU cores
and ensures user requests always have dedicated threads available.
"""

from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from enum import IntEnum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class TaskPriority(IntEnum):
    """Priority levels for background tasks. Lower values = higher priority."""

    HIGH = 0  # User queries - always prioritized
    NORMAL = 1  # Background tasks that should complete reasonably fast
    LOW = 2  # Preprocessing tasks (embedding, preloading) - can be delayed


class BackgroundTaskManager:
    """Manages background tasks with priority queues and dedicated thread pools.

    Architecture:
    - High-priority pool: Guaranteed threads for user queries
    - Low-priority pool: Shared pool for preprocessing tasks
    - Tasks are executed based on priority to prevent preprocessing from blocking users
    """

    _instance: Optional[BackgroundTaskManager] = None
    _lock = threading.Lock()

    def __new__(cls) -> BackgroundTaskManager:
        """Singleton pattern to ensure only one task manager exists."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize thread pools based on CPU count and configuration."""
        if self._initialized:
            return

        # Get CPU count
        cpu_count = os.cpu_count() or 2
        logger.info(f"Detected {cpu_count} CPU cores")

        # Configure thread pool sizes from environment or use defaults
        # High priority: Reserve at least 25% of cores (min 1, max 4) for user queries
        env_high = os.getenv("NALAMAP_HIGH_PRIORITY_THREADS", "")
        if env_high and env_high.strip():
            high_priority_threads = int(env_high)
        else:
            high_priority_threads = max(1, min(4, cpu_count // 4))

        # Low priority: Use remaining cores for preprocessing (min 1)
        env_low = os.getenv("NALAMAP_LOW_PRIORITY_THREADS", "")
        if env_low and env_low.strip():
            low_priority_threads = int(env_low)
        else:
            low_priority_threads = max(1, cpu_count - high_priority_threads)

        # Maximum concurrent preprocessing tasks (to prevent memory issues)
        env_max = os.getenv("NALAMAP_MAX_CONCURRENT_PRELOADS", "")
        if env_max and env_max.strip():
            max_concurrent_preloads = int(env_max)
        else:
            max_concurrent_preloads = 3

        logger.info(
            f"Initializing thread pools: {high_priority_threads} high-priority, "
            f"{low_priority_threads} low-priority threads, "
            f"max {max_concurrent_preloads} concurrent preloads"
        )

        # Create thread pools
        self._high_priority_executor = ThreadPoolExecutor(
            max_workers=high_priority_threads,
            thread_name_prefix="high-priority-",
        )

        self._low_priority_executor = ThreadPoolExecutor(
            max_workers=low_priority_threads,
            thread_name_prefix="low-priority-",
        )

        # Semaphore to limit concurrent preprocessing tasks
        self._preload_semaphore = threading.Semaphore(max_concurrent_preloads)

        # Track active tasks
        self._active_tasks: dict[str, Any] = {}
        self._task_lock = threading.Lock()

        self._initialized = True

    def submit_task(
        self,
        func: Callable,
        *args,
        priority: TaskPriority = TaskPriority.NORMAL,
        task_id: Optional[str] = None,
        **kwargs,
    ):
        """Submit a task to the appropriate thread pool based on priority.

        Args:
            func: The function to execute
            *args: Positional arguments for the function
            priority: Task priority level
            task_id: Optional unique identifier for tracking the task
            **kwargs: Keyword arguments for the function

        Returns:
            Future object representing the task execution
        """
        # Choose executor based on priority
        if priority == TaskPriority.HIGH:
            executor = self._high_priority_executor
        else:
            executor = self._low_priority_executor

        # For preprocessing tasks, acquire semaphore first
        if priority == TaskPriority.LOW:

            def wrapped_func(*args, **kwargs):
                with self._preload_semaphore:
                    return func(*args, **kwargs)

            future = executor.submit(wrapped_func, *args, **kwargs)
        else:
            future = executor.submit(func, *args, **kwargs)

        # Track task if ID provided
        if task_id:
            with self._task_lock:
                self._active_tasks[task_id] = {
                    "future": future,
                    "priority": priority,
                    "func": func.__name__,
                }

        return future

    def get_task_status(self, task_id: str) -> Optional[dict]:
        """Get the status of a tracked task.

        Args:
            task_id: The task identifier

        Returns:
            Dict with task status or None if not found
        """
        with self._task_lock:
            if task_id not in self._active_tasks:
                return None

            task = self._active_tasks[task_id]
            future = task["future"]

            return {
                "task_id": task_id,
                "priority": task["priority"].name,
                "function": task["func"],
                "running": future.running(),
                "done": future.done(),
                "cancelled": future.cancelled(),
            }

    def remove_task(self, task_id: str):
        """Remove a completed task from tracking.

        Args:
            task_id: The task identifier
        """
        with self._task_lock:
            if task_id in self._active_tasks:
                del self._active_tasks[task_id]

    def get_stats(self) -> dict:
        """Get statistics about the thread pools and active tasks.

        Returns:
            Dict with pool statistics
        """
        with self._task_lock:
            active_high = sum(
                1
                for t in self._active_tasks.values()
                if t["priority"] == TaskPriority.HIGH and t["future"].running()
            )
            active_low = sum(
                1
                for t in self._active_tasks.values()
                if t["priority"] == TaskPriority.LOW and t["future"].running()
            )

            return {
                "high_priority_threads": self._high_priority_executor._max_workers,
                "low_priority_threads": self._low_priority_executor._max_workers,
                "active_high_priority_tasks": active_high,
                "active_low_priority_tasks": active_low,
                "total_tracked_tasks": len(self._active_tasks),
            }

    def shutdown(self, wait: bool = True):
        """Shutdown all thread pools.

        Args:
            wait: Whether to wait for tasks to complete
        """
        logger.info("Shutting down background task manager")
        self._high_priority_executor.shutdown(wait=wait)
        self._low_priority_executor.shutdown(wait=wait)


# Global singleton instance
_task_manager: Optional[BackgroundTaskManager] = None


def get_task_manager() -> BackgroundTaskManager:
    """Get the global background task manager instance.

    Returns:
        The singleton BackgroundTaskManager instance
    """
    global _task_manager
    if _task_manager is None:
        _task_manager = BackgroundTaskManager()
    return _task_manager
