"""
par/observability.py — Cost tracking and per-node result recording.

Pricing reflects Anthropic API rates as of May 2026. Verify against
https://www.anthropic.com/pricing before running experiments — model
pricing changes and cost measurements depend on accurate rates.
"""
from __future__ import annotations

import json
from pathlib import Path

from .types import NodeResult, Tier, WorkflowTrace

# ---------------------------------------------------------------------------
# Pricing (per token, USD) — verify before running experiments
# ---------------------------------------------------------------------------

PRICING = {
    "small": {   # Claude Haiku 4.5
        "input":      1.00 / 1_000_000,
        "output":     5.00 / 1_000_000,
        "cache_read": 0.10 / 1_000_000,   # 90% discount on cached input
    },
    "mid": {     # Claude Sonnet 4.6
        "input":      3.00 / 1_000_000,
        "output":    15.00 / 1_000_000,
        "cache_read": 0.30 / 1_000_000,
    },
    "frontier": {  # Claude Opus 4.7
        "input":      5.00 / 1_000_000,
        "output":    25.00 / 1_000_000,
        "cache_read": 0.50 / 1_000_000,
    },
}

DEFAULT_KILL_SWITCH_USD = 75.0


# ---------------------------------------------------------------------------
# Cost computation
# ---------------------------------------------------------------------------

def compute_cost(
    tier: Tier,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
) -> float:
    """Compute the cost of a single model call in USD, accounting for caching."""
    p = PRICING[tier]
    fresh_input = max(0, input_tokens - cached_tokens)
    return (
        fresh_input    * p["input"]
        + cached_tokens  * p["cache_read"]
        + output_tokens  * p["output"]
    )


# ---------------------------------------------------------------------------
# Kill-switch
# ---------------------------------------------------------------------------

def check_kill_switch(
    cumulative_spend: float,
    ceiling: float = DEFAULT_KILL_SWITCH_USD,
    checkpoint_path: str | None = None,
    trace: WorkflowTrace | None = None,
) -> bool:
    """Return True if the kill-switch should fire. Writes a checkpoint if so."""
    if cumulative_spend >= ceiling:
        if checkpoint_path and trace:
            Path(checkpoint_path).parent.mkdir(parents=True, exist_ok=True)
            with open(checkpoint_path, "w") as f:
                json.dump({
                    "status": "kill_switch_triggered",
                    "cumulative_spend_usd": cumulative_spend,
                    "ceiling_usd": ceiling,
                    "last_task_id": trace.task_id,
                }, f, indent=2)
        return True
    return False


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------

def record_node_result(
    trace: WorkflowTrace,
    node_result: NodeResult,
    kill_switch_ceiling: float = DEFAULT_KILL_SWITCH_USD,
) -> tuple[WorkflowTrace, bool]:
    """
    Append a NodeResult to the trace, update cumulative cost,
    and check the kill-switch. Returns (trace, kill_switch_fired).
    """
    node_cost = compute_cost(
        tier=node_result.tier_assigned,
        input_tokens=node_result.input_tokens,
        output_tokens=node_result.output_tokens,
        cached_tokens=node_result.cached_tokens,
    )
    trace.total_cost_usd += node_cost
    trace.cumulative_spend_usd += node_cost
    trace.total_latency_ms += node_result.latency_ms
    trace.node_results.append(node_result)

    kill_switch_fired = check_kill_switch(
        trace.cumulative_spend_usd, ceiling=kill_switch_ceiling
    )
    return trace, kill_switch_fired


def finalize_trace(trace: WorkflowTrace, task_correct: bool) -> WorkflowTrace:
    """Mark the trace as complete with end-to-end correctness verdict."""
    trace.task_correct = task_correct
    return trace


def emit_trace(trace: WorkflowTrace, output_dir: str) -> None:
    """Write the completed trace to the results directory."""
    out_path = Path(output_dir) / f"{trace.task_id}_{trace.router}_seed{trace.seed}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        f.write(trace.model_dump_json(indent=2))
