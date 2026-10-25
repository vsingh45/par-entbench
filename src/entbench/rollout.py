"""
entbench/rollout.py — Process boundary between PaR/EntBench and an outer optimizer.

Harness² (or any harness optimizer) runs in its own environment and talks to
EntBench only through this CLI, so it never imports PaR code and never reads a
task file directly. That makes this module the ONE place that decides what an
optimizer may see:

  describe   task ids, classes and answer-free prompts (allowlisted fields only)
  validate   check a harness directory; exit 2 with an actionable message if invalid
  run        execute one task under a harness WITHOUT grading; write the run dir
  score      grade a finished run dir against live Postgres/MongoDB

A run directory holds:
  trace.json    the WorkflowTrace (plan, node outputs, tokens) with task_correct = null
  metrics.json  cost, wall time, router, seed, harness source

Grading happens only in `score`, after the optimizer has committed to a choice.

Usage:
  python -m entbench.rollout describe [--tasks all]
  python -m entbench.rollout validate --harness-dir H
  python -m entbench.rollout run --task-id SQL-001 --run-dir D [--harness-dir H]
                                 [--router par] [--seed 1]
  python -m entbench.rollout score --task-id SQL-001 --run-dir D
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

# Task fields an optimizer may see. Everything else (gold_*, evaluator,
# bug_patterns, known_trap, antipattern_to_avoid, expected_specialists,
# difficulty, linter_check, ...) is grading metadata or a hint, and stays hidden.
VISIBLE_FIELDS = (
    "task_id",
    "task_class",
    "query",
    "input_document",
    "context",
    "policy_registry",
    "candidate_actions",
    "collection",
    "substrate",
)

TRACE_FILE = "trace.json"
METRICS_FILE = "metrics.json"


def visible_task(task: dict) -> dict:
    """The task as an optimizer may see it: allowlisted fields only."""
    return {k: task[k] for k in VISIBLE_FIELDS if k in task}


def _task_by_id(task_id: str, task_set: str = "all") -> dict:
    from entbench.harness import load_tasks

    for t in load_tasks(task_set):
        if t["task_id"] == task_id:
            return t
    raise SystemExit(f"unknown task id {task_id!r}")


def cmd_describe(args: argparse.Namespace) -> int:
    from entbench.harness import load_tasks

    tasks = [visible_task(t) for t in load_tasks(args.tasks)]
    json.dump(tasks, sys.stdout, indent=2, sort_keys=True)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    from entbench.harness_files import validate_harness_dir

    try:
        validate_harness_dir(Path(args.harness_dir))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    import anthropic

    from entbench.harness import make_specialist_registry, run_task
    from entbench.harness_files import load_harness
    from par.observability import DEFAULT_KILL_SWITCH_USD

    task = _task_by_id(args.task_id, args.tasks)
    harness = load_harness(args.harness_dir) if args.harness_dir else load_harness(None)
    if not args.harness_dir and os.environ.get("PAR_HARNESS_DIR"):
        print("note: $PAR_HARNESS_DIR is set and was used as the harness", file=sys.stderr)

    client = anthropic.Anthropic()
    registry = make_specialist_registry(client, harness)

    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with tempfile.TemporaryDirectory() as scratch:
        trace, _, kill = run_task(
            task=task,
            router=args.router,
            seed=args.seed,
            client=client,
            specialist_registry=registry,
            cumulative_spend=0.0,
            kill_switch_ceiling=args.kill_switch_usd or DEFAULT_KILL_SWITCH_USD,
            output_dir=scratch,
            harness=harness,
            evaluate=False,
        )
    wall = time.time() - t0

    (run_dir / TRACE_FILE).write_text(trace.model_dump_json(indent=2), encoding="utf-8")
    metrics = {
        "task_id": trace.task_id,
        "task_class": trace.task_class,
        "router": args.router,
        "seed": args.seed,
        "harness": harness.source,
        "cost_usd": trace.total_cost_usd,
        "wall_s": round(wall, 3),
        "n_nodes": len(trace.node_results),
        "n_errors": sum(1 for n in trace.node_results if n.error),
        "kill_switch": kill,
    }
    (run_dir / METRICS_FILE).write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    from entbench.harness import evaluate_task
    from par.types import WorkflowTrace

    task = _task_by_id(args.task_id, args.tasks)
    trace_path = Path(args.run_dir) / TRACE_FILE
    trace = WorkflowTrace.model_validate_json(trace_path.read_text(encoding="utf-8"))
    correct = bool(evaluate_task(task, trace))
    json.dump(
        {"task_id": args.task_id, "correct": correct, "n_passed": int(correct), "n_criteria": 1},
        sys.stdout,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m entbench.rollout", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("describe", help="answer-free task list as JSON")
    d.add_argument("--tasks", default="all")
    d.set_defaults(fn=cmd_describe)

    v = sub.add_parser("validate", help="check a harness directory")
    v.add_argument("--harness-dir", required=True)
    v.set_defaults(fn=cmd_validate)

    r = sub.add_parser("run", help="execute one task without grading")
    r.add_argument("--task-id", required=True)
    r.add_argument("--run-dir", required=True)
    r.add_argument("--harness-dir", default=None)
    r.add_argument("--router", default="par")
    r.add_argument("--seed", type=int, default=1)
    r.add_argument("--tasks", default="all")
    r.add_argument("--kill-switch-usd", type=float, default=None)
    r.set_defaults(fn=cmd_run)

    s = sub.add_parser("score", help="grade a finished run dir")
    s.add_argument("--task-id", required=True)
    s.add_argument("--run-dir", required=True)
    s.add_argument("--tasks", default="all")
    s.set_defaults(fn=cmd_score)

    args = p.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
