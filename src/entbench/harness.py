"""
entbench/harness.py — Main experiment runner for EntBench.

Usage examples:
  par-entbench --verify-setup
  par-entbench --tasks pilot_100 --routers all --seeds 1 --output results/pilot/
  par-entbench --tasks all --routers all --seeds 3 --output results/full/
  par-entbench --tasks capability_calibration --routers all_tiers --output results/standalone/
  par-entbench --compute-rho results/full/ --standalone results/standalone/ \\
               --output results/rho_analysis.json
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path

import anthropic

from baselines.routers import ROUTER_REGISTRY
from par.dispatcher import dispatch_plan
from par.observability import (
    DEFAULT_KILL_SWITCH_USD,
    emit_trace,
    finalize_trace,
    record_node_result,
)
from par.batch_planner import BatchPlanner
from par.planner import run_planner
from par.types import WorkflowState, WorkflowTrace

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TASK_CLASSES = [
    "sql_gen",
    "sql_compose",
    "mongo_gen",
    "cross_recon",
    "extract",
    "multitool_plan",
    "policy_action",
]

CAPABILITY_CLASSES = ["sql_gen", "mongo_gen", "extract"]
COMPOSITIONAL_CLASSES = ["sql_compose", "cross_recon", "multitool_plan", "policy_action"]


def _find_tasks_dir() -> Path:
    """Locate the entbench/tasks directory. Looks in CWD first, then upward."""
    candidates = [
        Path.cwd() / "entbench" / "tasks",
        Path(__file__).parent.parent.parent.parent / "entbench" / "tasks",
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(
        "Could not locate entbench/tasks/. Run from the project root or set ENTBENCH_TASKS_DIR."
    )


def _find_config_path() -> Path:
    """Locate entbench/config.yaml."""
    candidates = [
        Path.cwd() / "entbench" / "config.yaml",
        Path(__file__).parent.parent.parent.parent / "entbench" / "config.yaml",
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError("Could not locate entbench/config.yaml.")


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def load_config(config_path: str | None = None) -> dict:
    import yaml

    path = Path(config_path) if config_path else _find_config_path()
    with open(path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Task loading
# ---------------------------------------------------------------------------


def load_tasks(task_set: str, tasks_dir: str | None = None) -> list[dict]:
    """Load tasks from disk; filter by task_set."""
    base = Path(tasks_dir) if tasks_dir else _find_tasks_dir()
    all_tasks = []
    for cls in TASK_CLASSES:
        cls_dir = base / cls
        if not cls_dir.exists():
            continue
        for task_file in sorted(cls_dir.glob("*.json")):
            with open(task_file) as f:
                task = json.load(f)
                task["task_class"] = cls
                all_tasks.append(task)

    if task_set == "all":
        return all_tasks
    elif task_set == "compositional":
        return [t for t in all_tasks if t["task_class"] in COMPOSITIONAL_CLASSES]
    elif task_set == "capability_calibration":
        return [t for t in all_tasks if t["task_class"] in CAPABILITY_CLASSES]
    elif task_set == "pilot_100":
        sampled = []
        for cls in TASK_CLASSES:
            cls_tasks = [t for t in all_tasks if t["task_class"] == cls]
            n = min(15, len(cls_tasks))
            if cls_tasks:
                sampled.extend(random.sample(cls_tasks, n))
        return sampled[:100]
    else:
        raise ValueError(f"Unknown task set: {task_set}")


# ---------------------------------------------------------------------------
# Specialist registry
# ---------------------------------------------------------------------------


def make_specialist_registry(client: anthropic.Anthropic) -> dict:
    """
    Build {specialist_name: callable} mapping.
    Each callable: (subtask, tier, upstream_outputs, client) -> (result_dict, usage_dict)
    """
    from par.dispatcher import TIER_MODELS

    def _call_specialist(subtask, tier, upstream_outputs, client, system_prompt, task_context=None, max_tokens=2000):
        model = TIER_MODELS[tier]

        # Build rich user message including task-specific context
        msg = {
            "task": subtask.description,
            "upstream_outputs": upstream_outputs,
        }
        if task_context:
            # Pass through fields the specialist needs to do its job
            for field in [
                "query",           # original user query
                "input_document",  # for extract tasks
                "context",         # for policy_action (user/role/resource/action)
                "policy_registry", # for policy_action
                "candidate_actions",# for policy_action
                "gold_plan",       # NOT passed (would be cheating) — excluded
            ]:
                if field in task_context and field != "gold_plan":
                    msg[field] = task_context[field]

        user_message = json.dumps(msg)

        response = client.messages.create(
            model=model,
            max_tokens=800,
            system=[{"type": "text", "text": system_prompt,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_message}],
        )

        output_text = "".join(b.text for b in response.content if hasattr(b, "text"))

        # Strip markdown fences if present
        import re as _re
        output_text = _re.sub(r"^```(?:json)?\s*", "", output_text.strip())
        output_text = _re.sub(r"\s*```$", "", output_text.strip())

        try:
            result = json.loads(output_text)
            # NodeResult.output must be a dict — wrap bare lists
            if isinstance(result, list):
                result = {"items": result}
        except json.JSONDecodeError:
            result = {"raw_output": output_text}

        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "cached_tokens": getattr(response.usage, "cache_read_input_tokens", 0),
        }
        return result, usage

    prompts = {
        "sql_gen": """You are a SQL specialist for the EntBench Postgres warehouse.

DATABASE SCHEMA:
- consumption_facts(event_id, license_id, publisher, product, event_date DATE,
  event_type, amount_usd NUMERIC, daily_active_seats INT, user_id, fiscal_year INT, fiscal_quarter INT)
- invoice_facts(invoice_id, contract_id, vendor_name, invoice_date DATE, due_date DATE,
  paid_date DATE, amount_usd NUMERIC, status)
- access_log_facts(log_id, user_id, permission, resource, access_time TIMESTAMP, action, result)
- customer(c_custkey, c_name, c_nationkey, c_mktsegment, c_acctbal NUMERIC)
- orders(o_orderkey, o_custkey, o_orderstatus, o_totalprice NUMERIC, o_orderdate DATE, o_orderpriority)
- lineitem(l_orderkey, l_linenumber, l_quantity NUMERIC, l_extendedprice NUMERIC,
  l_discount NUMERIC, l_tax NUMERIC, l_returnflag, l_linestatus, l_shipdate DATE)

RULES:
- Use date ranges (event_date >= '2024-01-01') not EXTRACT(YEAR FROM ...) for fiscal year filters
- Fiscal quarter 4 = October-December (fiscal_quarter = 4)
- Always qualify column names if joining multiple tables
- Return ONLY valid JSON, no explanation, no markdown fences

OUTPUT FORMAT (return exactly this JSON structure):
{"sql": "SELECT ... FROM ... WHERE ..."}""",

        "mongo_query": """You are a MongoDB specialist for SAM operational collections.

COLLECTIONS AND SCHEMAS:
- sam_licenses: {license_id, publisher, product, contract_value_usd, seat_count,
  cost_per_seat_usd, term_start ISODate, term_end ISODate, renewal_terms,
  assigned_team, status, criticality_tier}
- sam_seat_assignments: {assignment_id, license_id, user_id, assigned_date ISODate,
  last_active_date ISODate (may be missing/null), status}
- billing_contracts: {contract_id, vendor_name, term_months, annual_value_usd,
  payment_terms_days, early_payment_discount_pct, status}
- iam_roles: {role_name, permissions [array of strings], is_elevated bool}

RULES:
- For null/missing field checks use: {"$or": [{"field": null}, {"field": {"$exists": false}}]}
- Use $lookup for joins between collections
- Do NOT add $project stages unless explicitly asked — return full documents
- Return ONLY the aggregation pipeline stages needed to answer the query

EXAMPLE — "Find active Adobe licenses over $50k":
{"collection": "sam_licenses", "pipeline": [{"$match": {"publisher": "Adobe", "status": "active", "contract_value_usd": {"$gt": 50000}}}]}

EXAMPLE — "Group by publisher, sum contract values":
{"collection": "sam_licenses", "pipeline": [{"$group": {"_id": "$publisher", "total": {"$sum": "$contract_value_usd"}}}]}

Return ONLY valid JSON, no explanation, no markdown fences:
{"collection": "COLLECTION_NAME", "pipeline": [STAGE1, STAGE2, ...]}""",

        "extract": """You are a document extraction specialist.

Your job is to extract structured fields from the document provided in the task.
Extract ONLY fields that are explicitly present in the document.
For missing fields, use null (not empty string).
Normalize dates to YYYY-MM-DD format.
Normalize currency to a float (remove $ and commas).

RULES:
- Return ONLY valid JSON matching the schema implied by the task
- No explanation, no markdown fences, no extra fields
- null for missing, not "" (empty string)

OUTPUT FORMAT example for a contract:
{"effective_date": "2024-01-15", "expiration_date": "2025-01-14", "total_contract_value_usd": 145000.0}""",

        "cross_recon": """You are a cross-backend reconciliation specialist.

You receive outputs from a MongoDB query (operational state) and a SQL query (historical data).
Your job is to reconcile them using LEFT JOIN semantics with MongoDB as the primary source.

RECONCILIATION RULES:
- Every entity in the MongoDB result must appear in the output
- Entities in MongoDB but NOT in SQL results: use null/0 for missing SQL metrics
- Classify each entity based on the combined signal (both sources)
- Common classifications: expand, hold, reduce, no_recent_activity, at_risk, stable, growing

RULES:
- Return ONLY valid JSON, no explanation, no markdown fences

OUTPUT FORMAT:
{"reconciled": [{"entity_key": "...", "mongo_value": ..., "sql_value": ..., "classification": "..."}]}""",

        "multitool_plan": """You are a tool orchestration specialist for an enterprise tool registry.

AVAILABLE TOOLS (use EXACTLY these tool names):
- mongo.find, mongo.update, mongo.aggregate
- sql.snowflake.query, sql.postgres.query
- email.send, slack.post_message
- iam.check_permission, iam.grant_role, iam.revoke_role
- audit.log_action
- file.read, file.write
- calendar.create_event, calendar.list_events
- jira.create_ticket, jira.update_ticket, jira.list_tickets
- confluence.create_page, confluence.update_page
- github.create_pr, github.list_issues
- pagerduty.create_incident, pagerduty.resolve_incident
- datadog.query_metric, datadog.list_alerts

RULES:
- Use ONLY tool names from the list above (exact spelling, with dots)
- For governance operations: always check iam.check_permission FIRST
- For mutations: always log with audit.log_action after the mutation
- Reference previous step outputs as $N.field (e.g. $1.results)
- Return ONLY valid JSON, no explanation, no markdown fences

OUTPUT FORMAT:
{"plan": [{"tool": "mongo.find", "arguments": {"collection": "...", "filter": {}}, "depends_on": []}, {"tool": "slack.post_message", "arguments": {"channel": "#sam-team", "message": "Results: $1.results"}, "depends_on": [1]}]}""",

        "policy_action": """You are a policy evaluation specialist.

You receive a context (user, role, resource, action) and a policy registry.
Evaluate whether the action is permitted under each applicable policy.

COMPLIANCE VALUES (use EXACTLY one of these per policy):
- "pass" — action permitted under this policy
- "pass_conditional" — permitted with conditions/constraints
- "fail" — action denied by this policy
- "not_applicable" — this policy does not apply to this action
- "pending_review" — requires human review before decision

ACTION VALUES (use EXACTLY one):
- "allow" — action permitted
- "allow_with_constraints" — permitted with logged constraints
- "deny_with_reason" — denied, reason required
- "deny_pending_approvals" — denied until approvals obtained
- "escalate" — requires escalation to higher authority

RULES:
- Evaluate ALL policies in the registry, even if not applicable
- For not_applicable: still include in policy_compliance with value "not_applicable"
- Return ONLY valid JSON, no explanation, no markdown fences

OUTPUT FORMAT:
{"selected_action": "allow", "policy_compliance": {"POL-001": "pass", "POL-002": "not_applicable"}, "reason": "Brief explanation", "applied_constraints": []}""",
    }

    specialist_max_tokens = {"cross_recon": 1000}

    registry = {}
    for name, prompt in prompts.items():

        def make_fn(n, p, mt=2000):
            def fn(subtask, tier, upstream_outputs, client, task_context=None):
                return _call_specialist(subtask, tier, upstream_outputs, client, p, task_context, max_tokens=mt)

            fn.__name__ = n
            return fn

        registry[name] = make_fn(name, prompt, mt=specialist_max_tokens.get(name, 2000))

    # Override mongo_query with tool_use version for guaranteed structured output
    MONGO_TOOL = {
        "name": "generate_pipeline",
        "description": "Generate a MongoDB aggregation pipeline",
        "input_schema": {
            "type": "object",
            "properties": {
                "collection": {
                    "type": "string",
                    "description": "Collection name to query",
                    "enum": ["sam_licenses", "sam_seat_assignments", "billing_contracts", "iam_roles"],
                },
                "pipeline": {
                    "type": "array",
                    "description": "MongoDB aggregation pipeline stages",
                    "items": {"type": "object"},
                },
            },
            "required": ["collection", "pipeline"],
        },
    }

    mongo_system = prompts["mongo_query"]

    def mongo_tool_fn(subtask, tier, upstream_outputs, client, task_context=None):
        from par.dispatcher import TIER_MODELS
        model = TIER_MODELS[tier]
        msg = {"task": subtask.description, "upstream_outputs": upstream_outputs}
        if task_context:
            for field in ["query", "collection"]:
                if field in task_context:
                    msg[field] = task_context[field]
        response = client.messages.create(
            model=model,
            max_tokens=800,
            system=[{"type": "text", "text": mongo_system,
                     "cache_control": {"type": "ephemeral"}}],
            tools=[MONGO_TOOL],
            tool_choice={"type": "tool", "name": "generate_pipeline"},
            messages=[{"role": "user", "content": json.dumps(msg)}],
        )
        tool_block = next((b for b in response.content if b.type == "tool_use"), None)
        if tool_block:
            result = tool_block.input
        else:
            output_text = "".join(b.text for b in response.content if hasattr(b, "text"))
            try:
                result = json.loads(output_text)
                if isinstance(result, list):
                    result = {"items": result}
            except json.JSONDecodeError:
                result = {"raw_output": output_text}
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "cached_tokens": getattr(response.usage, "cache_read_input_tokens", 0),
        }
        return result, usage

    registry["mongo_query"] = mongo_tool_fn

    return registry


# ---------------------------------------------------------------------------
# Task execution
# ---------------------------------------------------------------------------


def run_task(
    task: dict,
    router: str,
    seed: int,
    client: anthropic.Anthropic,
    specialist_registry: dict,
    cumulative_spend: float,
    kill_switch_ceiling: float,
    output_dir: str,
    batch_planner: BatchPlanner | None = None,
) -> tuple[WorkflowTrace, float, bool]:
    random.seed(seed)

    # Wrap specialist registry to inject task context into every call
    task_context = {k: v for k, v in task.items() if k not in ("gold_sql", "gold_pipeline", "gold_extraction", "gold_output", "gold_plan", "gold_workflow")}
    context_registry = {}
    for name, fn in specialist_registry.items():
        def make_ctx_fn(f, ctx):
            def ctx_fn(subtask, tier, upstream_outputs, client):
                return f(subtask, tier, upstream_outputs, client, task_context=ctx)
            ctx_fn.__name__ = f.__name__
            return ctx_fn
        context_registry[name] = make_ctx_fn(fn, task_context)

    state = WorkflowState(
        query=task["query"],
        task_id=task["task_id"],
        task_class=task.get("task_class"),
        router=router,
        seed=seed,
        cumulative_spend_usd=cumulative_spend,
    )

    trace = WorkflowTrace(
        task_id=task["task_id"],
        task_class=task.get("task_class"),
        router=router,
        seed=seed,
        cumulative_spend_usd=cumulative_spend,
    )

    no_rationale = router == "par_no_rationale"
    if batch_planner is not None:
        batch_planner.no_rationale = no_rationale
        state = batch_planner.run(state)
    else:
        state = run_planner(state, client, no_rationale=no_rationale)
    trace.plan = state.plan

    if router in ("par", "par_no_rationale"):
        node_results, kill_switch = dispatch_plan(
            state, client, context_registry, kill_switch_ceiling
        )
    else:
        dispatch_fn = ROUTER_REGISTRY[router]
        node_results, kill_switch = dispatch_fn(
            state, client, context_registry, kill_switch_ceiling
        )

    for nr in node_results:
        trace, _ = record_node_result(trace, nr, kill_switch_ceiling)

    task_correct = evaluate_task(task, trace)
    trace = finalize_trace(trace, task_correct)

    emit_trace(trace, output_dir)

    return trace, trace.cumulative_spend_usd, kill_switch


def evaluate_task(task: dict, trace: WorkflowTrace) -> bool:
    """Dispatch to class-specific evaluator."""
    from entbench.evaluators import evaluate

    correct, _reason = evaluate(task, trace)
    return correct


def reeval_traces(results_dir: str) -> None:
    """
    Re-score existing trace files using current evaluators. No API calls.

    Loads each JSON trace, finds the corresponding task definition, runs the
    class-specific evaluator, and updates task_correct in place.
    """
    from entbench.evaluators import evaluate

    tasks_dir = _find_tasks_dir()
    task_index: dict[str, dict] = {}
    for cls in TASK_CLASSES:
        cls_dir = tasks_dir / cls
        if not cls_dir.exists():
            continue
        for task_file in sorted(cls_dir.glob("*.json")):
            with open(task_file) as f:
                t = json.load(f)
                t["task_class"] = cls
                task_index[t["task_id"]] = t

    paths = sorted(Path(results_dir).glob("*.json"))
    counts = {"reevaluated": 0, "task_correct": 0, "task_incorrect": 0, "task_not_found": 0}
    reasons: dict[str, int] = {}

    for p in paths:
        with open(p) as f:
            trace = json.load(f)

        task = task_index.get(trace["task_id"])
        if task is None:
            counts["task_not_found"] += 1
            continue

        correct, reason = evaluate(task, trace)
        trace["task_correct"] = correct
        trace["evaluator_reason"] = reason
        counts["reevaluated"] += 1
        if correct:
            counts["task_correct"] += 1
        else:
            counts["task_incorrect"] += 1
            reasons[reason] = reasons.get(reason, 0) + 1

        with open(p, "w") as f:
            json.dump(trace, f, indent=2)

    print(f"Re-evaluation complete for {results_dir}")
    print(f"  Re-evaluated: {counts['reevaluated']}")
    print(f"  Correct: {counts['task_correct']}")
    print(f"  Incorrect: {counts['task_incorrect']}")
    print(f"  Task not found: {counts['task_not_found']}")
    if reasons:
        print("\nIncorrect reasons:")
        for r, n in sorted(reasons.items(), key=lambda x: -x[1]):
            print(f"  {n:>4}  {r}")


# ---------------------------------------------------------------------------
# ρ computation
# ---------------------------------------------------------------------------


def compute_rho(workflow_dir: str, standalone_dir: str, output_path: str) -> dict:
    """
    Compute ρ using two-phase measurement:
      naive_predicted = ∏ over nodes of standalone_accuracy(tier, class)
      ρ = (1 − A_actual) / (1 − Â_naive)
    """
    standalone_acc: dict[tuple[str, str], float] = {}
    standalone_counts: dict[tuple[str, str], list[bool]] = {}

    for f in Path(standalone_dir).glob("*.json"):
        with open(f) as fh:
            t = json.load(fh)
        for nr in t.get("node_results", []):
            key = (nr["tier_assigned"], nr["specialist"])
            standalone_counts.setdefault(key, []).append(bool(t.get("task_correct", False)))

    for key, results in standalone_counts.items():
        standalone_acc[key] = sum(results) / len(results) if results else 1.0

    traces = []
    for f in Path(workflow_dir).glob("*.json"):
        with open(f) as fh:
            traces.append(json.load(fh))

    by_router: dict[str, list[dict]] = {}
    for t in traces:
        by_router.setdefault(t["router"], []).append(t)

    rho_results = {}
    for router, router_traces in by_router.items():
        comp_traces = [t for t in router_traces if t.get("task_class") in COMPOSITIONAL_CLASSES]
        if not comp_traces:
            continue

        actual_accuracy = sum(1 for t in comp_traces if t.get("task_correct")) / len(comp_traces)

        naive_predictions = []
        for t in comp_traces:
            naive = 1.0
            for nr in t.get("node_results", []):
                key = (nr["tier_assigned"], nr["specialist"])
                naive *= standalone_acc.get(key, 1.0)
            naive_predictions.append(naive)

        naive_accuracy = (
            sum(naive_predictions) / len(naive_predictions) if naive_predictions else 1.0
        )
        rho = 1.0 if naive_accuracy >= 1.0 else (1 - actual_accuracy) / (1 - naive_accuracy)

        rho_results[router] = {
            "rho": round(rho, 4),
            "actual_accuracy": round(actual_accuracy, 4),
            "naive_predicted_accuracy": round(naive_accuracy, 4),
            "n_compositional_tasks": len(comp_traces),
        }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(rho_results, f, indent=2)

    return rho_results


# ---------------------------------------------------------------------------
# Setup verification
# ---------------------------------------------------------------------------


def verify_setup() -> bool:
    import subprocess

    print("Verifying setup...")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("FAIL: ANTHROPIC_API_KEY not set")
        return False
    print("OK: ANTHROPIC_API_KEY is set")

    try:
        r = subprocess.run(
            ["psql", "-h", "localhost", "-U", "entbench", "-d", "entbench", "-c", "SELECT 1"],
            capture_output=True,
            timeout=5,
            env={**os.environ, "PGPASSWORD": "entbench"},
        )
        if r.returncode == 0:
            print("OK: Postgres is accessible")
        else:
            print(f"FAIL: Postgres: {r.stderr.decode()}")
            return False
    except Exception as e:
        print(f"FAIL: Postgres check failed: {e}")
        return False

    try:
        r = subprocess.run(
            ["mongosh", "--eval", "db.runCommand({ping:1})", "--quiet"],
            capture_output=True,
            timeout=5,
        )
        if r.returncode == 0:
            print("OK: MongoDB is accessible")
        else:
            print("FAIL: MongoDB connection failed")
            return False
    except Exception as e:
        print(f"FAIL: MongoDB check failed: {e}")
        return False

    try:
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": "ping"}],
        )
        print("OK: Anthropic API is accessible")
    except Exception as e:
        print(f"FAIL: Anthropic API check failed: {e}")
        return False

    print("\nAll setup checks passed. Ready to run experiments.")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="EntBench experiment harness")
    parser.add_argument(
        "--tasks",
        default="all",
        choices=["all", "compositional", "capability_calibration", "pilot_100"],
    )
    parser.add_argument(
        "--routers",
        default="all",
        help="Comma-separated router names, 'all', or 'all_tiers' for standalone",
    )
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--output", default="results/")
    parser.add_argument("--verify-setup", action="store_true")
    parser.add_argument("--resume", type=str, default=None)
    parser.add_argument(
        "--compute-rho",
        type=str,
        default=None,
        help="Path to workflow results dir for ρ computation",
    )
    parser.add_argument(
        "--standalone",
        type=str,
        default=None,
        help="Path to standalone results dir for ρ naive baseline",
    )
    parser.add_argument("--rho-output", default="results/rho_analysis.json")
    parser.add_argument(
        "--reeval",
        type=str,
        default=None,
        help="Path to results dir; re-score existing traces with current evaluators (no API calls)",
    )
    parser.add_argument("--kill-switch-usd", type=float, default=DEFAULT_KILL_SWITCH_USD)
    parser.add_argument(
        "--batch-plan",
        action="store_true",
        help="Generate one template plan per task class and reuse it (saves planner API calls)",
    )
    args = parser.parse_args()

    if args.verify_setup:
        sys.exit(0 if verify_setup() else 1)

    if args.reeval:
        reeval_traces(args.reeval)
        sys.exit(0)

    if args.compute_rho:
        if not args.standalone:
            print("ERROR: --compute-rho requires --standalone <dir>")
            sys.exit(1)
        rho = compute_rho(args.compute_rho, args.standalone, args.rho_output)
        print(f"ρ analysis written to {args.rho_output}")
        for router, result in rho.items():
            print(f"  {router}: ρ={result['rho']}, accuracy={result['actual_accuracy']}")
        sys.exit(0)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    specialist_registry = make_specialist_registry(client)

    tasks = load_tasks(args.tasks)

    if args.routers == "all":
        routers = ["par"] + list(ROUTER_REGISTRY.keys()) + ["par_no_rationale"]
    elif args.routers == "all_tiers":
        routers = ["all_small", "all_frontier"]
    else:
        routers = args.routers.split(",")

    seeds = list(range(1, args.seeds + 1))

    print(f"Running {len(tasks)} tasks × {len(routers)} routers × {len(seeds)} seeds")
    print(f"Total combinations: {len(tasks) * len(routers) * len(seeds)}")
    print(f"Kill-switch ceiling: ${args.kill_switch_usd}")
    if args.batch_plan:
        print("Batch planning: ON (one planner call per task class per router+seed)")

    cumulative_spend = 0.0
    completed = 0
    total = len(tasks) * len(routers) * len(seeds)

    # One BatchPlanner per (router, seed) so templates accumulate across tasks
    # in the same class but don't bleed across routing strategies or seeds.
    batch_planners: dict[tuple[str, int], BatchPlanner] = {}

    for task in tasks:
        for router in routers:
            if router == "par_no_rationale" and task.get("task_class") != "cross_recon":
                continue

            for seed in seeds:
                if cumulative_spend >= args.kill_switch_usd:
                    print(f"\nKill-switch triggered at ${cumulative_spend:.2f}")
                    print(f"Completed {completed}/{total}")
                    sys.exit(0)

                batch_planner: BatchPlanner | None = None
                if args.batch_plan:
                    key = (router, seed)
                    if key not in batch_planners:
                        batch_planners[key] = BatchPlanner(client)
                    batch_planner = batch_planners[key]

                try:
                    trace, cumulative_spend, kill_switch = run_task(
                        task=task,
                        router=router,
                        seed=seed,
                        client=client,
                        specialist_registry=specialist_registry,
                        cumulative_spend=cumulative_spend,
                        kill_switch_ceiling=args.kill_switch_usd,
                        output_dir=args.output,
                        batch_planner=batch_planner,
                    )
                    completed += 1
                    if completed % 10 == 0:
                        print(
                            f"Progress: {completed}/{total} | "
                            f"Spend: ${cumulative_spend:.2f} | "
                            f"Last: {task['task_id']} ({router}, seed {seed})"
                        )
                except Exception as e:
                    print(f"ERROR on {task['task_id']} ({router}, seed {seed}): {e}")
                    continue

    print(f"\nDone. {completed}/{total} completed.")
    print(f"Total spend: ${cumulative_spend:.2f}")
    print(f"Results in: {args.output}")


if __name__ == "__main__":
    main()
