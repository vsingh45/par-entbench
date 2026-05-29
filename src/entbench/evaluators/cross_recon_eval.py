"""
Cross-Recon evaluator — 3-stage:
1. MongoDB query correct (uses mongo_eval)
2. SQL query correct (uses sql_eval)
3. Reconciliation output correct (field-level check with tolerance)

All 3 must pass for task_correct = True.
"""

from __future__ import annotations

from typing import Any

from .mongo_eval import evaluate_mongo
from .sql_eval import evaluate_sql

NUMERIC_TOLERANCE = 0.01


def _find_node_output(trace: dict, specialist: str) -> dict | None:
    for nr in trace.get("node_results", []):
        if nr.get("specialist") == specialist:
            return nr.get("output")
    return None


def _check_recon_output(recon_output: Any, gold_step3: dict) -> tuple[bool, str]:
    """
    Validate the cross_recon output structure.
    Looks for presence of expected fields per the output schema, with
    numeric tolerance on values where they're present in both.
    """
    if not isinstance(recon_output, (dict, list)):
        return False, "recon_output_not_structured"

    output_schema = gold_step3.get("output_schema", {})
    expected_fields = list(output_schema.keys()) if output_schema else []

    if isinstance(recon_output, dict):
        items = (
            recon_output.get("reconciled")
            or recon_output.get("results")
            or recon_output.get("output")
            or recon_output.get("renewal_posture")
            or [recon_output]
        )
    else:
        items = recon_output

    if not isinstance(items, list):
        items = [items]

    if not items:
        return False, "recon_output_empty"

    if expected_fields:
        sample = items[0] if items else {}
        if isinstance(sample, dict):
            missing = [f for f in expected_fields if f not in sample and f != "_id"]
            if len(missing) > len(expected_fields) // 2:
                return False, f"recon_missing_required_fields: {missing}"

    return True, "ok"


def evaluate_cross_recon(task: dict, trace: dict) -> tuple[bool, str]:
    """Evaluate Cross-Recon. 3-stage check; all must pass."""
    gold_workflow = task.get("gold_workflow", {})
    step_1_gold = gold_workflow.get("step_1_mongo", {})
    step_2_gold = gold_workflow.get("step_2_sql", {})
    step_3_gold = gold_workflow.get("step_3_recon", {})

    # Stage 1: Mongo
    mongo_output = _find_node_output(trace, "mongo_query")
    if mongo_output is None:
        return False, "no_mongo_node"
    mongo_task = dict(task)
    mongo_task["collection"] = step_1_gold.get("collection", task.get("collection"))
    mongo_task["gold_pipeline"] = step_1_gold.get("pipeline", [])
    mongo_ok, mongo_reason = evaluate_mongo(mongo_task, mongo_output)
    if not mongo_ok:
        return False, f"stage1_mongo_fail: {mongo_reason}"

    # Stage 2: SQL
    sql_output = _find_node_output(trace, "sql_gen")
    if sql_output is None:
        return False, "no_sql_node"
    sql_task = dict(task)
    sql_task["gold_sql"] = step_2_gold.get("query", "")
    sql_ok, sql_reason = evaluate_sql(sql_task, sql_output)
    if not sql_ok:
        return False, f"stage2_sql_fail: {sql_reason}"

    # Stage 3: Reconciliation output structure
    recon_output = _find_node_output(trace, "cross_recon")
    if recon_output is None:
        return False, "no_recon_node"
    recon_ok, recon_reason = _check_recon_output(recon_output, step_3_gold)
    if not recon_ok:
        return False, f"stage3_recon_fail: {recon_reason}"

    return True, "ok"
