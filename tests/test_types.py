"""Tests for Pydantic schemas in par.types."""

import pytest
from pydantic import ValidationError

from par.types import NodeResult, Plan, Subtask, WorkflowState, WorkflowTrace


def test_subtask_minimal():
    s = Subtask(
        id="extract_1",
        description="Extract Adobe products from query",
        specialist="extract",
        tier="small",
    )
    assert s.id == "extract_1"
    assert s.tier == "small"
    assert s.depends_on == []


def test_subtask_with_dependencies():
    s = Subtask(
        id="recon_1",
        description="Reconcile contracts with spend",
        specialist="cross_recon",
        tier="frontier",
        depends_on=["mongo_1", "sql_1"],
    )
    assert s.depends_on == ["mongo_1", "sql_1"]


def test_subtask_invalid_tier():
    with pytest.raises(ValidationError):
        Subtask(
            id="bad",
            description="x",
            specialist="extract",
            tier="huge",  # invalid
        )


def test_subtask_invalid_specialist():
    with pytest.raises(ValidationError):
        Subtask(
            id="bad",
            description="x",
            specialist="unknown",  # invalid
            tier="small",
        )


def test_plan_with_rationale():
    plan = Plan(
        subtasks=[
            Subtask(id="s1", description="d1", specialist="sql_gen", tier="mid"),
        ],
        cost_rationale="Mid tier for moderate SQL complexity",
    )
    assert len(plan.subtasks) == 1
    assert plan.cost_rationale.startswith("Mid tier")


def test_node_result_with_error():
    nr = NodeResult(
        subtask_id="s1",
        specialist="sql_gen",
        tier_assigned="small",
        model_used="claude-haiku-4-5-20251001",
        input_tokens=0,
        output_tokens=0,
        cached_tokens=0,
        latency_ms=120,
        error="Timeout after 3 retries",
    )
    assert nr.error is not None
    assert nr.output is None


def test_workflow_trace_initialization():
    trace = WorkflowTrace(
        task_id="XR-001",
        task_class="cross_recon",
        router="par",
        seed=1,
    )
    assert trace.total_cost_usd == 0.0
    assert trace.node_results == []
    assert trace.task_correct is None


def test_workflow_state_initialization():
    state = WorkflowState(
        query="What is our Adobe spend?",
        task_id="SQL-001",
        task_class="sql_gen",
        router="par",
        seed=1,
    )
    assert state.cumulative_spend_usd == 0.0
    assert state.kill_switch_triggered is False
    assert state.completed_subtask_ids == set()
