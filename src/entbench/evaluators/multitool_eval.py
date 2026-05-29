"""
MultiTool-Plan evaluator — checks generated tool-call plan against gold.

Two checks:
1. Required tools present in the plan (set membership)
2. Dependency ordering respects gold's partial-order constraints
"""

from __future__ import annotations


def _extract_plan(output: dict | None) -> list[dict] | None:
    """Pull plan array from specialist output."""
    if not output:
        return None
    plan = output.get("plan")
    if isinstance(plan, list):
        return plan
    if isinstance(output, list):
        return output
    return None


def _required_tools(gold_plan: list[dict]) -> set[str]:
    """Set of tool names that must be present."""
    return {step.get("tool") for step in gold_plan if step.get("tool")}


def _tools_in_plan(plan: list[dict]) -> set[str]:
    """Set of tool names actually invoked."""
    return {step.get("tool") for step in plan if step.get("tool")}


def _check_partial_order(predicted: list[dict], gold: list[dict]) -> bool:
    """
    For each pair (A, B) where A appears before B in gold, check A appears
    before B in predicted (when both are present).
    """
    pred_positions = {}
    for i, step in enumerate(predicted):
        tool = step.get("tool")
        if tool and tool not in pred_positions:
            pred_positions[tool] = i

    gold_positions = {}
    for i, step in enumerate(gold):
        tool = step.get("tool")
        if tool and tool not in gold_positions:
            gold_positions[tool] = i

    gold_tools = sorted(gold_positions.keys(), key=lambda t: gold_positions[t])
    for i, t_before in enumerate(gold_tools):
        for t_after in gold_tools[i + 1 :]:
            if t_before in pred_positions and t_after in pred_positions:
                if pred_positions[t_before] >= pred_positions[t_after]:
                    return False
    return True


def evaluate_multitool(task: dict, generated_output: dict | None) -> tuple[bool, str]:
    """Evaluate a MultiTool-Plan task. Returns (correct, reason)."""
    predicted = _extract_plan(generated_output)
    if predicted is None:
        return False, "no_plan_in_output"

    gold = task.get("gold_plan")
    if not gold:
        return False, "task_missing_gold_plan"

    required = _required_tools(gold)
    actual = _tools_in_plan(predicted)

    missing = required - actual
    if missing:
        return False, f"missing_tools: {missing}"

    if not _check_partial_order(predicted, gold):
        return False, "dependency_ordering_violated"

    return True, "ok"
