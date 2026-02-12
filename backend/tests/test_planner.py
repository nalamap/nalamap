"""
Tests for the multi-step execution planner.

Tests cover:
- Plan creation for complex vs simple queries
- Plan step status tracking and updates
- Tool-to-step matching heuristics
- System prompt addendum generation
- Edge cases and error handling
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from models.states import ExecutionPlan, PlanStep
from services.planner import (
    build_plan_system_addendum,
    create_execution_plan,
    match_tool_to_plan_step,
    update_plan_step_status,
)


# =============================================================================
# Fixtures
# =============================================================================


def _make_plan(num_steps: int = 3) -> ExecutionPlan:
    """Create a test execution plan with the given number of steps."""
    steps = []
    step_templates = [
        ("Geocode the region", "Find the boundary for the target area", "geocoding"),
        ("Fetch data layer", "Retrieve the requested dataset", "data retrieval"),
        ("Perform spatial analysis", "Intersect/clip layers", "geoprocessing"),
        ("Style the results", "Apply appropriate colors", "styling"),
        ("Analyze attributes", "Summarize key statistics", "attribute"),
        ("Generate report", "Create summary description", "metadata"),
    ]

    for i in range(min(num_steps, len(step_templates))):
        title, desc, hint = step_templates[i]
        steps.append(
            PlanStep(
                step_number=i + 1,
                title=title,
                description=desc,
                tool_hint=hint,
                status="pending",
            )
        )

    return ExecutionPlan(
        goal="Test multi-step analysis",
        steps=steps,
        is_complex=True,
    )


def _mock_llm_response(content: str) -> AsyncMock:
    """Create a mock LLM that returns the given content."""
    mock_llm = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = content
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    return mock_llm


# =============================================================================
# PlanStep and ExecutionPlan Model Tests
# =============================================================================


class TestPlanStepModel:
    """Test the PlanStep Pydantic model."""

    def test_default_status(self):
        step = PlanStep(step_number=1, title="Test", description="A test step")
        assert step.status == "pending"
        assert step.result_summary is None
        assert step.tool_hint is None

    def test_full_step(self):
        step = PlanStep(
            step_number=2,
            title="Geocode Europe",
            description="Find the boundary of Europe",
            tool_hint="geocoding",
            status="complete",
            result_summary="Found boundary with 42 vertices",
        )
        assert step.step_number == 2
        assert step.title == "Geocode Europe"
        assert step.status == "complete"
        assert step.result_summary == "Found boundary with 42 vertices"

    def test_serialization(self):
        step = PlanStep(step_number=1, title="Test", description="desc")
        data = step.model_dump()
        assert data["step_number"] == 1
        assert data["status"] == "pending"

        # Round-trip
        step2 = PlanStep.model_validate(data)
        assert step2 == step


class TestExecutionPlanModel:
    """Test the ExecutionPlan Pydantic model."""

    def test_default_plan(self):
        plan = ExecutionPlan(goal="Test goal", steps=[], is_complex=False)
        assert plan.goal == "Test goal"
        assert len(plan.steps) == 0
        assert plan.is_complex is False

    def test_plan_with_steps(self):
        plan = _make_plan(3)
        assert plan.is_complex is True
        assert len(plan.steps) == 3
        assert plan.steps[0].step_number == 1
        assert plan.steps[2].step_number == 3

    def test_serialization(self):
        plan = _make_plan(2)
        data = plan.model_dump()
        assert data["goal"] == "Test multi-step analysis"
        assert len(data["steps"]) == 2

        # Round-trip
        plan2 = ExecutionPlan.model_validate(data)
        assert plan2.goal == plan.goal
        assert len(plan2.steps) == len(plan.steps)


# =============================================================================
# Plan Step Status Updates
# =============================================================================


class TestUpdatePlanStepStatus:
    """Test updating step statuses in a plan."""

    def test_update_to_in_progress(self):
        plan = _make_plan(3)
        updated = update_plan_step_status(plan, 1, "in-progress")
        assert updated.steps[0].status == "in-progress"
        assert updated.steps[1].status == "pending"
        assert updated.steps[2].status == "pending"

    def test_update_to_complete(self):
        plan = _make_plan(3)
        updated = update_plan_step_status(plan, 2, "complete", "Found 5 layers")
        assert updated.steps[1].status == "complete"
        assert updated.steps[1].result_summary == "Found 5 layers"

    def test_update_nonexistent_step(self):
        plan = _make_plan(2)
        # Should not raise, just do nothing
        updated = update_plan_step_status(plan, 99, "complete")
        assert all(s.status == "pending" for s in updated.steps)

    def test_sequential_updates(self):
        plan = _make_plan(3)
        update_plan_step_status(plan, 1, "in-progress")
        update_plan_step_status(plan, 1, "complete", "Done geocoding")
        update_plan_step_status(plan, 2, "in-progress")
        update_plan_step_status(plan, 2, "complete", "Data fetched")
        update_plan_step_status(plan, 3, "in-progress")

        assert plan.steps[0].status == "complete"
        assert plan.steps[1].status == "complete"
        assert plan.steps[2].status == "in-progress"


# =============================================================================
# Tool-to-Plan-Step Matching
# =============================================================================


class TestMatchToolToPlanStep:
    """Test the heuristic tool-to-step matching."""

    def test_geocoding_tool_matches_geocoding_step(self):
        plan = _make_plan(3)
        result = match_tool_to_plan_step("geocode_using_nominatim_to_geostate", plan)
        assert result == 1  # First step is geocoding

    def test_geoprocess_matches_third_step(self):
        plan = _make_plan(3)
        # Mark first two steps as complete
        plan.steps[0].status = "complete"
        plan.steps[1].status = "complete"
        result = match_tool_to_plan_step("geoprocess_tool", plan)
        assert result == 3  # Third step is geoprocessing

    def test_fallback_to_first_pending(self):
        plan = _make_plan(3)
        # Unknown tool should match first pending step
        result = match_tool_to_plan_step("some_unknown_tool", plan)
        assert result == 1

    def test_no_match_when_all_complete(self):
        plan = _make_plan(2)
        plan.steps[0].status = "complete"
        plan.steps[1].status = "complete"
        result = match_tool_to_plan_step("geocode_using_nominatim_to_geostate", plan)
        assert result is None

    def test_skips_completed_steps(self):
        plan = _make_plan(3)
        plan.steps[0].status = "complete"
        # geocoding tool should not match step 1 (already complete)
        result = match_tool_to_plan_step("geocode_using_nominatim_to_geostate", plan)
        # Should fall back to first pending step (step 2)
        assert result == 2


# =============================================================================
# System Prompt Addendum
# =============================================================================


class TestBuildPlanSystemAddendum:
    """Test the system prompt addendum builder."""

    def test_addendum_contains_goal(self):
        plan = _make_plan(2)
        addendum = build_plan_system_addendum(plan)
        assert "Test multi-step analysis" in addendum

    def test_addendum_contains_steps(self):
        plan = _make_plan(3)
        addendum = build_plan_system_addendum(plan)
        assert "Geocode the region" in addendum
        assert "Fetch data layer" in addendum
        assert "Perform spatial analysis" in addendum

    def test_addendum_contains_instructions(self):
        plan = _make_plan(2)
        addendum = build_plan_system_addendum(plan)
        assert "Execute each step in order" in addendum
        assert "EXECUTION PLAN" in addendum

    def test_addendum_shows_step_statuses(self):
        plan = _make_plan(3)
        plan.steps[0].status = "complete"
        plan.steps[1].status = "in-progress"
        addendum = build_plan_system_addendum(plan)
        assert "[COMPLETE]" in addendum
        assert "[IN-PROGRESS]" in addendum
        assert "[PENDING]" in addendum


# =============================================================================
# Plan Creation (LLM Integration)
# =============================================================================


class TestCreateExecutionPlan:
    """Test the plan creation using a mocked LLM."""

    @pytest.mark.asyncio
    async def test_complex_query_creates_plan(self):
        """Complex multi-step query should produce a plan."""
        llm_response = json.dumps(
            {
                "is_complex": True,
                "goal": "Find protected areas in Europe",
                "steps": [
                    {
                        "step_number": 1,
                        "title": "Geocode Europe",
                        "description": "Find the boundary of Europe",
                        "tool_hint": "geocoding",
                    },
                    {
                        "step_number": 2,
                        "title": "Fetch protected areas",
                        "description": "Get global protected area data",
                        "tool_hint": "data retrieval",
                    },
                    {
                        "step_number": 3,
                        "title": "Intersect layers",
                        "description": "Clip protected areas to Europe boundary",
                        "tool_hint": "geoprocessing",
                    },
                ],
            }
        )
        mock_llm = _mock_llm_response(llm_response)

        plan = await create_execution_plan(
            query="Geocode Europe, get protected areas, and intersect them",
            llm=mock_llm,
        )

        assert plan is not None
        assert plan.is_complex is True
        assert len(plan.steps) == 3
        assert plan.steps[0].title == "Geocode Europe"
        assert plan.steps[2].title == "Intersect layers"
        assert all(s.status == "pending" for s in plan.steps)

    @pytest.mark.asyncio
    async def test_simple_query_returns_none(self):
        """Simple single-step query should not produce a plan."""
        llm_response = json.dumps(
            {
                "is_complex": False,
                "goal": "Show Paris on the map",
                "steps": [
                    {
                        "step_number": 1,
                        "title": "Geocode Paris",
                        "description": "Find Paris coordinates",
                        "tool_hint": "geocoding",
                    }
                ],
            }
        )
        mock_llm = _mock_llm_response(llm_response)

        plan = await create_execution_plan(
            query="Show me Paris",
            llm=mock_llm,
        )

        assert plan is None

    @pytest.mark.asyncio
    async def test_handles_markdown_json_response(self):
        """LLM may wrap JSON in markdown code blocks."""
        llm_response = (
            "```json\n"
            + json.dumps(
                {
                    "is_complex": True,
                    "goal": "Multi-step analysis",
                    "steps": [
                        {
                            "step_number": 1,
                            "title": "Step one",
                            "description": "First step",
                        },
                        {
                            "step_number": 2,
                            "title": "Step two",
                            "description": "Second step",
                        },
                    ],
                }
            )
            + "\n```"
        )
        mock_llm = _mock_llm_response(llm_response)

        plan = await create_execution_plan(query="complex query", llm=mock_llm)
        assert plan is not None
        assert len(plan.steps) == 2

    @pytest.mark.asyncio
    async def test_handles_llm_error_gracefully(self):
        """LLM errors should return None, not crash."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM unavailable"))

        plan = await create_execution_plan(query="test query", llm=mock_llm)
        assert plan is None

    @pytest.mark.asyncio
    async def test_handles_invalid_json_gracefully(self):
        """Invalid JSON from LLM should return None."""
        mock_llm = _mock_llm_response("This is not valid JSON at all")

        plan = await create_execution_plan(query="test query", llm=mock_llm)
        assert plan is None

    @pytest.mark.asyncio
    async def test_includes_layer_context(self):
        """Should include existing layers in context."""
        llm_response = json.dumps(
            {
                "is_complex": False,
                "goal": "Simple query",
                "steps": [],
            }
        )
        mock_llm = _mock_llm_response(llm_response)

        await create_execution_plan(
            query="test query",
            llm=mock_llm,
            existing_layers=[
                {"title": "Rivers", "name": "rivers_layer"},
                {"title": "Cities", "name": "cities_layer"},
            ],
        )

        # Verify the prompt included layer context
        call_args = mock_llm.ainvoke.call_args[0][0]
        prompt_content = call_args[0].content
        assert "Rivers" in prompt_content
        assert "Cities" in prompt_content


# =============================================================================
# State Reducer Tests
# =============================================================================


class TestReduceExecutionPlan:
    """Test the execution_plan state reducer."""

    def test_reduce_none_current(self):
        from models.states import reduce_execution_plan

        plan = _make_plan(2)
        result = reduce_execution_plan(None, plan)
        assert result == plan

    def test_reduce_none_new(self):
        from models.states import reduce_execution_plan

        plan = _make_plan(2)
        result = reduce_execution_plan(plan, None)
        assert result == plan

    def test_reduce_both_none(self):
        from models.states import reduce_execution_plan

        result = reduce_execution_plan(None, None)
        assert result is None

    def test_reduce_merges_step_statuses(self):
        from models.states import reduce_execution_plan

        current = _make_plan(3)
        current.steps[0].status = "complete"

        new_plan = ExecutionPlan(
            goal="Test",
            steps=[
                PlanStep(
                    step_number=2,
                    title="Update",
                    description="Updated step",
                    status="in-progress",
                )
            ],
            is_complex=True,
        )

        result = reduce_execution_plan(current, new_plan)
        assert result is not None
        assert result.steps[0].status == "complete"  # Preserved
        assert result.steps[1].status == "in-progress"  # Updated
        assert result.steps[2].status == "pending"  # Unchanged
