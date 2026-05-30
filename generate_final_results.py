#!/usr/bin/env python3
"""Generate comprehensive final analysis from combined results."""

import json
import glob
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple

def load_combined_results(results_dir: str) -> List[dict]:
    """Load all result files from combined directory."""
    results = []
    for filepath in glob.glob(f"{results_dir}/*.json"):
        try:
            with open(filepath) as f:
                results.append(json.load(f))
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
    return results

def aggregate_by_router(results: List[dict]) -> Dict[str, Dict]:
    """Aggregate results by router."""
    by_router = defaultdict(lambda: {"total": 0, "correct": 0, "cost": 0.0, "latency_ms": 0})

    for result in results:
        router = result.get("router", "unknown")
        task_correct = result.get("task_correct", False)
        cost = result.get("total_cost_usd", 0.0)
        latency = result.get("total_latency_ms", 0)

        by_router[router]["total"] += 1
        by_router[router]["correct"] += 1 if task_correct else 0
        by_router[router]["cost"] += cost
        by_router[router]["latency_ms"] += latency

    return dict(by_router)

def aggregate_by_task_class(results: List[dict]) -> Dict[str, Dict[str, Dict]]:
    """Aggregate results by task class and router."""
    by_class = defaultdict(lambda: defaultdict(lambda: {"total": 0, "correct": 0}))

    for result in results:
        task_class = result.get("task_class", "unknown")
        router = result.get("router", "unknown")
        task_correct = result.get("task_correct", False)

        by_class[task_class][router]["total"] += 1
        by_class[task_class][router]["correct"] += 1 if task_correct else 0

    return {k: dict(v) for k, v in by_class.items()}

def generate_router_table(by_router: Dict[str, Dict]) -> str:
    """Generate per-router accuracy table."""
    md = "## Per-Router Performance\n\n"
    md += "| Router | Tasks | Correct | Accuracy | Total Cost | Avg Cost/Task | Avg Latency (ms) |\n"
    md += "|--------|-------|---------|----------|------------|---------------|------------------|\n"

    total_tasks = 0
    total_correct = 0
    total_cost = 0.0
    total_latency = 0

    for router in sorted(by_router.keys()):
        stats = by_router[router]
        accuracy = (stats["correct"] / stats["total"] * 100) if stats["total"] > 0 else 0
        avg_cost = stats["cost"] / stats["total"] if stats["total"] > 0 else 0
        avg_latency = stats["latency_ms"] / stats["total"] if stats["total"] > 0 else 0

        md += f"| {router:<30} | {stats['total']:<7} | {stats['correct']:<9} | {accuracy:>7.1f}% | ${stats['cost']:>9.2f} | ${avg_cost:>12.4f} | {avg_latency:>16.0f} |\n"

        total_tasks += stats["total"]
        total_correct += stats["correct"]
        total_cost += stats["cost"]
        total_latency += stats["latency_ms"]

    overall_accuracy = (total_correct / total_tasks * 100) if total_tasks > 0 else 0
    avg_cost = total_cost / total_tasks if total_tasks > 0 else 0
    avg_latency = total_latency / total_tasks if total_tasks > 0 else 0

    md += f"| **OVERALL** | **{total_tasks}** | **{total_correct}** | **{overall_accuracy:.1f}%** | **${total_cost:.2f}** | **${avg_cost:.4f}** | **{avg_latency:.0f}** |\n"

    return md

def generate_class_breakdown(by_class: Dict[str, Dict[str, Dict]]) -> str:
    """Generate per-class breakdown tables."""
    md = "\n## Performance by Task Class\n\n"

    for task_class in sorted(by_class.keys()):
        routers = by_class[task_class]
        total_tasks = sum(r["total"] for r in routers.values())
        total_correct = sum(r["correct"] for r in routers.values())
        overall_acc = (total_correct / total_tasks * 100) if total_tasks > 0 else 0

        md += f"\n### {task_class.upper()} (n={total_tasks}, acc={overall_acc:.1f}%)\n\n"
        md += "| Router | Tasks | Correct | Accuracy |\n"
        md += "|--------|-------|---------|----------|\n"

        for router in sorted(routers.keys()):
            stats = routers[router]
            acc = (stats["correct"] / stats["total"] * 100) if stats["total"] > 0 else 0
            md += f"| {router:<30} | {stats['total']:<7} | {stats['correct']:<9} | {acc:>7.1f}% |\n"

    return md

def main():
    results_dir = "results/combined"
    output_dir = "results/combined"

    print("Loading combined results...")
    results = load_combined_results(results_dir)
    print(f"Loaded {len(results)} results")

    if not results:
        print("ERROR: No results found")
        return

    print("\nAggregating by router...")
    by_router = aggregate_by_router(results)

    print("Aggregating by task class...")
    by_class = aggregate_by_task_class(results)

    # Generate markdown
    print("\nGenerating tables...")
    md = "# Final EntBench Results (54 Tasks, All Routers)\n\n"
    md += "This document contains the comprehensive evaluation of all routers across all 54 EntBench tasks.\n\n"

    # Overall summary
    total_tasks = len(results)
    total_correct = sum(1 for r in results if r.get("task_correct", False))
    total_cost = sum(r.get("total_cost_usd", 0) for r in results)
    overall_acc = (total_correct / total_tasks * 100) if total_tasks > 0 else 0

    md += f"**Overall: {total_correct}/{total_tasks} correct ({overall_acc:.1f}%)**\n\n"
    md += f"Total API Cost: ${total_cost:.2f}\n\n"

    # Router table
    md += generate_router_table(by_router)

    # Class breakdowns
    md += generate_class_breakdown(by_class)

    # Save results
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True, parents=True)

    with open(output_path / "FINAL_RESULTS.md", "w") as f:
        f.write(md)

    print(f"\n✅ Results saved to {output_dir}/FINAL_RESULTS.md")
    print(f"\nSummary:")
    print(f"  Tasks analyzed: {total_tasks}")
    print(f"  Correct: {total_correct}")
    print(f"  Accuracy: {overall_acc:.1f}%")
    print(f"  Total cost: ${total_cost:.2f}")
    print(f"  Routers: {len(by_router)}")
    print(f"  Task classes: {len(by_class)}")

if __name__ == "__main__":
    main()
