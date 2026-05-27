"""
par/types.py — Shared Pydantic types for PaR reference implementation.

Defines: Plan (planner output), Subtask, NodeResult (per-node execution),
WorkflowTrace (full task execution record), WorkflowState (LangGraph state).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Planner output types
# ---------------------------------------------------------------------------

Tier = Literal["small", "mid", "frontier"]

SpecialistType = Literal[
    "sql_gen", "mongo_query", "extract",
    "cross_recon", "multitool_plan", "policy_action"
]


class Subtask(BaseModel):
    """One subtask in the plan emitted by the planner."""
    id: str = Field(description="Unique subtask id, e.g. 'extract_1'")
    description: str = Field(description="Natural language description")
    specialist: SpecialistType = Field(description="Specialist agent to handle this subtask")
    tier: Tier = Field(description="Model tier: small (Haiku), mid (Sonnet), frontier (Opus)")
    depends_on: list[str] = Field(
        default_factory=list,
        description="IDs of subtasks whose outputs this one requires",
    )


class Plan(BaseModel):
    """Structured plan produced by the Planner-as-Router."""
    subtasks: list[Subtask] = Field(description="Ordered list of subtasks with tier assignments")
    cost_rationale: str = Field(
        description="Brief explanation of why each tier was chosen — forces explicit reasoning"
    )


# ---------------------------------------------------------------------------
# Execution result types
# ---------------------------------------------------------------------------

class NodeResult(BaseModel):
    """Per-node execution record produced by the dispatcher + observability layer."""
    subtask_id: str
    specialist: SpecialistType
    tier_assigned: Tier
    model_used: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    latency_ms: int
    output: dict | None = None       # structured output from the specialist
    node_correct: bool | None = None # set by the evaluator after execution
    error: str | None = None         # set if execution failed


class WorkflowTrace(BaseModel):
    """Full execution record for one task-router-seed combination."""
    task_id: str
    task_class: str | None = None
    router: str
    seed: int
    plan: Plan | None = None
    node_results: list[NodeResult] = Field(default_factory=list)
    task_correct: bool | None = None
    total_cost_usd: float = 0.0
    total_latency_ms: int = 0
    cumulative_spend_usd: float = 0.0   # running total across all tasks in a sweep


# ---------------------------------------------------------------------------
# Workflow state (LangGraph state object)
# ---------------------------------------------------------------------------

class WorkflowState(BaseModel):
    """Shared mutable state passed through the LangGraph workflow."""
    query: str
    task_id: str
    task_class: str | None = None
    router: str
    seed: int
    plan: Plan | None = None
    node_results: list[NodeResult] = Field(default_factory=list)
    pending_subtasks: list[Subtask] = Field(default_factory=list)
    completed_subtask_ids: set[str] = Field(default_factory=set)
    cumulative_spend_usd: float = 0.0
    kill_switch_triggered: bool = False

    model_config = ConfigDict(arbitrary_types_allowed=True)
