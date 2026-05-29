#!/usr/bin/env python3
"""
Final analysis: combine new + existing results, compute metrics, generate tables.
Run after pilot/experiments complete:
  python3 final_analysis.py results/final_sweep results/new_tasks results/combined
"""

import json
import glob
import sys
from pathlib import Path
from collections import defaultdict
from typing import Any

def load_all_results(dirs: list[str]) -> list[dict]:
    """Load results from multiple directories."""
    results = []
    for d in dirs:
        for f in glob.glob(f"{d}/*.json"):
            try:
                with open(f) as fp:
                    results.append(json.load(fp))
            except:
                pass
    return results

def aggregate_stats(traces: list[dict]) -> dict:
    """Compute overall and per-class statistics."""
    stats = defaultdict(lambda: {'n': 0, 'correct': 0, 'cost': 0.0})
    per_class = defaultdict(lambda: defaultdict(lambda: {'n': 0, 'correct': 0, 'cost': 0.0}))

    for trace in traces:
        router = trace.get("router", "unknown")
        task_class = trace.get("task_class", "unknown")
        is_correct = trace.get("task_correct", False)
        cost = trace.get("total_cost_usd", 0.0)

        stats[router]['n'] += 1
        stats[router]['correct'] += 1 if is_correct else 0
        stats[router]['cost'] += cost

        per_class[task_class][router]['n'] += 1
        per_class[task_class][router]['correct'] += 1 if is_correct else 0
        per_class[task_class][router]['cost'] += cost

    return dict(stats), {k: dict(v) for k, v in per_class.items()}

def generate_tables(stats: dict, per_class: dict) -> str:
    """Generate markdown tables from statistics."""
    md = "# Combined Results Analysis\n\n"

    # Overall table
    md += "## Overall Performance (All Tasks × All Routers)\n\n"
    md += "| Router | Tasks | Correct | Accuracy | Total Cost | Avg Cost/Task |\n"
    md += "|--------|-------|---------|----------|------------|--------------|\n"

    total_tasks = 0
    total_correct = 0
    total_cost = 0.0

    for router in sorted(stats.keys()):
        s = stats[router]
        acc = (s['correct'] / s['n'] * 100) if s['n'] > 0 else 0
        avg_cost = s['cost'] / s['n'] if s['n'] > 0 else 0
        md += f"| {router:<20} | {s['n']:<7} | {s['correct']:<9} | {acc:>7.1f}% | ${s['cost']:>10.2f} | ${avg_cost:>12.4f} |\n"
        total_tasks += s['n']
        total_correct += s['correct']
        total_cost += s['cost']

    overall_acc = (total_correct / total_tasks * 100) if total_tasks > 0 else 0
    avg_task_cost = total_cost / total_tasks if total_tasks > 0 else 0
    md += f"| **TOTAL** | **{total_tasks}** | **{total_correct}** | **{overall_acc:.1f}%** | **${total_cost:.2f}** | **${avg_task_cost:.4f}** |\n"

    # Per-class tables
    md += "\n## Performance by Task Class\n\n"

    for task_class in sorted(per_class.keys()):
        md += f"\n### {task_class.upper()}\n\n"
        md += "| Router | Tasks | Correct | Accuracy |\n"
        md += "|--------|-------|---------|----------|\n"

        for router in sorted(per_class[task_class].keys()):
            s = per_class[task_class][router]
            acc = (s['correct'] / s['n'] * 100) if s['n'] > 0 else 0
            md += f"| {router:<20} | {s['n']:<7} | {s['correct']:<9} | {acc:>7.1f}% |\n"

    return md

def save_json_export(stats: dict, per_class: dict, output_dir: str) -> None:
    """Save statistics as JSON."""
    output = Path(output_dir)
    output.mkdir(exist_ok=True)

    data = {
        "overall": stats,
        "per_class": per_class,
        "metadata": {
            "total_tasks": sum(s['n'] for s in stats.values()),
            "total_correct": sum(s['correct'] for s in stats.values()),
            "total_cost": sum(s['cost'] for s in stats.values()),
        }
    }

    with open(output / "ANALYSIS.json", "w") as f:
        json.dump(data, f, indent=2)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 final_analysis.py <existing_dir> <new_dir> [output_dir]")
        print("Example: python3 final_analysis.py results/final_sweep results/new_tasks results/combined")
        sys.exit(1)

    existing_dir = sys.argv[1]
    new_dir = sys.argv[2]
    output_dir = sys.argv[3] if len(sys.argv) > 3 else "results/combined"

    print(f"Loading results from:")
    print(f"  - Existing: {existing_dir}")
    print(f"  - New: {new_dir}")

    traces = load_all_results([existing_dir, new_dir])
    print(f"Loaded {len(traces)} total task results")

    if not traces:
        print("ERROR: No results found")
        sys.exit(1)

    stats, per_class = aggregate_stats(traces)

    # Generate markdown
    markdown = generate_tables(stats, per_class)

    # Write outputs
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True, parents=True)

    with open(output_path / "COMBINED_ANALYSIS.md", "w") as f:
        f.write(markdown)

    save_json_export(stats, per_class, output_dir)

    # Print summary
    total_tasks = sum(s['n'] for s in stats.values())
    total_correct = sum(s['correct'] for s in stats.values())
    total_cost = sum(s['cost'] for s in stats.values())

    print(f"\n{'='*60}")
    print(f"ANALYSIS COMPLETE")
    print(f"{'='*60}")
    print(f"Total tasks analyzed: {total_tasks}")
    print(f"Total correct: {total_correct}")
    print(f"Overall accuracy: {total_correct/total_tasks*100:.1f}%")
    print(f"Total API cost: ${total_cost:.2f}")
    print(f"\nResults saved to: {output_dir}/")
    print(f"  - COMBINED_ANALYSIS.md (tables)")
    print(f"  - ANALYSIS.json (structured data)")

if __name__ == "__main__":
    main()
