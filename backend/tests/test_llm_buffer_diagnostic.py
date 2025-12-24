"""
Diagnostic script to test the full geoprocessing pipeline end-to-end.

This script tests buffer operations by making actual LLM calls to see
if the issue is with the LLM not understanding the radius parameter.
"""

import asyncio
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.ai.llm_config import get_llm  # noqa: E402
from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402


@pytest.mark.asyncio
async def test_llm_buffer_understanding():
    """Test if the LLM correctly understands buffer requests."""

    llm = get_llm()

    # Test different variations of buffer requests
    test_queries = [
        "buffer by 100 meters",
        "create a 500 meter buffer",
        "buffer this layer with a distance of 1 km",
        "buffer by 1000m",
        "make a 2 kilometer buffer zone",
    ]

    available_ops = [
        (
            "operation: buffer params: radius=<number>, "
            "radius_unit=<meters|kilometers|miles>, crs=<EPSG_code_optional>, "
            "dissolve=<bool>"
        )
    ]

    system_msg = (
        "You are a geospatial task execution assistant. Your role is to "
        "translate the user's request into a geoprocessing operation with parameters. "
        "CRITICAL FOR BUFFER OPERATION: If the chosen operation is 'buffer', "
        "you MUST extract 'radius' (a number) and 'radius_unit' (e.g., 'meters', "
        "'kilometers', 'miles') directly and precisely from the user's query. "
        "Return a JSON object structured EXACTLY as follows: "
        '`{{"steps": [{{"operation": "chosen_operation_name", '
        '"params": {{extracted_parameters}}}}], "result_name": '
        '"Short Descriptive Title", "result_description": '
        '"Brief description of what this operation does."}}`. '
        f"Available operations: {json.dumps(available_ops)}"
    )

    results = []

    for query in test_queries:
        user_payload = {
            "query": query,
            "available_operations": available_ops,
            "layers": [{"name": "test_layer"}],
        }
        user_msg = json.dumps(user_payload)

        messages = [
            SystemMessage(content=system_msg),
            HumanMessage(content=user_msg),
        ]

        try:
            response = await llm.agenerate([messages])
            content = response.generations[0][0].text

            # Try to parse the response
            # Strip markdown code blocks if present
            cleaned_content = content
            if cleaned_content.strip().startswith("```"):
                # Extract content between code blocks
                lines = cleaned_content.split("\n")
                start_idx = 0
                for i, line in enumerate(lines):
                    if "```" in line:
                        start_idx = i
                        break
                cleaned_content = "\n".join(lines[start_idx + 1 :])
                if "```" in cleaned_content:
                    cleaned_content = cleaned_content.split("```")[0]

            plan = json.loads(cleaned_content)

            results.append(
                {
                    "query": query,
                    "success": True,
                    "plan": plan,
                    "params": plan.get("steps", [{}])[0].get("params", {}),
                }
            )

        except Exception as e:
            results.append(
                {
                    "query": query,
                    "success": False,
                    "error": str(e),
                    "response": content if "content" in locals() else "No response",
                }
            )

    # Print results
    print("\n" + "=" * 80)
    print("LLM BUFFER PARAMETER UNDERSTANDING TEST")
    print("=" * 80 + "\n")

    for result in results:
        print(f"Query: {result['query']}")
        if result["success"]:
            params = result["params"]
            print("  ✅ SUCCESS")
            print(f"  Radius: {params.get('radius', 'MISSING')}")
            print(f"  Unit: {params.get('radius_unit', 'MISSING')}")
            print(f"  Full params: {json.dumps(params, indent=2)}")
        else:
            print(f"  ❌ FAILED: {result['error']}")
            print(f"  Response: {result.get('response', 'N/A')[:200]}")
        print()

    # Summary
    success_count = sum(1 for r in results if r["success"])
    print("=" * 80)
    print(f"Results: {success_count}/{len(results)} queries correctly parsed")
    print("=" * 80)

    # Check for common issues
    issues = []
    for result in results:
        if result["success"]:
            params = result["params"]
            if "radius" not in params:
                issues.append(f"Missing 'radius' in: {result['query']}")
            if "radius_unit" not in params:
                issues.append(f"Missing 'radius_unit' in: {result['query']}")

    if issues:
        print("\n⚠️  ISSUES DETECTED:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("\n✅ All queries correctly extracted radius and radius_unit!")


if __name__ == "__main__":
    asyncio.run(test_llm_buffer_understanding())
