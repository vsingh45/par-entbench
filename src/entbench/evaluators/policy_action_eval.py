"""
Policy-Action evaluator — exact match on selected_action + compliance vocabulary.

Compliance vocabulary (5 values): pass, pass_conditional, fail, not_applicable, pending_review
"""
from __future__ import annotations

COMPLIANCE_VOCAB = {"pass", "pass_conditional", "fail", "not_applicable", "pending_review"}


def evaluate_policy_action(task: dict, generated_output: dict | None) -> tuple[bool, str]:
    """Evaluate a Policy-Action task. Returns (correct, reason)."""
    if not generated_output or not isinstance(generated_output, dict):
        return False, "no_output"

    gold = task.get("gold_output")
    if not gold:
        return False, "task_missing_gold_output"

    fields = task.get("evaluator", {}).get(
        "fields", ["selected_action", "policy_compliance"]
    )

    for field in fields:
        gold_val = gold.get(field)
        pred_val = generated_output.get(field)

        if gold_val is None and pred_val is None:
            continue
        if gold_val is None or pred_val is None:
            return False, f"{field}_missing"

        if field == "policy_compliance":
            if not isinstance(pred_val, dict):
                return False, "policy_compliance_not_dict"
            # Each policy must have a value from vocab
            for pol_id, status in pred_val.items():
                if status not in COMPLIANCE_VOCAB:
                    return False, f"invalid_compliance_value: {pol_id}={status}"
            if pred_val != gold_val:
                return False, "policy_compliance_mismatch"
        else:
            if pred_val != gold_val:
                return False, f"{field}_mismatch"

    return True, "ok"
