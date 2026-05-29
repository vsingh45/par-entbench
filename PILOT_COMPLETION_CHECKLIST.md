# Pilot Completion Checklist

## Current Status
- **Pilot Run**: 33 new tasks × PaR router × 1 seed
- **Progress**: ~17/33 tasks (50%)
- **ETA**: 45-60 minutes remaining
- **Budget**: $30 available

## When Pilot Completes (33/33 tasks in results/new_tasks/)

### Step 1: Extract Cost
```bash
# Find actual pilot cost from logs
tail -50 logs/new_tasks.log | grep -i "cost\|cumulative\|total"

# Estimate: 33 tasks * ~$0.08-0.12/task ≈ $2.60-3.96
```

### Step 2: Decision Logic
```
If remaining budget < $4:
  → SKIP extended experiments, go to Step 4
Else if remaining budget < $10:
  → Run: 33 × 3 routers (frugal, frontier, small) × 1 seed (~$3)
Else:
  → Run: 33 × 6 routers × 1 seed (~$5)
```

### Step 3: Run Extended Experiments (if budget allows)
```bash
mkdir -p results/new_tasks_extended
par-entbench --tasks new \
  --routers frugal_cascade,all_frontier,all_small \
  --seeds 1 \
  --output results/new_tasks_extended/ \
  --kill-switch-usd 70 > logs/extended.log 2>&1 &
```

### Step 4: Combine Results
```bash
# Merge pilot + existing (or pilot + pilot + existing)
python3 final_analysis.py results/final_sweep results/new_tasks results/combined
```

### Step 5: Final Commit
```bash
git add -A
git commit -m "Add new task results: 54 tasks × 8 routers baseline

Expanded benchmark from 21 to 54 tasks.
Pilot results: 33 new tasks × PaR × 1 seed
Combined with existing: 21 tasks × 8 routers × 3 seeds

Results in results/combined/:
  - COMBINED_ANALYSIS.md (performance tables)
  - ANALYSIS.json (structured metrics)

Remaining budget: ~\$XX.XX"

git push origin main
```

## Monitoring

Two monitors active:
- `byrwgfszu`: 30-second updates on task count
- `bwjzl2h1w`: 45-second updates with cost tracking

Watch for notifications of 33/33 completion.

## Success Metrics

✓ All 33 tasks complete successfully
✓ Pilot cost < $5 (preserves budget)
✓ Combined results include ≥ 53 tasks
✓ Per-router accuracy table generated
✓ Results committed to GitHub
✓ Budget remaining > $20

