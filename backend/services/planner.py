"""
Multi-step execution planner for complex geospatial queries.

Analyzes user queries to determine if they require multi-step execution,
and if so, creates a structured plan that the agent can follow. The plan
is streamed to the frontend so users can see what the agent is doing.

Design:
- Uses a lightweight LLM call to classify and plan BEFORE the ReAct agent runs.
- Simple queries (single tool) skip planning entirely for zero overhead.
- Complex queries get a plan that is injected into the agent's system prompt
  so the ReAct loop follows the structured steps.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage, HumanMessage

from models.states import ExecutionPlan, PlanStep

logger = logging.getLogger(__name__)

# Threshold: if the query likely needs >= this many tool calls, create a plan
MIN_STEPS_FOR_PLAN = 2

# Planning prompt - asks the LLM to classify and plan
PLANNING_PROMPT = """You are a planning assistant for a geospatial AI agent called NaLaMap.
Your job is to analyze a user's request and determine if it requires multiple sequential steps.

The agent has these tool categories:
- Geocoding: Find locations, boundaries, POIs (Nominatim, Overpass)
- Data Retrieval: Fetch datasets from GeoServer, catalogs
- Geoprocessing: Buffer, intersect, clip, merge spatial layers
- Attribute Operations: Filter, summarize, query layer attributes
- Styling: Apply colors, themes to map layers
- Metadata: Describe existing datasets
- OSINT: World Bank indicators, NASA fire/satellite data, ECMWF weather

Analyze the user's query and respond with a JSON object:
{{
  "is_complex": true/false,
  "goal": "Brief description of what the user wants to achieve",
  "steps": [
    {{
      "step_number": 1,
      "title": "Short title (3-7 words)",
      "description": "What this step accomplishes",
      "tool_hint": "Suggested tool category or name"
    }}
  ]
}}

Rules:
- Set is_complex=false for simple queries (single geocode, single question, simple styling).
- Set is_complex=true when the query requires 2+ sequential tool calls where later steps
  depend on results from earlier steps.
- Steps should be ordered by dependency (each step can use results from prior steps).
- Keep step titles concise and action-oriented.
- The tool_hint is informational only — the agent decides the actual tool to use.
- Maximum 6 steps. If more are needed, combine related operations.
- Do NOT include a final "respond to user" step — that happens automatically.

Examples of SIMPLE queries (is_complex=false):
- "Show me Paris" → single geocode
- "What layers do I have?" → single metadata query
- "Style the rivers blue" → single styling call

Examples of COMPLEX queries (is_complex=true):
- "Geocode Europe, find protected areas globally, then intersect them to get only
   European protected areas" → 3 steps: geocode, fetch data, geoprocess
- "Find hospitals in Berlin, create 1km buffers, and show how many parks are within
   each buffer" → 4 steps: geocode POIs, buffer, geocode parks, intersect/analyze
- "Get rainfall data for Kenya and overlay it with crop production statistics" →
   3 steps: geocode region, fetch weather, fetch World Bank data

User's current context:
{context}

User's query:
{query}

Respond with ONLY the JSON object, no markdown formatting."""


async def create_execution_plan(
    query: str,
    llm: Any,
    messages: Optional[List[BaseMessage]] = None,
    existing_layers: Optional[List[Dict[str, Any]]] = None,
) -> Optional[ExecutionPlan]:
    """Analyze a query and create an execution plan if it's complex.

    Args:
        query: The user's natural language query
        llm: The LLM instance to use for planning
        messages: Recent conversation history for context
        existing_layers: Currently loaded layers for context

    Returns:
        ExecutionPlan if the query is complex, None if simple
    """
    try:
        # Build context string
        context_parts = []
        if existing_layers:
            layer_names = [
                layer.get("title") or layer.get("name", "unnamed") for layer in existing_layers
            ]
            context_parts.append(f"Existing layers on map: {', '.join(layer_names)}")
        else:
            context_parts.append("No layers currently loaded on the map.")

        if messages and len(messages) > 1:
            # Include last few messages for conversation context
            recent = messages[-4:]  # Last 2 exchanges
            context_parts.append(
                f"Recent conversation ({len(recent)} messages): "
                + "; ".join(
                    f"[{getattr(m, 'type', 'unknown')}] {str(m.content)[:80]}" for m in recent
                )
            )

        context = "\n".join(context_parts)

        # Format the planning prompt
        prompt = PLANNING_PROMPT.format(query=query, context=context)

        # Use the LLM to analyze the query
        response = await llm.ainvoke([HumanMessage(content=prompt)])

        # Parse the JSON response
        content = response.content.strip()
        # Handle markdown code blocks
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

        plan_data = json.loads(content)

        if not plan_data.get("is_complex", False):
            logger.info(f"Query classified as simple, skipping plan: {query[:80]}")
            return None

        steps = [
            PlanStep(
                step_number=step.get("step_number", i + 1),
                title=step.get("title", f"Step {i + 1}"),
                description=step.get("description", ""),
                tool_hint=step.get("tool_hint"),
                status="pending",
            )
            for i, step in enumerate(plan_data.get("steps", []))
        ]

        if len(steps) < MIN_STEPS_FOR_PLAN:
            logger.info(f"Plan has {len(steps)} steps (< {MIN_STEPS_FOR_PLAN}), skipping")
            return None

        plan = ExecutionPlan(
            goal=plan_data.get("goal", query[:100]),
            steps=steps,
            is_complex=True,
        )

        logger.info(f"Created execution plan with {len(steps)} steps for: {query[:80]}")
        return plan

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse planning response as JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"Error creating execution plan: {e}")
        return None


def build_plan_system_addendum(plan: ExecutionPlan) -> str:
    """Build a system prompt addendum that instructs the agent to follow the plan.

    This is appended to the system prompt so the ReAct agent follows the
    structured plan while still using its own judgment for tool selection.

    Args:
        plan: The execution plan to follow

    Returns:
        String to append to the system prompt
    """
    steps_text = "\n".join(
        f"  {s.step_number}. [{s.status.upper()}] {s.title}: {s.description}"
        + (f" (suggested tool: {s.tool_hint})" if s.tool_hint else "")
        for s in plan.steps
    )

    return (
        "\n\n# EXECUTION PLAN\n"
        f"The user's request has been analyzed and broken into these sequential steps:\n"
        f"Goal: {plan.goal}\n\n"
        f"Steps:\n{steps_text}\n\n"
        "Instructions for following the plan:\n"
        "- Execute each step in order. Later steps may depend on results from earlier steps.\n"
        "- Use your judgment to select the best tool for each step.\n"
        "- If a step fails, explain the issue and try an alternative approach.\n"
        "- After completing all steps, provide a comprehensive summary of what was accomplished.\n"
        "- You may skip steps if they become unnecessary based on intermediate results.\n"
    )


def match_tool_to_plan_step(
    tool_name: str,
    plan: ExecutionPlan,
) -> Optional[int]:
    """Try to match a tool execution to a plan step based on tool category.

    Uses the tool_hint and tool name to find the most likely matching
    pending/in-progress step. This is a best-effort heuristic.

    Args:
        tool_name: Name of the tool being executed
        plan: The current execution plan

    Returns:
        Step number if matched, None otherwise
    """
    # Tool name to category mapping
    tool_categories = {
        "geocode_using_nominatim_to_geostate": "geocod",
        "geocode_using_overpass_to_geostate": "geocod",
        "geoprocess_tool": "geoprocess",
        "metadata_search": "metadata",
        "style_map_layers": "styl",
        "auto_style_new_layers": "styl",
        "check_and_auto_style_layers": "styl",
        "apply_intelligent_color_scheme": "color",
        "get_custom_geoserver_data": "data",
        "attribute_tool": "attribute",
        "attribute_tool2": "attribute",
        "get_world_bank_data": "world_bank",
        "get_ecmwf_weather_data": "weather",
        "get_nasa_fire_data": "fire",
        "get_nasa_gibs_layer": "satellite",
        "list_nasa_gibs_layers": "satellite",
    }

    tool_category = tool_categories.get(tool_name, tool_name.lower())

    # Find first pending step that matches the tool category
    for step in plan.steps:
        if step.status not in ("pending", "in-progress"):
            continue

        # Check tool_hint match
        hint = (step.tool_hint or "").lower()
        title = step.title.lower()
        desc = step.description.lower()
        search_text = f"{hint} {title} {desc}"

        if tool_category in search_text or tool_name.lower() in search_text:
            return step.step_number

    # Fallback: return first pending step (tools execute in order)
    for step in plan.steps:
        if step.status == "pending":
            return step.step_number

    return None


def update_plan_step_status(
    plan: ExecutionPlan,
    step_number: int,
    status: str,
    result_summary: Optional[str] = None,
) -> ExecutionPlan:
    """Update the status of a specific step in the plan.

    Args:
        plan: The execution plan to update
        step_number: The step number to update
        status: New status (pending, in-progress, complete, skipped, error)
        result_summary: Optional summary of the step result

    Returns:
        The updated plan (mutated in place)
    """
    for step in plan.steps:
        if step.step_number == step_number:
            step.status = status
            if result_summary:
                step.result_summary = result_summary
            break
    return plan
