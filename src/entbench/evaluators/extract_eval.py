"""
Extract evaluator — field-level F1 against gold annotations.

Normalization:
- Dates → YYYY-MM-DD
- Currency → float
- Whitespace stripped
- null vs empty string treated strictly
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any


def _normalize_date(s: Any) -> str | None:
    if s is None:
        return None
    s = str(s).strip()
    formats = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%m-%d-%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s


def _normalize_currency(s: Any) -> float | None:
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    s = re.sub(r"[$,€£¥]", "", str(s)).strip()
    try:
        return float(s)
    except ValueError:
        return None


def _normalize_value(v: Any, field_hint: str = "") -> Any:
    if v is None:
        return None
    if "date" in field_hint.lower():
        return _normalize_date(v)
    if any(t in field_hint.lower() for t in ["price", "value", "amount", "usd", "total"]):
        return _normalize_currency(v)
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, list):
        return [_normalize_value(x, field_hint) for x in v]
    if isinstance(v, dict):
        return {k: _normalize_value(val, k) for k, val in v.items()}
    return v


def _flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten nested dict/list into dotted keys for field-level comparison."""
    out: dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (dict, list)):
                out.update(_flatten(v, key))
            else:
                out[key] = v
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            key = f"{prefix}[{i}]"
            if isinstance(v, (dict, list)):
                out.update(_flatten(v, key))
            else:
                out[key] = v
    else:
        if prefix:
            out[prefix] = obj
    return out


def _compute_f1(predicted: dict, gold: dict) -> float:
    """Field-level F1: each (key, value) pair that matches counts as TP."""
    if not gold:
        return 1.0 if not predicted else 0.0
    if not predicted:
        return 0.0

    pred_norm = {k: _normalize_value(v, k) for k, v in predicted.items()}
    gold_norm = {k: _normalize_value(v, k) for k, v in gold.items()}

    tp = sum(1 for k in gold_norm if k in pred_norm and pred_norm[k] == gold_norm[k])
    fp = sum(1 for k in pred_norm if k not in gold_norm or pred_norm[k] != gold_norm.get(k))
    fn = sum(1 for k in gold_norm if k not in pred_norm or pred_norm[k] != gold_norm[k])

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def evaluate_extract(task: dict, generated_output: dict | None) -> tuple[bool, str]:
    """Evaluate an Extract task. Returns (correct, reason)."""
    if not generated_output or not isinstance(generated_output, dict):
        return False, "no_output"

    if "raw_output" in generated_output and len(generated_output) == 1:
        return False, "output_not_structured"

    gold = task.get("gold_extraction")
    if not gold:
        return False, "task_missing_gold_extraction"

    # Unwrap {"items": [...]} if the specialist returned a bare list
    predicted = generated_output
    if "items" in predicted and isinstance(predicted["items"], list) and len(predicted) == 1:
        # Try to match against gold structure
        if isinstance(gold, dict):
            # gold might be {"line_items": [...]} — try to find matching key
            for gold_key, gold_val in gold.items():
                if isinstance(gold_val, list):
                    predicted = {gold_key: predicted["items"]}
                    break

    predicted_flat = _flatten(predicted)
    gold_flat = _flatten(gold)

    f1 = _compute_f1(predicted_flat, gold_flat)

    threshold = task.get("evaluator", {}).get("threshold", 0.85)
    if f1 >= threshold:
        return True, f"f1={f1:.3f}"
    return False, f"f1={f1:.3f}_below_{threshold}"
