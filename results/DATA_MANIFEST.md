# Experiment Data Manifest

**Experiment Date**: 2026-05-28 to 2026-05-29  
**Planner Model**: claude-haiku-4-5-20251001  
**Total Cost**: $5.11 USD  
**Completion Rate**: 449/504 tasks (89.1%)

---

## Archive Files

| Archive | Size | Contents | Extraction |
|---------|------|----------|-----------|
| `final_sweep.tar.gz` | 397 KB | 449 JSON files (21 tasks × 8 routers × 3 seeds) | `tar -xzf final_sweep.tar.gz` |
| `standalone.tar.gz` | 6.7 KB | 18 JSON files (per-tier-class calibration baselines) | `tar -xzf standalone.tar.gz` |
| `xr_haiku.tar.gz` | 47 KB | 36 JSON files (XR tasks with Haiku planner, 3 seeds) | `tar -xzf xr_haiku.tar.gz` |
| `xr_sonnet.tar.gz` | 49 KB | 36 JSON files (XR tasks with Sonnet planner, 3 seeds) | `tar -xzf xr_sonnet.tar.gz` |

---

## CSV Summary Tables

### METRICS_BY_ROUTER.csv
Per-router performance metrics (accuracy, cost).

**Columns**:
- `Router`: Router name (par, frugal_cascade, etc.)
- `N`: Number of tasks completed
- `Correct`: Number of correct answers
- `Accuracy`: Accuracy percentage (0-1)
- `Avg_Cost_USD`: Average cost per task
- `Total_Cost_USD`: Total cost for all tasks

**Best by Accuracy**: frugal_cascade, par (0.333)  
**Best by Cost**: all_small ($0.0039/task)  
**Target Met**: PaR meets ≥25% accuracy ✓, misses ≤$0.008 cost ✗

### RHO_ANALYSIS.csv
Routing efficiency metrics (composition penalty analysis).

**Columns**:
- `Router`: Router name
- `Rho`: Composition penalty (lower = better, 1 = ideal)
- `Actual_Accuracy`: Observed accuracy on compositional tasks
- `Naive_Predicted_Accuracy`: Expected accuracy if subtasks independent
- `N_Compositional_Tasks`: Number of compositional tasks evaluated
- `Composition_Penalty_Rank`: Rank by ρ (1 = least penalty)

**Key Finding**: PaR (ρ=3.33) has 3.3x higher error ratio than naive prediction  
**Best Efficiency**: all_frontier (ρ=1.27)

---

## JSON Structured Data

### rho_analysis.json
Complete ρ analysis output with:
- Per-router rho value, actual accuracy, naive predicted accuracy
- 36 compositional tasks per router (except par_no_rationale with 9 XR-only tasks)
- Detailed breakdown used for paper analysis

---

## Exploratory Analysis

### Task Class Performance (from final_sweep/)
```
sql_gen:        3/9 correct (33.3%)
sql_compose:    3/9 correct (33.3%)
mongo_gen:      3/9 correct (33.3%)
cross_recon:    0/3 correct (0.0%)
extract:        3/9 correct (33.3%)
multitool_plan: 3/9 correct (33.3%)
policy_action:  3/9 correct (33.3%)
```

---

## Directory Structure

```
results/
├── final_sweep/                      # Raw JSON: 449 task results
├── final_sweep.tar.gz               # Compressed archive (397 KB)
├── standalone/                       # Raw JSON: 18 calibration results
├── standalone.tar.gz                # Compressed archive (6.7 KB)
├── xr_haiku/                         # Raw JSON: 36 XR + Haiku results
├── xr_haiku.tar.gz                  # Compressed archive (47 KB)
├── xr_sonnet/                        # Raw JSON: 36 XR + Sonnet results
├── xr_sonnet.tar.gz                 # Compressed archive (49 KB)
├── METRICS_BY_ROUTER.csv            # Summary table: router metrics
├── RHO_ANALYSIS.csv                 # Summary table: composition penalties
├── rho_analysis.json                # Full ρ analysis (JSON)
├── DATA_MANIFEST.md                 # This file
└── full_sweep/                       # (Previous Sonnet sweep, if present)
```

---

## Reproducibility

### Environment
```bash
export PLANNER_MODEL="claude-haiku-4-5-20251001"
source .venv/bin/activate && source .env
```

### Commands to Recreate

**Final Sweep** (21 tasks × 8 routers × 3 seeds):
```bash
mkdir -p results/final_sweep logs
par-entbench --tasks all --routers all --seeds 3 \
  --output results/final_sweep/ --kill-switch-usd 70 \
  > logs/final_sweep.log 2>&1
```

**Standalone Calibration** (per-tier-class baselines):
```bash
mkdir -p results/standalone logs
par-entbench --tasks capability_calibration --routers all_tiers --seeds 1 \
  --output results/standalone/ --kill-switch-usd 70 \
  > logs/standalone.log 2>&1
```

**Compute ρ Analysis**:
```bash
par-entbench --compute-rho results/final_sweep/ \
  --standalone results/standalone/ \
  --rho-output results/rho_analysis.json
```

**Export Summaries** (generates CSV files):
```bash
# METRICS_BY_ROUTER.csv
python3 << 'PYTHON'
import json, glob
from collections import defaultdict
stats = defaultdict(lambda: {'n': 0, 'correct': 0, 'cost': 0.0})
for f in glob.glob('results/final_sweep/*.json'):
    t = json.load(open(f))
    r = t.get('router', 'unknown')
    stats[r]['n'] += 1
    stats[r]['correct'] += 1 if t.get('task_correct') else 0
    stats[r]['cost'] += t.get('total_cost_usd', 0)
with open('results/METRICS_BY_ROUTER.csv', 'w') as out:
    out.write('Router,N,Correct,Accuracy,Avg_Cost_USD,Total_Cost_USD\n')
    for r in sorted(stats):
        s = stats[r]
        acc = s['correct']/s['n'] if s['n'] else 0
        avg = s['cost']/s['n'] if s['n'] else 0
        out.write(f'{r},{s["n"]},{s["correct"]},{acc:.3f},{avg:.4f},{s["cost"]:.4f}\n')
print('METRICS_BY_ROUTER.csv written')
PYTHON
```

---

## Data Formats Summary

| Format | Size | Best For | Accessibility |
|--------|------|----------|---|
| **JSON (raw)** | ~3 MB | Detailed analysis, per-task debugging | Full data, queryable |
| **JSON (compressed)** | ~500 KB | Archival, distribution | Preserved as-is |
| **CSV** | ~2 KB | Spreadsheet analysis, plotting | Excel, Python pandas |
| **Markdown** | ~10 KB | Documentation, narrative | Human-readable |

---

## Usage Examples

### Python: Load metrics
```python
import pandas as pd
df = pd.read_csv('results/METRICS_BY_ROUTER.csv')
print(df.sort_values('Accuracy', ascending=False))
```

### Python: Load rho analysis
```python
import json
rho = json.load(open('results/rho_analysis.json'))
for router, data in rho.items():
    print(f"{router}: ρ={data['rho']}, acc={data['actual_accuracy']:.1%}")
```

### Bash: Extract one result
```bash
tar -xzf results/final_sweep.tar.gz results/final_sweep/SQL-001_par_seed1.json
```

---

**Last Updated**: 2026-05-29  
**Manifest Version**: 1.0
