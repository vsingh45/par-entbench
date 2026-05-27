"""Tests for par.observability — cost computation and kill-switch."""

import pytest

from par.observability import (
    DEFAULT_KILL_SWITCH_USD,
    PRICING,
    check_kill_switch,
    compute_cost,
    record_node_result,
)
from par.types import NodeResult, WorkflowTrace


def test_compute_cost_small_tier():
    cost = compute_cost(tier="small", input_tokens=1000, output_tokens=500, cached_tokens=0)
    expected = 1000 * (1.00 / 1_000_000) + 500 * (5.00 / 1_000_000)
    assert cost == pytest.approx(expected)


def test_compute_cost_with_caching():
    cost = compute_cost(tier="mid", input_tokens=1000, output_tokens=500, cached_tokens=800)
    # 200 fresh input + 800 cached input + 500 output
    expected = (
        200 * (3.00 / 1_000_000)
        + 800 * (0.30 / 1_000_000)
        + 500 * (15.00 / 1_000_000)
    )
    assert cost == pytest.approx(expected)


def test_compute_cost_frontier_tier():
    cost = compute_cost(tier="frontier", input_tokens=2000, output_tokens=1000, cached_tokens=0)
    expected = 2000 * (5.00 / 1_000_000) + 1000 * (25.00 / 1_000_000)
    assert cost == pytest.approx(expected)


def test_kill_switch_does_not_fire_below_ceiling():
    assert check_kill_switch(cumulative_spend=10.0, ceiling=75.0) is False


def test_kill_switch_fires_at_ceiling():
    assert check_kill_switch(cumulative_spend=75.0, ceiling=75.0) is True


def test_kill_switch_fires_above_ceiling():
    assert check_kill_switch(cumulative_spend=80.0, ceiling=75.0) is True


def test_pricing_table_completeness():
    for tier in ["small", "mid", "frontier"]:
        assert tier in PRICING
        for key in ["input", "output", "cache_read"]:
            assert key in PRICING[tier]


def test_record_node_result_accumulates_cost():
    trace = WorkflowTrace(task_id="t1", router="par", seed=1)
    nr = NodeResult(
        subtask_id="s1",
        specialist="sql_gen",
        tier_assigned="small",
        model_used="claude-haiku-4-5-20251001",
        input_tokens=1000,
        output_tokens=500,
        cached_tokens=0,
        latency_ms=200,
    )
    trace, fired = record_node_result(trace, nr, kill_switch_ceiling=75.0)
    assert fired is False
    assert trace.total_cost_usd > 0
    assert len(trace.node_results) == 1
