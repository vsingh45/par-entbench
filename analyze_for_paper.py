#!/usr/bin/env python3
"""
PaR-EntBench comprehensive analysis — extracts every paper-ready statistic
from the existing results/combined/ directory. No new experiments.

Usage:
    python3 analyze_for_paper.py results/combined/ > paper_stats.txt

Paste paper_stats.txt back to continue building the rigorous paper.
"""
import json, glob, sys, math
from collections import defaultdict

RESULTS_DIR = sys.argv[1] if len(sys.argv) > 1 else "results/combined/"
files = glob.glob(f"{RESULTS_DIR.rstrip('/')}/*.json")

if not files:
    print(f"ERROR: no JSON files found in {RESULTS_DIR}")
    sys.exit(1)

# Load everything
recs = []
for f in files:
    try:
        t = json.load(open(f))
        recs.append(t)
    except Exception as e:
        pass

print(f"Loaded {len(recs)} result records from {RESULTS_DIR}\n")

def acc(rows):
    n = len(rows)
    c = sum(1 for r in rows if r.get("task_correct"))
    return c, n, (c / n * 100 if n else 0)

def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else 0

def std(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2: return 0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))

# Group helpers
def by(field):
    g = defaultdict(list)
    for r in recs:
        g[r.get(field)].append(r)
    return g

routers = sorted(set(r.get("router") for r in recs if r.get("router")))
classes = sorted(set(r.get("task_class") for r in recs if r.get("task_class")))
seeds = sorted(set(r.get("seed") for r in recs if r.get("seed") is not None))

print("=" * 70)
print("SECTION 1: OVERALL PER-ROUTER (all 54 tasks)")
print("=" * 70)
print(f"{'router':<20} {'N':>5} {'correct':>8} {'acc%':>7} {'cost_mean':>11} {'cost_std':>10}")
g = by("router")
for rt in sorted(g, key=lambda x: -acc(g[x])[2]):
    rows = g[rt]
    c, n, a = acc(rows)
    costs = [r.get("total_cost_usd", 0) for r in rows]
    print(f"{rt:<20} {n:>5} {c:>8} {a:>6.1f}% ${mean(costs):>9.4f} ${std(costs):>8.4f}")

print()
print("=" * 70)
print("SECTION 2: EXCLUDING SQL-COMPOSE")
print("=" * 70)
print(f"{'router':<20} {'N':>5} {'correct':>8} {'acc%':>7} {'cost_mean':>11}")
for rt in sorted(g, key=lambda x: -acc([r for r in g[x] if r.get('task_class') != 'sql_compose'])[2]):
    rows = [r for r in g[rt] if r.get("task_class") != "sql_compose"]
    if not rows: continue
    c, n, a = acc(rows)
    costs = [r.get("total_cost_usd", 0) for r in rows]
    print(f"{rt:<20} {n:>5} {c:>8} {a:>6.1f}% ${mean(costs):>9.4f}")

print()
print("=" * 70)
print("SECTION 3: PER-CLASS x PER-ROUTER ACCURACY MATRIX")
print("=" * 70)
header = f"{'class':<16}" + "".join(f"{rt[:11]:>12}" for rt in routers)
print(header)
for cls in classes:
    line = f"{cls:<16}"
    for rt in routers:
        rows = [r for r in recs if r.get("task_class") == cls and r.get("router") == rt]
        if rows:
            _, _, a = acc(rows)
            line += f"{a:>11.1f}%"
        else:
            line += f"{'—':>12}"
    print(line)

print()
print("=" * 70)
print("SECTION 4: PER-CLASS AGGREGATE (all routers)")
print("=" * 70)
print(f"{'class':<16} {'N':>5} {'acc%':>7} {'cost_mean':>11}  best_router")
for cls in classes:
    rows = [r for r in recs if r.get("task_class") == cls]
    c, n, a = acc(rows)
    costs = [r.get("total_cost_usd", 0) for r in rows]
    # best router on this class
    best_rt, best_a = None, -1
    for rt in routers:
        rr = [r for r in rows if r.get("router") == rt]
        if rr:
            _, _, ra = acc(rr)
            if ra > best_a:
                best_a, best_rt = ra, rt
    print(f"{cls:<16} {n:>5} {a:>6.1f}% ${mean(costs):>9.4f}  {best_rt} ({best_a:.1f}%)")

print()
print("=" * 70)
print("SECTION 5: PER-SEED ACCURACY (for significance / variance)")
print("=" * 70)
print(f"{'router':<20}" + "".join(f"{'seed'+str(s):>10}" for s in seeds) + f"{'mean':>10}{'std':>9}")
for rt in routers:
    line = f"{rt:<20}"
    seed_accs = []
    for s in seeds:
        rows = [r for r in recs if r.get("router") == rt and r.get("seed") == s and r.get("task_class") != "sql_compose"]
        if rows:
            _, _, a = acc(rows)
            seed_accs.append(a)
            line += f"{a:>9.1f}%"
        else:
            line += f"{'—':>10}"
    if seed_accs:
        line += f"{mean(seed_accs):>9.1f}%{std(seed_accs):>8.2f}"
    print(line)

print()
print("=" * 70)
print("SECTION 6: UTILITY U = A / C^alpha  (excl SQL-Compose)")
print("=" * 70)
for alpha in [0.5, 1.0, 1.5, 2.0]:
    print(f"\nalpha = {alpha}:")
    util = []
    for rt in routers:
        if rt == "par_no_rationale": continue
        rows = [r for r in recs if r.get("router") == rt and r.get("task_class") != "sql_compose"]
        if not rows: continue
        _, _, a = acc(rows)
        cm = mean([r.get("total_cost_usd", 0) for r in rows])
        if cm > 0:
            u = a / (cm ** alpha)
            util.append((rt, u))
    for rt, u in sorted(util, key=lambda x: -x[1]):
        mark = "  <-- PaR" if rt == "par" else ""
        print(f"  {rt:<20} U = {u:>12.1f}{mark}")

print()
print("=" * 70)
print("SECTION 7: PaR TIER-ASSIGNMENT DISTRIBUTION")
print("=" * 70)
tier_counts = defaultdict(int)
subtask_counts = []
par_rows = [r for r in recs if r.get("router") == "par"]
for r in par_rows:
    plan = r.get("plan") or {}
    subs = plan.get("subtasks") or r.get("subtasks") or []
    if subs:
        subtask_counts.append(len(subs))
        for s in subs:
            tier = s.get("tier") if isinstance(s, dict) else None
            if tier:
                tier_counts[tier] += 1
if tier_counts:
    total = sum(tier_counts.values())
    print("Tier assignment frequency across all PaR subtasks:")
    for tier in ["small", "mid", "frontier"]:
        cnt = tier_counts.get(tier, 0)
        print(f"  {tier:<10} {cnt:>5} ({cnt/total*100:.1f}%)")
    print(f"Avg subtasks per PaR plan: {mean(subtask_counts):.2f}")
else:
    print("(tier distribution not found in result JSON — may need plan field)")

print()
print("=" * 70)
print("SECTION 8: FAILURE MODE FREQUENCY")
print("=" * 70)
reasons = defaultdict(int)
for r in recs:
    reason = r.get("evaluator_reason") or r.get("failure_reason")
    if reason and not r.get("task_correct"):
        reasons[reason] += 1
for reason, cnt in sorted(reasons.items(), key=lambda x: -x[1])[:15]:
    print(f"  {cnt:>5}  {reason}")

print()
print("=" * 70)
print("SECTION 9: WORKED CASE STUDY CANDIDATES (PaR on XR tasks)")
print("=" * 70)
# find a cross_recon task where PaR has a rich plan
xr_par = [r for r in recs if r.get("router") == "par" and r.get("task_class") == "cross_recon"]
for r in xr_par[:3]:
    plan = r.get("plan") or {}
    subs = plan.get("subtasks") or r.get("subtasks") or []
    print(f"\nTask {r.get('task_id')} (seed {r.get('seed')}): correct={r.get('task_correct')}, cost=${r.get('total_cost_usd',0):.4f}")
    rationale = plan.get("cost_rationale") or r.get("cost_rationale")
    if rationale:
        print(f"  cost_rationale: {rationale[:200]}")
    for s in (subs if isinstance(subs, list) else []):
        if isinstance(s, dict):
            print(f"    [{s.get('id','?')}] {s.get('specialist','?')} -> {s.get('tier','?')}")

print()
print("=" * 70)
print("DONE — paste this entire output back to continue building the paper")
print("=" * 70)
