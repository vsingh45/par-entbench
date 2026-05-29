"""
par/dispatcher.py — Dispatcher for PaR.

Reads the plan, dispatches subtasks to specialists in dependency order,
applies Flavor A bounded retry, and records per-node results.

Flavor A retry: retry at the assigned tier up to MAX_RETRIES times,
then escalate one tier and retry once. If escalation also fails,
mark the node failed and pass null to downstream nodes.
"""

from __future__ import annotations

import time

import anthropic

from .observability import DEFAULT_KILL_SWITCH_USD, compute_cost
from .types import NodeResult, Plan, Subtask, Tier, WorkflowState

TIER_MODELS: dict[Tier, str] = {
    "small": "claude-haiku-4-5-20251001",
    "mid": "claude-sonnet-4-6",
    "frontier": "claude-opus-4-7",
}

TIER_ESCALATION: dict[Tier, Tier | None] = {
    "small": "mid",
    "mid": "frontier",
    "frontier": None,
}

MAX_RETRIES = 3


# ---------------------------------------------------------------------------
# Dependency resolution
# ---------------------------------------------------------------------------


def get_ready_subtasks(plan: Plan, completed_ids: set[str]) -> list[Subtask]:
    """Return subtasks whose dependencies are all satisfied."""
    return [
        s
        for s in plan.subtasks
        if s.id not in completed_ids and all(dep in completed_ids for dep in s.depends_on)
    ]


def collect_upstream_outputs(subtask: Subtask, node_results: list[NodeResult]) -> dict[str, dict]:
    """Collect outputs from upstream nodes."""
    result_map = {r.subtask_id: r.output for r in node_results if r.output}
    return {dep: result_map.get(dep, {}) for dep in subtask.depends_on}


# ---------------------------------------------------------------------------
# Single subtask execution with Flavor A retry
# ---------------------------------------------------------------------------


def execute_subtask(
    subtask: Subtask,
    upstream_outputs: dict[str, dict],
    client: anthropic.Anthropic,
    specialist_fn,
    assigned_tier: Tier,
) -> NodeResult:
    """Execute one subtask with Flavor A bounded retry."""
    tier_to_try = assigned_tier
    attempt = 0
    last_error = None

    while True:
        attempt += 1
        model = TIER_MODELS[tier_to_try]
        t0 = time.monotonic()

        try:
            result_data, usage = specialist_fn(
                subtask=subtask,
                tier=tier_to_try,
                upstream_outputs=upstream_outputs,
                client=client,
            )
            latency_ms = int((time.monotonic() - t0) * 1000)
            return NodeResult(
                subtask_id=subtask.id,
                specialist=subtask.specialist,
                tier_assigned=assigned_tier,
                model_used=model,
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                cached_tokens=usage.get("cached_tokens", 0),
                latency_ms=latency_ms,
                output=result_data,
            )

        except Exception as e:
            last_error = str(e)
            latency_ms = int((time.monotonic() - t0) * 1000)

            if attempt < MAX_RETRIES:
                continue

            # Max retries exhausted — try escalation once
            escalated = TIER_ESCALATION.get(tier_to_try)
            if escalated and tier_to_try == assigned_tier:
                tier_to_try = escalated
                attempt = 0
                continue

            # All exhausted — return failed node
            return NodeResult(
                subtask_id=subtask.id,
                specialist=subtask.specialist,
                tier_assigned=assigned_tier,
                model_used=model,
                input_tokens=0,
                output_tokens=0,
                cached_tokens=0,
                latency_ms=latency_ms,
                output=None,
                error=last_error,
            )


# ---------------------------------------------------------------------------
# Main dispatcher (PaR — uses tier from planner)
# ---------------------------------------------------------------------------


def dispatch_plan(
    state: WorkflowState,
    client: anthropic.Anthropic,
    specialist_registry: dict,
    kill_switch_ceiling: float = DEFAULT_KILL_SWITCH_USD,
) -> tuple[list[NodeResult], bool]:
    """
    Execute all subtasks in dependency order using tier from the plan.
    Returns (node_results, kill_switch_triggered).
    """
    plan = state.plan
    completed_ids: set[str] = set()
    node_results: list[NodeResult] = []
    cumulative_spend = state.cumulative_spend_usd
    kill_switch_triggered = False

    remaining = list(plan.subtasks)

    while remaining:
        ready = get_ready_subtasks(plan, completed_ids)
        if not ready:
            raise ValueError(
                f"Dependency deadlock for task {state.task_id}. "
                f"Remaining: {[s.id for s in remaining]}"
            )

        for subtask in ready:
            if kill_switch_triggered:
                break

            upstream = collect_upstream_outputs(subtask, node_results)
            specialist_fn = specialist_registry.get(subtask.specialist)
            if specialist_fn is None:
                raise ValueError(f"No specialist registered for: {subtask.specialist}")

            # PaR: use the tier assigned by the planner
            assigned_tier = subtask.tier

            node_result = execute_subtask(
                subtask=subtask,
                upstream_outputs=upstream,
                client=client,
                specialist_fn=specialist_fn,
                assigned_tier=assigned_tier,
            )

            node_results.append(node_result)
            completed_ids.add(subtask.id)

            node_cost = compute_cost(
                tier=node_result.tier_assigned,
                input_tokens=node_result.input_tokens,
                output_tokens=node_result.output_tokens,
                cached_tokens=node_result.cached_tokens,
            )
            cumulative_spend += node_cost
            if cumulative_spend >= kill_switch_ceiling:
                kill_switch_triggered = True

        remaining = [s for s in remaining if s.id not in completed_ids]

    return node_results, kill_switch_triggered
