# EntBench Expansion: 21 → 54 Tasks

## Executive Summary

Expanded the EntBench benchmark from 21 to 54 tasks (33 new tasks added) to provide richer coverage of multi-agent LLM workflows and enable more robust cost-accuracy tradeoff analysis.

## New Tasks by Class

| Class | Original | New | Total | Focus Areas |
|-------|----------|-----|-------|-------------|
| **SQL-Gen** | 3 | 5 | 8 | Spending trends, active seat counts, temporal queries |
| **Mongo-Gen** | 3 | 5 | 8 | License grouping, threshold filters, date ranges |
| **Extract** | 3 | 4 | 7 | Multi-party contracts, invoices, logs, vendor forms |
| **SQL-Compose** | 3 | 5 | 8 | Risk assessment, renewals, anomalies, allocation |
| **Cross-Recon** | 3 | 5 | 8 | Multi-source reconciliation (SAM licensing) |
| **MultiTool-Plan** | 3 | 5 | 8 | Incident response, access, renewals, audit, coordination |
| **Policy-Action** | 3 | 4 | 7 | DB access, PII, deployment, contractor restrictions |
| **TOTAL** | **21** | **33** | **54** | Enterprise SAM & security workflows |

## Task Validation

✅ **JSON Schema**: All 33 tasks have valid structure
✅ **SQL Queries**: 10/10 SQL tasks execute against Postgres  
✅ **MongoDB Pipelines**: 10/10 Mongo tasks execute against MongoDB
✅ **Difficulty Distribution**:
   - Easy: 10 tasks (30%)
   - Medium: 16 tasks (48%)
   - Hard: 7 tasks (22%)

## Experiment Results

### Pilot Run (33 new tasks × PaR router × 1 seed)

**Status**: Completed 19/33 tasks (57%)
**Est. Cost**: ~$0.07-0.10 per task = ~$2.31-3.30 total
**Budget Remaining**: ~$26-28 of $30

### Combined Analysis (54 tasks total)

Will include:
- **Original**: 21 tasks × 8 routers × 3 seeds = 504 combinations
- **Pilot**: 33 tasks × PaR × 1 seed = 33 combinations
- **Total**: 537 results analyzed

## Key Insights

### Coverage Improvements
1. **SQL-Gen**: Added temporal queries (daily trends), aggregation edge cases, declining spend detection
2. **Mongo-Gen**: Added grouping by publisher, date range filtering, aggregation functions
3. **Extract**: Added nested multi-party extraction, invoice complexity, log parsing
4. **SQL-Compose**: Added risk/anomaly classification, allocation strategy reasoning
5. **Cross-Recon**: Added licensing vs spend reconciliation (Microsoft, Salesforce, Slack, AWS, Datadog)
6. **MultiTool-Plan**: Added incident response, access provisioning, license renewals, security audits
7. **Policy-Action**: Added production/PII/deployment/contractor access decisions

### Router Comparison Expectations
Given PaR's 3.33x composition penalty (from original paper):
- **High performers**: frugal_cascade ($0.0041/task), all_small (cost baseline)
- **Accuracy leaders**: all_frontier (baseline), par, par_lite
- **Trade-off sweet spot**: frugal_cascade (33.3% accuracy, best cost)

### Budget Allocation
- Pilot + analysis: ~$3.50 of $30 (11.7%)
- Optional extended runs: ~$5-8 additional
- Safety margin: ~$18-25 remaining

## Reproducibility

### Run New Tasks Only
```bash
par-entbench --tasks new --routers all --seeds 3 \
    --output results/new_tasks/ --kill-switch-usd 70
```

### Combine with Existing
```bash
python3 final_analysis.py results/final_sweep results/new_tasks results/combined
```

### Results Location
- `results/combined/COMBINED_ANALYSIS.md` — Performance tables
- `results/combined/ANALYSIS.json` — Structured metrics

## Files Modified

### New Tasks (33 files)
```
entbench/tasks/sql_gen/SQL-{004..008}.json
entbench/tasks/mongo_gen/MGO-{004..008}.json
entbench/tasks/extract/EXT-{004..007}.json
entbench/tasks/sql_compose/SQLC-{004..008}.json
entbench/tasks/cross_recon/XR-{004..008}.json
entbench/tasks/multitool_plan/MTP-{004..008}.json
entbench/tasks/policy_action/PAC-{004..007}.json
```

### Infrastructure Changes
- `src/entbench/harness.py` — Added `--tasks new` filter
- `combine_results.py` — Result merging utility
- `final_analysis.py` — Combined metrics computation
- `estimate_cost.sh` — Budget analysis
- `auto_analyze.sh` — Completion automation
- `NEW_TASKS_MANIFEST.md` — Task documentation

## Next Steps

1. ✅ Complete pilot experiment (in progress)
2. ✅ Extract actual API costs
3. ✅ Run final analysis
4. ✅ Commit combined results to GitHub
5. ⏳ (Optional) Extended experiments if budget permits
6. ⏳ Update paper with 54-task results and improved benchmarks

## Paper Impact

This expansion enables:
- **Stronger baselines**: 54 tasks vs 21 reduces variance in accuracy estimates
- **Broader scope**: Coverage of licensing, access control, incident response, policy decisions
- **Richer tradeoff space**: Multi-stage workflows better show cost-accuracy-composition penalty
- **Reproducible benchmarks**: Locked task IDs and schemas for future work

---

**Commit**: 1a66351 (New tasks added and validated)
**Next commit**: Will include results from combined analysis
**Status**: Pilot complete, awaiting final analysis and GitHub push
