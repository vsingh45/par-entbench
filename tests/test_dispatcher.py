"""Tests for par.dispatcher dependency resolution."""

from par.dispatcher import collect_upstream_outputs, dispatch_plan, get_ready_subtasks
from par.types import NodeResult, Plan, Subtask, WorkflowState


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


# ---------------------------------------------------------------------------
# Null propagation (Algorithm 1, lines 3-5): a node whose dependency returned
# null must itself be recorded null WITHOUT being executed.
# ---------------------------------------------------------------------------


def test_null_propagates_and_downstream_not_executed():
    """If s1 hard-fails, s2 (depends on s1) is recorded null and never run."""
    plan = Plan(
        subtasks=[
            Subtask(id="s1", description="root", specialist="sql_gen", tier="small"),
            Subtask(
                id="s2",
                description="depends on s1",
                specialist="cross_recon",
                tier="mid",
                depends_on=["s1"],
            ),
        ],
        cost_rationale="test",
    )
    state = WorkflowState(query="q", task_id="t1", router="par", seed=1, plan=plan)

    calls: list[str] = []

    def failing_sql_gen(subtask, tier, upstream_outputs, client):
        calls.append(subtask.id)
        raise RuntimeError("specialist blew up")

    def recon(subtask, tier, upstream_outputs, client):
        calls.append(subtask.id)
        return {"result": "should never run"}, {"input_tokens": 1, "output_tokens": 1}

    registry = {"sql_gen": failing_sql_gen, "cross_recon": recon}

    node_results, kill = dispatch_plan(state, client=object(), specialist_registry=registry)

    by_id = {r.subtask_id: r for r in node_results}
    # s1 attempted (and failed), s2 skipped entirely
    assert "s1" in calls
    assert "s2" not in calls, "downstream node ran despite null upstream"
    # both recorded null
    assert by_id["s1"].output is None
    assert by_id["s2"].output is None
    # skipped node carries zero cost and a skip reason
    assert by_id["s2"].input_tokens == 0 and by_id["s2"].output_tokens == 0
    assert "skipped" in (by_id["s2"].error or "")
    assert kill is False


def test_healthy_plan_executes_all_nodes():
    """No failures -> every node runs, nothing is nulled."""
    plan = Plan(
        subtasks=[
            Subtask(id="s1", description="root", specialist="sql_gen", tier="small"),
            Subtask(
                id="s2", description="dep", specialist="cross_recon", tier="mid", depends_on=["s1"]
            ),
        ],
        cost_rationale="test",
    )
    state = WorkflowState(query="q", task_id="t2", router="par", seed=1, plan=plan)
    calls: list[str] = []

    def ok(subtask, tier, upstream_outputs, client):
        calls.append(subtask.id)
        return {"ok": True}, {"input_tokens": 10, "output_tokens": 5}

    registry = {"sql_gen": ok, "cross_recon": ok}
    node_results, kill = dispatch_plan(state, client=object(), specialist_registry=registry)

    assert calls == ["s1", "s2"]
    assert all(r.output is not None for r in node_results)
