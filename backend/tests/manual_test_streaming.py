"""
Manual test script for the /chat/stream SSE endpoint.
Run this with: poetry run python tests/manual_test_streaming.py
"""

import asyncio
import json
import sys
from pathlib import Path

import httpx
from httpx_sse import aconnect_sse

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_streaming_endpoint():
    """Test the /chat/stream endpoint with a simple query."""

    # Minimal test payload
    payload = {
        "messages": [],
        "query": "Show me rivers in Germany",
        "geodata_last_results": [],
        "geodata_layers": [],
        "options": {
            "model_settings": {
                "llm_provider": "openai",
                "model_name": "gpt-4o-mini",
                "enable_performance_metrics": True,
            },
            "tools": {
                "overpass_search": {"enabled": True},
            },
            "session_id": "test-streaming-session",
        },
    }

    url = "http://localhost:8000/chat/stream"

    print(f"🚀 Testing streaming endpoint: {url}")
    print(f"📤 Payload: {json.dumps(payload, indent=2)}\n")

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with aconnect_sse(client, "POST", url, json=payload) as event_source:
                event_count = 0
                async for sse in event_source.aiter_sse():
                    event_count += 1
                    event_type = sse.event or "message"

                    try:
                        data = json.loads(sse.data)

                        if event_type == "tool_start":
                            print(f"🔧 Tool Started: {data.get('tool', 'unknown')}")

                        elif event_type == "tool_end":
                            tool_name = data.get("tool", "unknown")
                            output_preview = data.get("output", "")[:100]
                            print(f"✅ Tool Completed: {tool_name}")
                            print(f"   Output preview: {output_preview}...")

                        elif event_type == "llm_token":
                            token = data.get("token", "")
                            print(token, end="", flush=True)

                        elif event_type == "result":
                            print("\n\n📊 Final Result Received")
                            messages_count = len(data.get("messages", []))
                            results_count = len(data.get("geodata_results", []))
                            layers_count = len(data.get("geodata_layers", []))
                            print(f"   Messages: {messages_count}")
                            print(f"   GeoData Results: {results_count}")
                            print(f"   GeoData Layers: {layers_count}")
                            if "metrics" in data:
                                metrics = data["metrics"]
                                exec_time = metrics.get("agent_execution_time", 0)
                                token_total = metrics.get("token_usage", {}).get("total", 0)
                                print(f"   Agent Execution Time: {exec_time:.2f}s")
                                print(f"   Token Usage: {token_total}")

                        elif event_type == "error":
                            print(f"\n❌ Error: {data.get('error', 'unknown')}")
                            print(f"   Message: {data.get('message', '')}")

                        elif event_type == "done":
                            status = data.get("status", "unknown")
                            print(f"\n\n✨ Stream Complete: {status}")
                            print(f"   Total events received: {event_count}")

                    except json.JSONDecodeError as e:
                        print(f"\n⚠️ Failed to parse event data: {e}")
                        print(f"   Raw data: {sse.data}")

    except httpx.ConnectError:
        print("❌ Connection Error: Is the backend running on http://localhost:8000?")
        print("   Start it with: cd backend && poetry run python main.py")
        return False

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return False

    print("\n✅ Streaming test completed successfully!")
    return True


if __name__ == "__main__":
    print("=" * 70)
    print("SSE Streaming Endpoint Test")
    print("=" * 70)
    print()

    success = asyncio.run(test_streaming_endpoint())

    sys.exit(0 if success else 1)
