"""
analyze_significance.py — statistical analysis of EntBench router results.

Computes, from the committed per-task traces in results/combined/:
  1. Per-router accuracy with 95% bootstrap confidence intervals.
  2. Paired (per-task) differences vs PaR on accuracy and cost, with 95% CIs.

Unit of analysis is the task: the three seeds are averaged per task before
resampling, so the bootstrap reflects task-level variance (the dominant source
at n=54) rather than treating each seed as independent. A paired difference is
"statistically separable" when its 95% CI excludes 0.

Cost here is `total_cost_usd` (specialist-only; the planner is held constant
across all routers and excluded — see README "Cost controls").

The SQL-Compose class scores 0% for every router (a degenerate floor class),
so the paper reports accuracy excluding it ("the cleaner routing signal").
Pass --excl-sql-compose to reproduce that view. Cost significance is reported
on the full 54-task set by default, since every task incurs real spend and the
full set makes no exclusion that could look outcome-motivated; the excl view is
a robustness check, not the primary basis.

Usage:
    python analyze_significance.py [results_dir]                  # full 54-task
    python analyze_significance.py [results_dir] --excl-sql-compose  # n=138 view
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import random

N_BOOT = 10_000
SEED = 42
MAIN_ROUTERS = [
    "all_frontier",
    "source_frontier",
    "par",
    "par_lite",
    "sink_frontier",
    "all_small",
    "frugal_cascade",
]


def load(
    results_dir: str, excl_sql_compose: bool = False
) -> dict[str, dict[str, list[tuple[float, float]]]]:
    """router -> task_id -> list of (correct, cost) across seeds."""
    rows: dict[str, dict[str, list[tuple[float, float]]]] = collections.defaultdict(
        lambda: collections.defaultdict(list)
    )
    files = glob.glob(f"{results_dir}/**/*.json", recursive=True)
    for f in files:
        d = json.load(open(f))
        if excl_sql_compose and d["task_class"] == "sql_compose":
            continue
        rows[d["router"]][d["task_id"]].append(
            (1.0 if d["task_correct"] else 0.0, d["total_cost_usd"])
        )
    return rows


def task_means(router_rows: dict[str, list[tuple[float, float]]]) -> tuple[dict, dict]:
    acc = {t: sum(v[0] for v in vals) / len(vals) for t, vals in router_rows.items()}
    cost = {t: sum(v[1] for v in vals) / len(vals) for t, vals in router_rows.items()}
    return acc, cost


def boot_ci(values: list[float], rng: random.Random, n: int = N_BOOT) -> tuple[float, float, float]:
    mean = sum(values) / len(values)
    k = len(values)
    bs = sorted(sum(values[rng.randrange(k)] for _ in range(k)) / k for _ in range(n))
    return mean, bs[int(0.025 * n)], bs[int(0.975 * n)]


def paired_boot(
    a: dict[str, float], b: dict[str, float], rng: random.Random, n: int = N_BOOT
) -> tuple[float, float, float]:
    """Bootstrap the mean paired difference (b - a) over shared tasks."""
    tasks = sorted(set(a) & set(b))
    diffs = [b[t] - a[t] for t in tasks]
    return boot_ci(diffs, rng, n)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results_dir", nargs="?", default="results/combined")
    parser.add_argument(
        "--excl-sql-compose",
        action="store_true",
        help="drop the degenerate SQL-Compose class (n=138 robustness view)",
    )
    a = parser.parse_args()
    rng = random.Random(SEED)
    rows = load(a.results_dir, excl_sql_compose=a.excl_sql_compose)
    routers = [r for r in MAIN_ROUTERS if r in rows]
    tm = {r: task_means(rows[r]) for r in routers}

    basis = "excl SQL-Compose (n=138)" if a.excl_sql_compose else "full 54-task set"
    print(f"Results dir: {a.results_dir}  |  basis: {basis}  |  bootstrap n={N_BOOT}, seed={SEED}\n")
    print("=== Per-router accuracy and cost (95% bootstrap CI, unit = task) ===")
    print(f"{'router':18} {'accuracy':>22}  {'cost/task':>22}")
    for r in routers:
        acc, cost = tm[r]
        am, alo, ahi = boot_ci(list(acc.values()), rng)
        cm, clo, chi = boot_ci(list(cost.values()), rng)
        print(
            f"{r:18} {am*100:5.1f}% [{alo*100:4.1f}, {ahi*100:4.1f}]   "
            f"${cm:.5f} [${clo:.5f}, ${chi:.5f}]"
        )

    if "par" not in tm:
        return
    pa, pc = tm["par"]
    print("\n=== Paired difference vs PaR (positive = other higher; * = CI excludes 0) ===")
    print(f"{'vs PaR':18} {'Δ accuracy (pp)':>24}   {'Δ cost ($)':>26}")
    for r in routers:
        if r == "par":
            continue
        oa, oc = tm[r]
        dam, dalo, dahi = paired_boot(pa, oa, rng)
        dcm, dclo, dchi = paired_boot(pc, oc, rng)
        asig = "" if dalo < 0 < dahi else " *"
        csig = "" if dclo < 0 < dchi else " *"
        print(
            f"{r:18} {dam*100:6.1f} [{dalo*100:5.1f}, {dahi*100:5.1f}]{asig:2}   "
            f"{dcm:+.5f} [{dclo:+.5f}, {dchi:+.5f}]{csig}"
        )
    print("\npp = percentage points. Cost is specialist-only (planner held constant, excluded).")


if __name__ == "__main__":
    main()
