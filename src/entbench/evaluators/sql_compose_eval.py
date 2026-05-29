"""
SQL-Compose evaluator — multi-stage:
1. SQL step uses sql_eval
2. Downstream consumer check (narrative presence or per-entity classification)
"""

from __future__ import annotations

from typing import Any

from .sql_eval import evaluate_sql


def _find_node_output(trace: dict, specialist: str) -> dict | None:
    """Find first node_result with matching specialist; return its output."""
    for nr in trace.get("node_results", []):
        if nr.get("specialist") == specialist:
            return nr.get("output")
    return None


def _check_narrative_presence(consumer_output: Any, required_phrases: list[str]) -> bool:
    """Each narrative must contain all required phrases."""
    if not consumer_output:
        return False
    if isinstance(consumer_output, dict):
        narratives = (
            consumer_output.get("narratives", [])
            or consumer_output.get("publisher_summaries", [])
            or consumer_output.get("recommendations", [])
        )
    else:
        return False
    if not narratives:
        return False
    for entity in narratives:
        text = " ".join(str(v) for v in entity.values() if isinstance(v, str)).lower()
        for phrase in required_phrases:
            if phrase.lower() not in text:
                return False
    return True


def _check_classification_per_entity(consumer_output: Any) -> bool:
    """Each entity has a classification field with valid value."""
    if not isinstance(consumer_output, dict):
        return False
    entities = (
        consumer_output.get("publisher_summaries")
        or consumer_output.get("recommendations")
        or consumer_output.get("narratives")
    )
    if not entities:
        return False
    for entity in entities:
        if not any(
            k in entity for k in ["classification", "recommendation", "posture", "renewal_posture"]
        ):
            return False
    return True


def evaluate_sql_compose(task: dict, trace: dict) -> tuple[bool, str]:
    """Evaluate SQL-Compose. Reads trace, validates each stage."""
    gold_workflow = task.get("gold_workflow", {})
    step_1_gold = gold_workflow.get("step_1_sql", {})

    sql_node_output = _find_node_output(trace, "sql_gen")
    if sql_node_output is None:
        return False, "no_sql_node"

    # Synthetic task with gold_sql from step_1
    sql_task = dict(task)
    sql_task["gold_sql"] = step_1_gold.get("query", "")
    sql_ok, sql_reason = evaluate_sql(sql_task, sql_node_output)
    if not sql_ok:
        return False, f"step1_sql_fail: {sql_reason}"

    consumer_output = None
    for spec in ["policy_action", "extract", "cross_recon"]:
        consumer_output = _find_node_output(trace, spec)
        if consumer_output is not None:
            break

    if consumer_output is None:
        return False, "no_consumer_node"

    evaluator_spec = task.get("evaluator", {})
    stages = evaluator_spec.get("stages", [])
    consumer_stage: dict[Any, Any] = next((s for s in stages if s.get("name") == "consumer_correct"), {})
    consumer_type = consumer_stage.get("type", "classification_per_entity")

    if consumer_type == "narrative_presence_check":
        required = consumer_stage.get("required_phrases_per_entity", [])
        if _check_narrative_presence(consumer_output, required):
            return True, "ok"
        return False, "step2_consumer_narrative_check_failed"

    if _check_classification_per_entity(consumer_output):
        return True, "ok"
    return False, "step2_consumer_classification_missing"
