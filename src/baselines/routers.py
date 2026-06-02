"""
baselines/routers.py — Five baseline routers for comparison.

Each baseline is a drop-in replacement for the PaR dispatcher's
tier-assignment logic. The planner, specialists, observability, and
retry semantics remain identical across baselines to isolate the
effect of tier assignment from other factors.

Routers implemented:
  1. AllFrontier        — every node uses Opus 4.7 (accuracy upper bound)
  2. AllSmall           — every node uses Haiku 4.5 (cost lower bound)
  3. SinkFrontier       — frontier on terminal nodes only
  4. SourceFrontier     — frontier on root nodes only
  5. FrugalGPT cascade  — small first; escalate on low confidence
"""

from __future__ import annotations

from collections.abc import Callable

import anthropic

from baselines.frugal_confidence import score_confidence
from par.dispatcher import collect_upstream_outputs, execute_subtask, get_ready_subtasks
from par.observability import DEFAULT_KILL_SWITCH_USD, compute_cost
from par.types import NodeResult, Subtask, Tier, WorkflowState

# ---------------------------------------------------------------------------
# Generic dispatch using a tier-decision function
# ---------------------------------------------------------------------------


def _dispatch_with_tier_fn(
    state: WorkflowState,
    client: anthropic.Anthropic,
    specialist_registry: dict,
    tier_fn: Callable[[Subtask, list[NodeResult]], Tier],
    kill_switch_ceiling: float = DEFAULT_KILL_SWITCH_USD,
) -> tuple[list[NodeResult], bool]:
    """Dispatch ignoring the planner's tier; uses tier_fn instead."""
    plan = state.plan
    if plan is None:
        raise ValueError(f"No plan set for task {state.task_id}")
    completed_ids: set[str] = set()
    node_results: list[NodeResult] = []
    cumulative_spend = state.cumulative_spend_usd
    kill_switch_triggered = False

    remaining = list(plan.subtasks)

    while remaining:
        ready = get_ready_subtasks(plan, completed_ids)
        if not ready:
            raise ValueError(f"Dependency deadlock for task {state.task_id}")

        for subtask in ready:
            if kill_switch_triggered:
                break

            upstream = collect_upstream_outputs(subtask, node_results)
            specialist_fn = specialist_registry[subtask.specialist]
            assigned_tier = tier_fn(subtask, node_results)

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


# ---------------------------------------------------------------------------
# 1. AllFrontier
# ---------------------------------------------------------------------------


def all_frontier_dispatch(
    state, client, specialist_registry, kill_switch_ceiling=DEFAULT_KILL_SWITCH_USD
):
    return _dispatch_with_tier_fn(
        state,
        client,
        specialist_registry,
        tier_fn=lambda subtask, _: "frontier",
        kill_switch_ceiling=kill_switch_ceiling,
    )


# ---------------------------------------------------------------------------
# 2. AllSmall
# ---------------------------------------------------------------------------


def all_small_dispatch(
    state, client, specialist_registry, kill_switch_ceiling=DEFAULT_KILL_SWITCH_USD
):
    return _dispatch_with_tier_fn(
        state,
        client,
        specialist_registry,
        tier_fn=lambda subtask, _: "small",
        kill_switch_ceiling=kill_switch_ceiling,
    )


# ---------------------------------------------------------------------------
# 3. SinkFrontier — frontier on terminal nodes only
# ---------------------------------------------------------------------------


def sink_frontier_dispatch(
    state, client, specialist_registry, kill_switch_ceiling=DEFAULT_KILL_SWITCH_USD
):
    all_deps: set[str] = set()
    for s in state.plan.subtasks:
        all_deps.update(s.depends_on)
    terminal_ids = {s.id for s in state.plan.subtasks if s.id not in all_deps}

    return _dispatch_with_tier_fn(
        state,
        client,
        specialist_registry,
        tier_fn=lambda subtask, _: "frontier" if subtask.id in terminal_ids else "small",
        kill_switch_ceiling=kill_switch_ceiling,
    )


# ---------------------------------------------------------------------------
# 4. SourceFrontier — frontier on root nodes only
# ---------------------------------------------------------------------------


def source_frontier_dispatch(
    state, client, specialist_registry, kill_switch_ceiling=DEFAULT_KILL_SWITCH_USD
):
    root_ids = {s.id for s in state.plan.subtasks if not s.depends_on}
    return _dispatch_with_tier_fn(
        state,
        client,
        specialist_registry,
        tier_fn=lambda subtask, _: "frontier" if subtask.id in root_ids else "small",
        kill_switch_ceiling=kill_switch_ceiling,
    )


# ---------------------------------------------------------------------------
# 5. FrugalGPT-style cascade
# ---------------------------------------------------------------------------

FRUGAL_CONFIDENCE_THRESHOLD = 0.70
FRUGAL_TIER_ORDER: list[Tier] = ["small", "mid", "frontier"]


def frugal_cascade_dispatch(
    state,
    client,
    specialist_registry,
    kill_switch_ceiling=DEFAULT_KILL_SWITCH_USD,
    confidence_threshold: float = FRUGAL_CONFIDENCE_THRESHOLD,
):
    """
    Cascade: try small; if specialist returns confidence below threshold,
    re-invoke at next tier; repeat up to frontier.
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
            raise ValueError(f"Dependency deadlock for task {state.task_id}")

        for subtask in ready:
            if kill_switch_triggered:
                break

            upstream = collect_upstream_outputs(subtask, node_results)
            specialist_fn = specialist_registry[subtask.specialist]

            final_result = None
            for tier in FRUGAL_TIER_ORDER:
                result = execute_subtask(
                    subtask=subtask,
                    upstream_outputs=upstream,
                    client=client,
                    specialist_fn=specialist_fn,
                    assigned_tier=tier,
                )

                node_cost = compute_cost(
                    tier=tier,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    cached_tokens=result.cached_tokens,
                )
                cumulative_spend += node_cost
                if cumulative_spend >= kill_switch_ceiling:
                    kill_switch_triggered = True

                final_result = result

                # FrugalGPT scoring function: judge the answer to decide whether
                # to accept this tier or escalate. The judge is a real Haiku call,
                # so bill its cost to keep the cost comparison honest.
                confidence, judge_usage = score_confidence(
                    client=client,
                    subtask_description=subtask.description,
                    specialist_type=subtask.specialist,
                    output=result.output,
                    error=result.error,
                )
                judge_cost = compute_cost(
                    tier="small",
                    input_tokens=judge_usage["input_tokens"],
                    output_tokens=judge_usage["output_tokens"],
                    cached_tokens=judge_usage["cached_tokens"],
                )
                cumulative_spend += judge_cost
                if cumulative_spend >= kill_switch_ceiling:
                    kill_switch_triggered = True

                # A hard error escalates; otherwise accept iff confident enough,
                # or once we've reached the top tier (nowhere left to escalate).
                if (not result.error) and (
                    confidence >= confidence_threshold or tier == "frontier"
                ):
                    break
                if result.error and tier == "frontier":
                    break

            node_results.append(final_result)  # type: ignore[arg-type]
            completed_ids.add(subtask.id)

        remaining = [s for s in remaining if s.id not in completed_ids]

    return node_results, kill_switch_triggered


# ---------------------------------------------------------------------------
# Router registry
# ---------------------------------------------------------------------------
# "par" and "par_no_rationale" are handled in dispatcher.py / harness.py
# These are the baseline router functions only.

from par.par_lite import par_lite_dispatch  # noqa: E402

ROUTER_REGISTRY = {
    "all_frontier": all_frontier_dispatch,
    "all_small": all_small_dispatch,
    "sink_frontier": sink_frontier_dispatch,
    "source_frontier": source_frontier_dispatch,
    "frugal_cascade": frugal_cascade_dispatch,
    "par_lite": par_lite_dispatch,
}
