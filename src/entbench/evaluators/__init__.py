"""
EntBench evaluator dispatcher.

Entry point: evaluate(task, trace) -> (bool, str)

Routes the task to its class-specific evaluator based on task_class.
"""
from __future__ import annotations

from .cross_recon_eval import evaluate_cross_recon
from .extract_eval import evaluate_extract
from .mongo_eval import evaluate_mongo
from .multitool_eval import evaluate_multitool
from .policy_action_eval import evaluate_policy_action
from .sql_compose_eval import evaluate_sql_compose
from .sql_eval import evaluate_sql


def _find_node_output(trace, specialist: str):
    for nr in trace.get("node_results", []):
        if nr.get("specialist") == specialist:
            return nr.get("output")
    return None


def evaluate(task: dict, trace) -> tuple[bool, str]:
    """
    Dispatch to the right evaluator. Returns (correct, reason).
    """
    if not isinstance(trace, dict):
        trace = trace.model_dump() if hasattr(trace, "model_dump") else dict(trace)

    for nr in trace.get("node_results", []):
        if nr.get("error"):
            return False, f"node_error: {nr['subtask_id']} - {nr['error']}"

    task_class = task.get("task_class")

    if task_class == "sql_gen":
        return evaluate_sql(task, _find_node_output(trace, "sql_gen"))
    if task_class == "mongo_gen":
        return evaluate_mongo(task, _find_node_output(trace, "mongo_query"))
    if task_class == "extract":
        return evaluate_extract(task, _find_node_output(trace, "extract"))
    if task_class == "multitool_plan":
        return evaluate_multitool(task, _find_node_output(trace, "multitool_plan"))
    if task_class == "policy_action":
        return evaluate_policy_action(task, _find_node_output(trace, "policy_action"))
    if task_class == "sql_compose":
        return evaluate_sql_compose(task, trace)
    if task_class == "cross_recon":
        return evaluate_cross_recon(task, trace)

    return False, f"unknown_task_class: {task_class}"
