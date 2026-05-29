#!/usr/bin/env python3
"""Combine existing and new task results into unified analysis."""

import json
import glob
from pathlib import Path
from collections import defaultdict

def combine_results(existing_dir, new_dir, output_dir):
    """Combine results from two runs into unified metrics."""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    # Load all results
    all_results = []
    for f in glob.glob(f"{existing_dir}/*.json"):
        with open(f) as fp:
            all_results.append(json.load(fp))
    for f in glob.glob(f"{new_dir}/*.json"):
        with open(f) as fp:
            all_results.append(json.load(fp))

    print(f"Loaded {len(all_results)} total task results")

    # Aggregate by router
    stats = defaultdict(lambda: {'n': 0, 'correct': 0, 'cost': 0.0})
    per_class = defaultdict(lambda: defaultdict(lambda: {'n': 0, 'correct': 0, 'cost': 0.0}))

    for trace in all_results:
        router = trace.get("router", "unknown")
        task_class = trace.get("task_class", "unknown")
        is_correct = trace.get("task_correct", False)
        cost = trace.get("total_cost_usd", 0)

        stats[router]['n'] += 1
        stats[router]['correct'] += 1 if is_correct else 0
        stats[router]['cost'] += cost

        per_class[task_class][router]['n'] += 1
        per_class[task_class][router]['correct'] += 1 if is_correct else 0
        per_class[task_class][router]['cost'] += cost

    # Write summary
    summary = f"""# Combined Results Summary

## Overall Metrics (All Tasks × All Routers)

| Router | N | Correct | Accuracy | Avg Cost/Task |
|--------|---|---------|----------|---------------|
"""

    for router in sorted(stats.keys()):
        s = stats[router]
        acc = (s['correct'] / s['n'] * 100) if s['n'] else 0
        avg_cost = (s['cost'] / s['n']) if s['n'] else 0
        summary += f"| {router} | {s['n']} | {s['correct']} | {acc:.1f}% | ${avg_cost:.4f} |\n"

    summary += f"\n## Per-Class Breakdown\n\n"
    for task_class in sorted(per_class.keys()):
        summary += f"### {task_class.upper()}\n\n"
        for router in sorted(per_class[task_class].keys()):
            s = per_class[task_class][router]
            acc = (s['correct'] / s['n'] * 100) if s['n'] else 0
            summary += f"- {router}: {s['n']} tasks, {acc:.1f}% accuracy, ${s['cost']:.2f} total\n"
        summary += "\n"

    # Write files
    with open(output_path / "COMBINED_SUMMARY.md", "w") as f:
        f.write(summary)

    with open(output_path / "COMBINED_METRICS.json", "w") as f:
        json.dump({
            "total_tasks": len(all_results),
            "router_stats": dict(stats),
            "per_class_stats": {k: dict(v) for k, v in per_class.items()}
        }, f, indent=2)

    print(f"Wrote combined results to {output_path}")
    print(f"\nTotal tasks analyzed: {len(all_results)}")
    print(f"Total cost: ${sum(s['cost'] for s in stats.values()):.2f}")
    print(f"Average accuracy: {sum(s['correct'] for s in stats.values()) / sum(s['n'] for s in stats.values()) * 100:.1f}%")

if __name__ == "__main__":
    import sys
    existing = sys.argv[1] if len(sys.argv) > 1 else "results/final_sweep"
    new = sys.argv[2] if len(sys.argv) > 2 else "results/new_tasks"
    output = sys.argv[3] if len(sys.argv) > 3 else "results/combined"
    combine_results(existing, new, output)
