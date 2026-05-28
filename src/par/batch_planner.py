"""
par/batch_planner.py — Batch Planner for PaR.

Generates one template plan per task class by running the planner once on
the first task encountered in that class, then reuses the plan's structure
(specialist sequence + tier assignments) for all subsequent tasks in the
same class. This eliminates per-task planner API calls for all but one
task per class, significantly reducing planner cost across a sweep.

Usage:
    planner = BatchPlanner(client)
    state = planner.run(state)   # drop-in for run_planner(state, client)
"""
from __future__ import annotations

import anthropic

from .planner import run_planner
from .types import Plan, WorkflowState


class BatchPlanner:
    """
    Caches one template Plan per task class and reuses it for every task
    in that class after the first.

    The first task in each class pays the full planner API cost and its
    plan is stored as the template. All subsequent tasks in the same class
    receive a deep copy of the template — no API call, no planner cost.

    The template's subtask descriptions come from the representative query,
    but specialists also receive the full task query via task_context, so
    they answer the correct question regardless.
    """

    def __init__(self, client: anthropic.Anthropic, no_rationale: bool = False) -> None:
        self.client = client
        self.no_rationale = no_rationale
        self._templates: dict[str, Plan] = {}

    def run(self, state: WorkflowState) -> WorkflowState:
        """
        Return state with plan populated.

        If a template exists for state.task_class, reuses it (zero API cost).
        Otherwise runs the real planner, caches the result, and charges cost.
        """
        task_class = state.task_class or "unknown"

        if task_class in self._templates:
            plan = self._templates[task_class].model_copy(deep=True)
            state.plan = plan
            state.pending_subtasks = list(plan.subtasks)
        else:
            state = run_planner(state, self.client, no_rationale=self.no_rationale)
            self._templates[task_class] = state.plan

        return state

    @property
    def template_classes(self) -> list[str]:
        """Task classes for which a template plan has been generated."""
        return list(self._templates.keys())
