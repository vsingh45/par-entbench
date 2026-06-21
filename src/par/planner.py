"""
par/planner.py — Planner agent for PaR.

The planner decomposes the user query into subtasks AND assigns each
subtask to a model tier in one structured output. Runs on Haiku 4.5
(small tier) across all routers — the planner itself is held fixed.

The cost_rationale field forces the planner to explicitly justify its
tier assignments. PaR-no-rationale (ablation) uses a variant without it.
"""

from __future__ import annotations

import os

import anthropic

from .observability import compute_cost
from .types import Plan, Subtask, WorkflowState

PLANNER_MODEL = os.environ.get("PLANNER_MODEL", "claude-haiku-4-5-20251001")


# ---------------------------------------------------------------------------
# Complexity classifier (Haiku, cached system prompt)
# ---------------------------------------------------------------------------

COMPLEXITY_CLASSIFIER_PROMPT = """Classify this query as SIMPLE or COMPLEX.

SIMPLE: Single-step. One SQL query, one MongoDB pipeline, one document extraction, one policy check.
COMPLEX: Multi-step. Requires multiple specialists or cross-backend reconciliation.

Reply with exactly one word: SIMPLE or COMPLEX"""

_SPECIALIST_MAP: dict[str, str] = {
    "sql_gen": "sql_gen",
    "mongo_gen": "mongo_query",
    "extract": "extract",
    "policy_action": "policy_action",
    "multitool_plan": "multitool_plan",
    "sql_compose": "sql_gen",
    "cross_recon": "cross_recon",
}


def classify_complexity(query: str, client: anthropic.Anthropic) -> str:
    """Return 'SIMPLE' or 'COMPLEX' for the given query using Haiku."""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10,
        system=[
            {
                "type": "text",
                "text": COMPLEXITY_CLASSIFIER_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": query}],
    )
    text = ""
    for block in response.content:
        if hasattr(block, "text"):
            text = block.text.strip().upper()
            break
    return "COMPLEX" if "COMPLEX" in text else "SIMPLE"


def _infer_specialist(task_class: str) -> str:
    return _SPECIALIST_MAP.get(task_class, "sql_gen")


# ---------------------------------------------------------------------------
# System prompts (PaR + PaR-no-rationale ablation variant)
# ---------------------------------------------------------------------------

PLANNER_SYSTEM_PROMPT = """You are the Planner-as-Router for a multi-agent enterprise workflow system.

Your job is to:
1. Decompose the user query into the MINIMUM number of subtasks needed
2. Assign each subtask to the right specialist agent
3. Assign each subtask to the right model tier (small, mid, or frontier)
4. Identify dependencies between subtasks

CRITICAL DECOMPOSITION RULES:
- Use the FEWEST subtasks that fully answer the query. Do not split work unnecessarily.
- A query asking for ONE SQL query produces ONE sql_gen subtask. Do not split a multi-CTE SQL into multiple sql_gen calls — a single sql_gen subtask can produce a complex multi-CTE query.
- A query asking for ONE MongoDB pipeline produces ONE mongo_query subtask.
- A query asking for ONE document extraction produces ONE extract subtask.
- Combine related queries into a single subtask whenever they share substrate and can run in one call. Multiple metrics from the same SQL warehouse should be one sql_gen with multiple result columns, not separate sql_gen subtasks.

DO NOT HALLUCINATE EXTRA STEPS:
- Do NOT add a policy_action subtask unless the query EXPLICITLY asks for policy evaluation, access control, compliance checking, or governance approval. Renewal recommendations, prioritization, and classification are NOT policy_action — they are part of cross_recon or the calling specialist's output.
- Do NOT add a cross_recon subtask unless the query requires reconciling data from TWO OR MORE distinct sources. Single-source queries do not need reconciliation.
- Do NOT add multitool_plan unless the query explicitly asks for a multi-step tool invocation plan involving the enterprise tool registry.

SPECIALIST AGENT SCOPE:
- sql_gen: Generates ONE SQL query (may have multiple CTEs, window functions, joins). Returns SQL string.
- mongo_query: Generates ONE MongoDB aggregation pipeline. Returns pipeline array.
- extract: Extracts structured fields from documents. Returns JSON matching the requested schema. Handles all fields in one call.
- cross_recon: Reconciles results from two sources (e.g., MongoDB state + SQL history). INCLUDES classification, posture decisions, and recommendation generation as part of reconciliation. Do not add a separate specialist for downstream decisions when cross_recon is already in the plan.
- multitool_plan: Generates a tool-call plan from the 25-tool registry. Only used when the query explicitly requires multi-tool orchestration.
- policy_action: Evaluates a governance decision against a policy registry. Only used when the query asks for compliance, access control, or policy evaluation.

MODEL TIERS:
- small (Haiku 4.5): Simple, explicit tasks. Single-table queries, basic field extraction, straightforward policy checks with one applicable rule.
- mid (Sonnet 4.6): Moderate complexity. Multi-table joins, aggregation pipelines, multi-clause document extraction, multi-policy reasoning.
- frontier (Opus 4.7): High complexity. Multi-CTE SQL with window functions, cross-collection $lookup pipelines, cross-document extraction with inference, multi-signal reconciliation with classification, complex policy interactions with exceptions.

TIER ASSIGNMENT GUIDELINES:
- Assign the minimum tier that will reliably handle the subtask
- When a subtask receives output from a previous node, the upstream quality affects whether this node needs higher capability to compensate
- Budget-sensitive: prefer small tier when the task is genuinely simple

You MUST include a cost_rationale field briefly explaining your tier assignment decisions AND why the plan has the number of subtasks it does (justify both the count and the tier).

EXAMPLES OF MINIMUM DECOMPOSITION:
- "Generate a multi-CTE SQL with LAG and DENSE_RANK..." → 1 subtask (sql_gen, frontier). NOT 3 subtasks.
- "Reconcile Adobe contracts with Q4 spend and classify renewal posture" → 3 subtasks (mongo_query + sql_gen + cross_recon). NOT 5 subtasks. The classification is part of cross_recon, not a separate policy_action.
- "Extract the contract date and value from this document" → 1 subtask (extract, small). NOT split into separate field extractions.

Always produce valid JSON matching the Plan schema. Be specific in subtask descriptions."""


PLANNER_SYSTEM_PROMPT_NO_RATIONALE = """You are the Planner-as-Router for a multi-agent enterprise workflow system.

Your job is to:
1. Decompose the user query into a sequence of subtasks
2. Assign each subtask to the right specialist agent
3. Assign each subtask to the right model tier (small, mid, or frontier)
4. Identify dependencies between subtasks

SPECIALIST AGENTS available:
- sql_gen, mongo_query, extract, cross_recon, multitool_plan, policy_action

MODEL TIERS:
- small (Haiku 4.5): Simple tasks
- mid (Sonnet 4.6): Moderate complexity
- frontier (Opus 4.7): High complexity

Always produce valid JSON matching the Plan schema."""


# ---------------------------------------------------------------------------
# Planner tool schema (structured output via tool_use)
# ---------------------------------------------------------------------------

PLANNER_TOOL = {
    "name": "produce_plan",
    "description": "Produce a structured plan with subtasks and tier assignments",
    "input_schema": {
        "type": "object",
        "properties": {
            "subtasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "description": {"type": "string"},
                        "specialist": {
                            "type": "string",
                            "enum": [
                                "sql_gen",
                                "mongo_query",
                                "extract",
                                "cross_recon",
                                "multitool_plan",
                                "policy_action",
                            ],
                        },
                        "tier": {"type": "string", "enum": ["small", "mid", "frontier"]},
                        "depends_on": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["id", "description", "specialist", "tier"],
                },
            },
            "cost_rationale": {"type": "string"},
        },
        "required": ["subtasks", "cost_rationale"],
    },
}


PLANNER_TOOL_NO_RATIONALE = {
    "name": "produce_plan",
    "description": "Produce a structured plan with subtasks and tier assignments",
    "input_schema": {
        "type": "object",
        "properties": {
            "subtasks": PLANNER_TOOL["input_schema"]["properties"]["subtasks"],  # type: ignore[index]
            "cost_rationale": {"type": "string", "default": ""},
        },
        "required": ["subtasks"],
    },
}


# ---------------------------------------------------------------------------
# Planner invocation
# ---------------------------------------------------------------------------


def _run_full_planner(
    state: WorkflowState,
    client: anthropic.Anthropic,
    no_rationale: bool = False,
) -> WorkflowState:
    """Run the full Claude Haiku 4.5 (small tier) planner and charge small-tier cost."""
    system_prompt = PLANNER_SYSTEM_PROMPT_NO_RATIONALE if no_rationale else PLANNER_SYSTEM_PROMPT
    tool = PLANNER_TOOL_NO_RATIONALE if no_rationale else PLANNER_TOOL

    response = client.messages.create(  # type: ignore[call-overload]
        model=PLANNER_MODEL,
        max_tokens=1000,
        system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
        tools=[tool],
        tool_choice={"type": "tool", "name": "produce_plan"},
        messages=[{"role": "user", "content": state.query}],
    )

    tool_block = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_block is None:
        raise ValueError(f"Planner did not produce a tool_use block for task {state.task_id}")

    plan_data = tool_block.input
    if no_rationale and "cost_rationale" not in plan_data:
        plan_data["cost_rationale"] = ""
    plan = Plan(**plan_data)

    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    cached_tokens = getattr(response.usage, "cache_read_input_tokens", 0)
    planner_cost = compute_cost(
        tier="small",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_tokens=cached_tokens,
    )

    state.plan = plan
    state.pending_subtasks = list(plan.subtasks)
    state.cumulative_spend_usd += planner_cost
    return state


def run_planner(
    state: WorkflowState,
    client: anthropic.Anthropic,
    no_rationale: bool = False,
) -> WorkflowState:
    """
    Cascaded planner: classify complexity with Haiku first.

    SIMPLE tasks get a single-subtask plan at small tier immediately —
    no full-planner call. COMPLEX tasks fall through to the full Claude Haiku 4.5 (small tier) planner.
    no_rationale=True activates the PaR-no-rationale ablation variant.
    """
    complexity = classify_complexity(state.query, client)

    if complexity == "SIMPLE":
        specialist = _infer_specialist(state.task_class or "")
        plan = Plan(
            subtasks=[
                Subtask(
                    id="subtask_1",
                    description=state.query,
                    specialist=specialist,  # type: ignore[arg-type]
                    tier="small",
                    depends_on=[],
                )
            ],
            cost_rationale="Simple task — Haiku classifier, small tier",
        )
        state.plan = plan
        state.pending_subtasks = list(plan.subtasks)
        return state

    # COMPLEX: run full Claude Haiku 4.5 (small tier) planner
    return _run_full_planner(state, client, no_rationale=no_rationale)
