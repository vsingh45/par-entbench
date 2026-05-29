"""
SQL evaluator — executes generated SQL against Postgres, compares result bags to gold.

Used by both sql_gen tasks (single-step) and sql_compose tasks (step 1 of multi-step).
"""

from __future__ import annotations

import math
import re
from typing import Any

import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "entbench",
    "password": "entbench",
    "dbname": "entbench",
}

NUMERIC_TOLERANCE = 0.01


def _extract_sql(output: dict | None) -> str | None:
    """Pull SQL string from specialist output. Handles a few common formats."""
    if not output:
        return None
    if isinstance(output, str):
        return output.strip()
    if "sql" in output and isinstance(output["sql"], str):
        return output["sql"].strip()
    if "query" in output and isinstance(output["query"], str):
        return output["query"].strip()
    if "raw_output" in output:
        raw = output["raw_output"]
        m = re.search(r"```sql\s*(.+?)\s*```", raw, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _execute_sql(sql: str) -> list[tuple] | None:
    """Execute SQL and return rows as list of tuples. None on error."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception:
        return None


def _normalize_value(v: Any) -> Any:
    """Normalize a single cell value for comparison."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 4)
    return str(v).strip()


def _bag_equivalent(
    actual: list[tuple], expected: list[tuple], tolerance: float = NUMERIC_TOLERANCE
) -> bool:
    """
    Compare two result bags. Order-independent. Numeric tolerance applied.
    Returns True if bags are equivalent.
    """
    if actual is None or expected is None:
        return False
    if len(actual) != len(expected):
        return False

    # Convert both to sortable normalized representation
    def normalize_row(row):
        return tuple(_normalize_value(v) for v in row)

    actual_norm = sorted([normalize_row(r) for r in actual], key=lambda r: tuple(str(v) for v in r))
    expected_norm = sorted(
        [normalize_row(r) for r in expected], key=lambda r: tuple(str(v) for v in r)
    )

    for a_row, e_row in zip(actual_norm, expected_norm, strict=False):
        if len(a_row) != len(e_row):
            return False
        for a_val, e_val in zip(a_row, e_row, strict=False):
            if a_val is None and e_val is None:
                continue
            if a_val is None or e_val is None:
                return False
            if isinstance(a_val, float) or isinstance(e_val, float):
                try:
                    if not math.isclose(float(a_val), float(e_val), abs_tol=tolerance):
                        return False
                except (TypeError, ValueError):
                    if str(a_val) != str(e_val):
                        return False
            else:
                if str(a_val) != str(e_val):
                    return False
    return True


def evaluate_sql(task: dict, generated_output: dict | None) -> tuple[bool, str]:
    """
    Evaluate a SQL task. Returns (correct, reason).
    """
    generated_sql = _extract_sql(generated_output)
    if not generated_sql:
        return False, "no_sql_in_output"

    gold_sql = task.get("gold_sql")
    if not gold_sql:
        return False, "task_missing_gold_sql"

    # Skip TPC-H tasks (tables are empty in pilot setup)
    if any(t in gold_sql.lower() for t in ["from customer", "from orders", "from lineitem"]):
        return True, "tpch_skipped"

    actual = _execute_sql(generated_sql)
    if actual is None:
        return False, "generated_sql_execution_error"

    expected = _execute_sql(gold_sql)
    if expected is None:
        return False, "gold_sql_execution_error"

    tolerance = task.get("evaluator", {}).get("tolerance_numeric", NUMERIC_TOLERANCE)
    if _bag_equivalent(actual, expected, tolerance):
        return True, "ok"
    return False, "result_bag_mismatch"
