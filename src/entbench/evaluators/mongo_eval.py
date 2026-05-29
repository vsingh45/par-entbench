"""
MongoDB evaluator — executes generated aggregation pipeline against MongoDB,
compares document bags to gold.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any

from pymongo import MongoClient

MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "entbench"

NUMERIC_TOLERANCE = 0.01

# Atlas sample datasets that aren't loaded in this pilot
ATLAS_COLLECTIONS = {
    "sample_mflix",
    "sample_airbnb",
    "sample_analytics",
    "movies",
    "listingsAndReviews",
    "customers",
}


def _extract_pipeline_and_collection(output: dict | None) -> tuple[list | None, str | None]:
    """Extract pipeline + collection name from specialist output."""
    if not output:
        return None, None
    # Handle {"items": [...]} wrapper from bare-list outputs
    if "items" in output and isinstance(output["items"], list):
        return None, None  # items wrapper means it wasn't a pipeline response
    pipeline = output.get("pipeline")
    collection = output.get("collection")
    if pipeline is not None and isinstance(pipeline, list):
        return pipeline, collection
    if "raw_output" in output:
        raw = output["raw_output"]
        m = re.search(r"```(?:json|javascript)?\s*(.+?)\s*```", raw, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(1))
                if isinstance(parsed, dict):
                    return parsed.get("pipeline"), parsed.get("collection")
                if isinstance(parsed, list):
                    return parsed, None
            except json.JSONDecodeError:
                pass
    return None, None


def _execute_pipeline(collection: str, pipeline: list) -> list[dict] | None:
    """Execute pipeline against MongoDB. Returns docs as list of dicts. None on error."""
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
        db = client[DB_NAME]
        coll = db[collection]
        docs = list(coll.aggregate(pipeline))
        client.close()
        return docs
    except Exception:
        return None


def _normalize_doc(doc: dict) -> tuple:
    """Convert doc to comparable form, dropping _id and normalizing values."""
    items = []
    for k, v in sorted(doc.items()):
        if k == "_id" and not isinstance(v, str):
            continue
        items.append((k, _normalize_value(v)))
    return tuple(items)


def _normalize_value(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 4)
    if isinstance(v, list):
        return tuple(_normalize_value(x) for x in v)
    if isinstance(v, dict):
        return tuple(sorted((k, _normalize_value(val)) for k, val in v.items()))
    return str(v).strip()


def _doc_bag_equivalent(
    actual: list[dict], expected: list[dict], tolerance: float = NUMERIC_TOLERANCE
) -> bool:
    """
    Compare document bags, order-independent, numeric tolerance applied.

    Uses SUBSET matching: actual documents must contain all fields present
    in expected documents (with matching values), but may have additional
    fields (e.g. from $project stages the model adds).
    """
    if actual is None or expected is None:
        return False

    # Allow actual to have more documents if expected is a subset
    # (model may not apply LIMIT that gold doesn't specify)
    if len(actual) < len(expected):
        return False

    # Normalize expected docs
    expected_norm = sorted([_normalize_doc(d) for d in expected], key=lambda d: str(d))

    # For each expected doc, check that at least one actual doc contains
    # all its key-value pairs
    def _doc_contains(actual_doc: tuple, expected_doc: tuple) -> bool:
        actual_dict = dict(actual_doc)
        expected_dict = dict(expected_doc)
        for k, ev in expected_dict.items():
            if k not in actual_dict:
                return False
            av = actual_dict[k]
            if isinstance(av, float) or isinstance(ev, float):
                try:
                    if not math.isclose(float(av), float(ev), abs_tol=tolerance):
                        return False
                except (TypeError, ValueError):
                    return False
            elif av != ev:
                return False
        return True

    actual_norm = [_normalize_doc(d) for d in actual]

    # Each expected doc must be matched by at least one actual doc
    matched_actual = set()
    for e_doc in expected_norm:
        found = False
        for i, a_doc in enumerate(actual_norm):
            if i not in matched_actual and _doc_contains(a_doc, e_doc):
                matched_actual.add(i)
                found = True
                break
        if not found:
            return False
    return True


def evaluate_mongo(task: dict, generated_output: dict | None) -> tuple[bool, str]:
    """Evaluate a Mongo-Gen task. Returns (correct, reason)."""
    pipeline, collection = _extract_pipeline_and_collection(generated_output)
    if pipeline is None:
        return False, "no_pipeline_in_output"

    # Use task's specified collection if not in output
    if not collection:
        collection = task.get("collection")
    if not collection:
        return False, "no_collection_specified"

    # Skip Atlas sample datasets (not loaded)
    if any(c in collection.lower() for c in ATLAS_COLLECTIONS):
        return True, "atlas_skipped"

    gold_pipeline = task.get("gold_pipeline")
    if not gold_pipeline:
        return False, "task_missing_gold_pipeline"

    actual = _execute_pipeline(collection, pipeline)
    if actual is None:
        return False, "generated_pipeline_execution_error"

    expected = _execute_pipeline(collection, gold_pipeline)
    if expected is None:
        return False, "gold_pipeline_execution_error"

    tolerance = task.get("evaluator", {}).get("tolerance_numeric", NUMERIC_TOLERANCE)
    if _doc_bag_equivalent(actual, expected, tolerance):
        return True, "ok"
    return False, "doc_bag_mismatch"
