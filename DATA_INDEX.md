# PaR Experiment Data Index

**Complete experiment dataset from 2026-05-28 to 2026-05-29**

## Quick Links

- **Summary Tables**
  - [METRICS_BY_ROUTER.csv](results/METRICS_BY_ROUTER.csv) — Accuracy & cost by router (8 rows)
  - [RHO_ANALYSIS.csv](results/RHO_ANALYSIS.csv) — Composition penalty (ρ) by router (8 rows)

- **Analysis Documents**
  - [EXPERIMENT_RESULTS.md](EXPERIMENT_RESULTS.md) — Full narrative with code & insights
  - [EXPERIMENT_METRICS.json](EXPERIMENT_METRICS.json) — Structured metrics export
  - [results/DATA_MANIFEST.md](results/DATA_MANIFEST.md) — Archive contents & reproducibility

- **Raw Data Archives** (ready to extract)
  - [results/final_sweep.tar.gz](results/final_sweep.tar.gz) — 449 JSON files (397 KB)
  - [results/standalone.tar.gz](results/standalone.tar.gz) — 18 JSON files (6.7 KB)
  - [results/xr_haiku.tar.gz](results/xr_haiku.tar.gz) — 36 JSON files (47 KB)
  - [results/xr_sonnet.tar.gz](results/xr_sonnet.tar.gz) — 36 JSON files (49 KB)

- **Analysis Output**
  - [results/rho_analysis.json](results/rho_analysis.json) — ρ efficiency metrics

---

## Key Findings at a Glance

| Metric | Value |
|--------|-------|
| **Total Cost** | $5.11 |
| **Tasks Completed** | 449 / 504 (89.1%) |
| **Best Accuracy (tie)** | frugal_cascade & par: 33.3% |
| **Best Cost** | all_small: $0.0039/task |
| **PaR Accuracy** | 33.3% ✓ (≥25% target) |
| **PaR Cost** | $0.0099/task ✗ (>$0.008 target) |
| **PaR Composition Penalty (ρ)** | 3.33 (highest; all_frontier: 1.27) |

---

## Data Format Reference

```
results/
├── CSV summaries (human-readable)
│   ├── METRICS_BY_ROUTER.csv
│   └── RHO_ANALYSIS.csv
│
├── JSON archives (compressed)
│   ├── final_sweep.tar.gz          [449 task results]
│   ├── standalone.tar.gz           [18 calibration results]
│   ├── xr_haiku.tar.gz             [36 XR + Haiku results]
│   └── xr_sonnet.tar.gz            [36 XR + Sonnet results]
│
├── JSON analysis (uncompressed)
│   ├── rho_analysis.json
│   └── DATA_MANIFEST.md
│
└── Uncompressed raw directories (for quick inspection)
    ├── final_sweep/                [449 JSON files]
    ├── standalone/                 [18 JSON files]
    ├── xr_haiku/                   [36 JSON files]
    └── xr_sonnet/                  [36 JSON files]
```

---

## Quick Start for Analysis

### View Summary Tables
```bash
# Accuracy & cost comparison
cat results/METRICS_BY_ROUTER.csv

# Composition penalty ranking
cat results/RHO_ANALYSIS.csv
```

### Extract Raw Data
```bash
# Extract all final sweep results
tar -xzf results/final_sweep.tar.gz

# Extract one task result
tar -xzf results/final_sweep.tar.gz results/final_sweep/SQL-001_par_seed1.json
```

### Load in Python
```python
import pandas as pd
import json

# Summary metrics
metrics = pd.read_csv('results/METRICS_BY_ROUTER.csv')
print(metrics.sort_values('Accuracy', ascending=False))

# ρ analysis
rho = json.load(open('results/rho_analysis.json'))
print(f"PaR composition penalty: ρ={rho['par']['rho']}")
```

### Load in R/Excel
```bash
# Open CSV files directly
open results/METRICS_BY_ROUTER.csv
open results/RHO_ANALYSIS.csv
```

---

## Files Manifest

### Documentation
- `EXPERIMENT_RESULTS.md` (8 KB) — Complete narrative, code, insights
- `EXPERIMENT_METRICS.json` (12 KB) — Structured metrics, reproducibility
- `results/DATA_MANIFEST.md` (10 KB) — Archive guide, reproducibility details
- `DATA_INDEX.md` (this file) — Quick navigation

### Summary Tables
- `results/METRICS_BY_ROUTER.csv` (700 B) — 8 routers × 6 columns
- `results/RHO_ANALYSIS.csv` (800 B) — 8 routers × ρ metrics

### Raw Archives
- `results/final_sweep.tar.gz` (397 KB) — 449 tasks
- `results/standalone.tar.gz` (6.7 KB) — 18 calibration
- `results/xr_haiku.tar.gz` (47 KB) — 36 XR tasks (Haiku)
- `results/xr_sonnet.tar.gz` (49 KB) — 36 XR tasks (Sonnet)

### Raw Directories (uncompressed)
- `results/final_sweep/` (~3 MB) — 449 JSON files
- `results/standalone/` (~20 KB) — 18 JSON files
- `results/xr_haiku/` (~500 KB) — 36 JSON files
- `results/xr_sonnet/` (~520 KB) — 36 JSON files

### Analysis Output
- `results/rho_analysis.json` (5 KB) — ρ metrics per router

---

## Reproducibility

**Environment**:
```bash
export PLANNER_MODEL="claude-haiku-4-5-20251001"
source .venv/bin/activate && source .env
```

**Full details**: See [results/DATA_MANIFEST.md](results/DATA_MANIFEST.md) for all reproduction commands.

---

**Total Dataset Size**: ~4 MB (uncompressed) | ~500 KB (compressed archives)  
**Generated**: 2026-05-29  
**Status**: Complete & ready for analysis
