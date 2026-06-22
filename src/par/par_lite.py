"""
PaR-Lite — cost-optimized PaR variant.

Uses Haiku classifier to decide complexity, then:
- SIMPLE tasks: Haiku specialist directly (no full planner call)
- COMPLEX tasks: full PaR with the Haiku 4.5 (small-tier) planner + tier routing

This is one of the eight routers in the comparison table.
Expected cost: ~$0.004-0.007/task blended.
Expected accuracy: similar to PaR on complex tasks, similar to AllSmall on simple.
"""

from __future__ import annotations

import anthropic

from par.dispatcher import dispatch_plan
from par.observability import DEFAULT_KILL_SWITCH_USD
from par.types import NodeResult, WorkflowState


def par_lite_dispatch(
    state: WorkflowState,
    client: anthropic.Anthropic,
    specialist_registry: dict,
    kill_switch_ceiling: float = DEFAULT_KILL_SWITCH_USD,
) -> tuple[list[NodeResult], bool]:
    """
    PaR-Lite dispatch:
    - Simple tasks: plan already set by cascaded run_planner (single Haiku subtask)
    - Complex tasks: plan already set by cascaded run_planner (full Sonnet plan)
    Both cases dispatch via the standard plan dispatcher.
    """
    return dispatch_plan(state, client, specialist_registry, kill_switch_ceiling)
