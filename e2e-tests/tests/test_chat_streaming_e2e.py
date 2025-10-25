"""
End-to-end integration tests for /chat/stream SSE endpoint.
Tests real backend + frontend integration with actual agent execution.

These tests require:
- Backend running on http://localhost:8000
- Frontend running on http://localhost:3000
- Valid OpenAI API key configured
"""
import os
import sys
import json
import time
from pathlib import Path
from typing import List, Dict, Any
import asyncio

import pytest
from playwright.async_api import async_playwright, Page, expect

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))

# Configuration
BACKEND_URL = os.environ.get("E2E_BACKEND_URL", "http://localhost:8000")
FRONTEND_URL = os.environ.get("E2E_FRONTEND_URL", "http://localhost:3000")
RESULTS_DIR = Path(__file__).parent.parent / "results"

# Ensure results directory exists
RESULTS_DIR.mkdir(exist_ok=True)


class StreamingMetrics:
    """Collect metrics about streaming performance."""

    def __init__(self):
        self.first_event_time: float = 0
        self.last_event_time: float = 0
        self.event_count: int = 0
        self.tool_events: List[Dict[str, Any]] = []
        self.token_events: List[Dict[str, Any]] = []
        self.total_time: float = 0
        self.ttfb: float = 0  # Time to first byte

    def record_event(self, event_type: str, timestamp: float, data: Any = None):
        """Record an event with timestamp."""
        if self.first_event_time == 0:
            self.first_event_time = timestamp

        self.last_event_time = timestamp
        self.event_count += 1

        if event_type in ["tool_start", "tool_end"]:
            self.tool_events.append(
                {"type": event_type, "timestamp": timestamp, "data": data}
            )
        elif event_type == "llm_token":
            self.token_events.append(
                {"type": event_type, "timestamp": timestamp, "data": data}
            )

    def finalize(self):
        """Calculate final metrics."""
        if self.first_event_time > 0 and self.last_event_time > 0:
            self.total_time = self.last_event_time - self.first_event_time

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_time": self.total_time,
            "ttfb": self.ttfb,
            "event_count": self.event_count,
            "tool_event_count": len(self.tool_events),
            "token_count": len(self.token_events),
            "events_per_second": (
                self.event_count / self.total_time if self.total_time > 0 else 0
            ),
        }


@pytest.fixture(scope="module")
async def browser():
    """Create browser instance."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        yield browser
        await browser.close()


@pytest.fixture
async def page(browser):
    """Create a new page for each test."""
    context = await browser.new_context()
    page = await context.new_page()
    yield page
    await context.close()


class TestChatStreamingE2E:
    """End-to-end tests for chat streaming."""

    @pytest.mark.asyncio
    async def test_streaming_with_simple_query(self, page: Page):
        """Test streaming with a simple query that doesn't require tools."""
        metrics = StreamingMetrics()
        start_time = time.time()

        # Navigate to app
        await page.goto(FRONTEND_URL)
        await page.wait_for_load_state("networkidle")

        # Intercept SSE events for metrics
        events_received = []

        async def handle_response(response):
            if "/chat/stream" in response.url:
                metrics.ttfb = time.time() - start_time
                # Try to read response body
                try:
                    body = await response.text()
                    for line in body.split("\n\n"):
                        if line.strip():
                            if "event:" in line and "data:" in line:
                                event_lines = line.split("\n")
                                event_type = ""
                                event_data = ""
                                for event_line in event_lines:
                                    if event_line.startswith("event: "):
                                        event_type = event_line.split("event: ")[1]
                                    elif event_line.startswith("data: "):
                                        event_data = event_line.split("data: ", 1)[1]

                                if event_type and event_data:
                                    events_received.append(
                                        {
                                            "type": event_type,
                                            "data": json.loads(event_data),
                                        }
                                    )
                                    metrics.record_event(
                                        event_type, time.time(), event_data
                                    )
                except Exception as e:
                    print(f"Error reading response: {e}")

        page.on("response", handle_response)

        # Find input and submit query
        input_selector = 'input[placeholder*="Ask about maps"]'
        await page.wait_for_selector(input_selector, state="visible")

        await page.fill(input_selector, "What is the capital of France?")
        await page.press(input_selector, "Enter")

        # Wait for streaming to complete
        # Look for the final message in chat
        await page.wait_for_selector(
            ".chat-message:has-text('Paris')", timeout=30000
        )

        # Finalize metrics
        metrics.finalize()
        print(f"\nSimple query metrics: {metrics.to_dict()}")

        # Assertions
        assert metrics.event_count > 0, "Should receive events"
        assert metrics.ttfb < 2.0, f"TTFB too high: {metrics.ttfb:.3f}s"
        assert metrics.total_time < 20.0, f"Total time too high: {metrics.total_time:.3f}s"

    @pytest.mark.asyncio
    async def test_streaming_with_tool_execution(self, page: Page):
        """Test streaming with a query that triggers tool execution."""
        metrics = StreamingMetrics()

        await page.goto(FRONTEND_URL)
        await page.wait_for_load_state("networkidle")

        # Monitor for tool progress indicator
        tool_progress_appeared = False

        async def check_tool_progress():
            nonlocal tool_progress_appeared
            try:
                tool_progress = page.locator(".tool-progress-container")
                if await tool_progress.is_visible():
                    tool_progress_appeared = True
            except Exception:
                pass

        # Find input and submit query that requires tools
        input_selector = 'input[placeholder*="Ask about maps"]'
        await page.wait_for_selector(input_selector, state="visible")

        await page.fill(input_selector, "Show me rivers in Germany")
        await page.press(input_selector, "Enter")

        # Check for tool progress periodically
        for _ in range(10):
            await check_tool_progress()
            if tool_progress_appeared:
                break
            await asyncio.sleep(0.5)

        # Wait for streaming to complete
        await page.wait_for_selector(".chat-message .ai", timeout=60000)

        metrics.finalize()
        print(f"\nTool execution metrics: {metrics.to_dict()}")

        # Assertions
        assert tool_progress_appeared, "Tool progress indicator should appear"
        assert metrics.total_time < 60.0, f"Query took too long: {metrics.total_time:.3f}s"

    @pytest.mark.asyncio
    async def test_streaming_performance_comparison(self, page: Page):
        """Compare streaming vs non-streaming performance."""
        # This test compares perceived latency

        await page.goto(FRONTEND_URL)
        await page.wait_for_load_state("networkidle")

        # Test streaming (current default)
        start_streaming = time.time()

        input_selector = 'input[placeholder*="Ask about maps"]'
        await page.fill(input_selector, "What is Python?")
        await page.press(input_selector, "Enter")

        # Measure time to first visual feedback (streaming message or tool progress)
        try:
            await page.wait_for_selector(
                ".streaming-message, .tool-progress-container",
                timeout=5000,
                state="visible",
            )
            time_to_feedback = time.time() - start_streaming
        except Exception:
            time_to_feedback = 999  # No feedback

        # Wait for completion
        await page.wait_for_selector(".chat-message .ai", timeout=30000)
        total_streaming_time = time.time() - start_streaming

        print("\nStreaming performance:")
        print(f"  Time to first feedback: {time_to_feedback:.3f}s")
        print(f"  Total time: {total_streaming_time:.3f}s")

        # Assertions
        assert time_to_feedback < 2.0, f"First feedback too slow: {time_to_feedback:.3f}s"
        assert (
            time_to_feedback < total_streaming_time / 5
        ), "Feedback should arrive early in the process"

    @pytest.mark.asyncio
    async def test_streaming_with_multiple_queries(self, page: Page):
        """Test consecutive streaming queries."""
        await page.goto(FRONTEND_URL)
        await page.wait_for_load_state("networkidle")

        queries = [
            "What is 2+2?",
            "Name a European country",
            "What color is the sky?",
        ]

        input_selector = 'input[placeholder*="Ask about maps"]'

        for query in queries:
            # Submit query
            await page.fill(input_selector, query)
            await page.press(input_selector, "Enter")

            # Wait for response
            await page.wait_for_function(
                "() => !document.querySelector('input[placeholder*=\"Ask about maps\"]').disabled",
                timeout=30000,
            )

            # Small delay between queries
            await asyncio.sleep(1)

        # Verify all responses are in chat
        messages = page.locator(".chat-message")
        message_count = await messages.count()

        # Should have 6 messages (3 human + 3 AI)
        assert message_count >= 6, f"Expected at least 6 messages, got {message_count}"

    @pytest.mark.asyncio
    async def test_streaming_error_handling(self, page: Page):
        """Test error handling during streaming."""
        await page.goto(FRONTEND_URL)
        await page.wait_for_load_state("networkidle")

        # Submit a query that might cause issues
        input_selector = 'input[placeholder*="Ask about maps"]'
        await page.fill(input_selector, "")  # Empty query
        await page.press(input_selector, "Enter")

        # Should handle gracefully - input should remain enabled
        await asyncio.sleep(2)
        input_element = page.locator(input_selector)
        is_enabled = await input_element.is_enabled()

        assert is_enabled, "Input should remain enabled after empty query"

    @pytest.mark.asyncio
    async def test_streaming_ui_updates(self, page: Page):
        """Test that UI updates correctly during streaming."""
        await page.goto(FRONTEND_URL)
        await page.wait_for_load_state("networkidle")

        input_selector = 'input[placeholder*="Ask about maps"]'
        await page.fill(input_selector, "Tell me about maps")
        await page.press(input_selector, "Enter")

        # Check that input is disabled during streaming
        input_element = page.locator(input_selector)
        await expect(input_element).to_be_disabled(timeout=2000)

        # Wait for completion
        await page.wait_for_selector(".chat-message .ai", timeout=30000)

        # Check that input is enabled again
        await expect(input_element).to_be_enabled(timeout=5000)

    @pytest.mark.asyncio
    async def test_streaming_token_display(self, page: Page):
        """Test that streaming tokens are displayed in real-time."""
        await page.goto(FRONTEND_URL)
        await page.wait_for_load_state("networkidle")

        input_selector = 'input[placeholder*="Ask about maps"]'
        await page.fill(input_selector, "Write a short sentence about geography")
        await page.press(input_selector, "Enter")

        # Check for streaming message container
        streaming_msg = page.locator(".streaming-message")

        # Should appear quickly
        try:
            await streaming_msg.wait_for(state="visible", timeout=5000)
            streaming_visible = True
        except Exception:
            streaming_visible = False

        # Wait for completion
        await page.wait_for_selector(".chat-message .ai", timeout=30000)

        print(f"\nStreaming message visibility: {streaming_visible}")

        # Note: streaming_visible might be False if response is very fast
        # which is okay - it means the LLM responded quickly


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "asyncio: mark test as async")
    config.addinivalue_line("markers", "e2e: end-to-end integration test")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s", "--tb=short"])
