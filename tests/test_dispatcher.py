"""Tests for par.dispatcher dependency resolution."""

from par.dispatcher import collect_upstream_outputs, get_ready_subtasks
from par.types import NodeResult, Plan, Subtask


def _make_plan() -> Plan:
    return Plan(
        subtasks=[
            Subtask(id="s1", description="root", specialist="sql_gen", tier="mid"),
            Subtask(
                id="s2",
                description="depends on s1",
                specialist="cross_recon",
                tier="frontier",
                depends_on=["s1"],
            ),
            Subtask(
                id="s3",
                description="depends on s1, s2",
                specialist="policy_action",
                tier="small",
                depends_on=["s1", "s2"],
            ),
        ],
        cost_rationale="test",
    )


def test_get_ready_subtasks_returns_root_initially():
    plan = _make_plan()
    ready = get_ready_subtasks(plan, completed_ids=set())
    assert len(ready) == 1
    assert ready[0].id == "s1"


def test_get_ready_subtasks_returns_next_after_root():
    plan = _make_plan()
    ready = get_ready_subtasks(plan, completed_ids={"s1"})
    assert len(ready) == 1
    assert ready[0].id == "s2"


def test_get_ready_subtasks_waits_for_all_deps():
    plan = _make_plan()
    # s3 should NOT be ready when only s1 is complete (also needs s2)
    ready = get_ready_subtasks(plan, completed_ids={"s1"})
    ids = [s.id for s in ready]
    assert "s3" not in ids


def test_get_ready_subtasks_returns_terminal():
    plan = _make_plan()
    ready = get_ready_subtasks(plan, completed_ids={"s1", "s2"})
    assert len(ready) == 1
    assert ready[0].id == "s3"


def test_collect_upstream_outputs_finds_deps():
    subtask = Subtask(
        id="s2",
        description="x",
        specialist="cross_recon",
        tier="frontier",
        depends_on=["s1"],
    )
    node_results = [
        NodeResult(
            subtask_id="s1",
            specialist="sql_gen",
            tier_assigned="mid",
            model_used="claude-sonnet-4-6",
            input_tokens=100,
            output_tokens=50,
            cached_tokens=0,
            latency_ms=200,
            output={"result": "rows"},
        )
    ]
    upstream = collect_upstream_outputs(subtask, node_results)
    assert "s1" in upstream
    assert upstream["s1"]["result"] == "rows"


def test_collect_upstream_outputs_missing_dep():
    subtask = Subtask(
        id="s2",
        description="x",
        specialist="cross_recon",
        tier="frontier",
        depends_on=["missing"],
    )
    upstream = collect_upstream_outputs(subtask, node_results=[])
    assert "missing" in upstream
    assert upstream["missing"] == {}
