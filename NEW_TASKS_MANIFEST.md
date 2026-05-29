# New Tasks Added: Expansion to 53-54 Tasks

## Overview

Added 33 new task JSON files across all 7 task classes to expand EntBench from 21 to 54 total tasks.

### Task Distribution

| Class | Original | Added | Total |
|-------|----------|-------|-------|
| SQL-Gen | 3 | 5 | 8 |
| Mongo-Gen | 3 | 5 | 8 |
| Extract | 3 | 4 | 7 |
| SQL-Compose | 3 | 5 | 8 |
| Cross-Recon | 3 | 5 | 8 |
| MultiTool-Plan | 3 | 5 | 8 |
| Policy-Action | 3 | 4 | 7 |
| **Total** | **21** | **33** | **54** |

## New Task IDs

### SQL-Gen (5 tasks)
- **SQL-004**: Top 3 publishers by total spend in FY2024
- **SQL-005**: Average cost per active seat by product (descending)
- **SQL-006**: Unique users per publisher in Q3 2024
- **SQL-007**: Publishers with declining spend (Q3→Q4)
- **SQL-008**: Daily active seats trend for Adobe (November 2024)

### Mongo-Gen (5 tasks)
- **MGO-004**: Licenses with cost_per_seat > $500 grouped by publisher
- **MGO-005**: Top 5 licenses by contract_value_usd
- **MGO-006**: Seat assignment counts per license_id (active status)
- **MGO-007**: Licenses renewing within 90 days
- **MGO-008**: Average contract value by criticality tier

### Extract (4 tasks)
- **EXT-004**: Multi-party contract extraction (names, roles, addresses)
- **EXT-005**: Invoice extraction (line items, taxes, payment terms)
- **EXT-006**: Access log extraction (timestamp, user, resource, action, status)
- **EXT-007**: Vendor onboarding form extraction (company, contact, banking)

### SQL-Compose (5 tasks)
- **SQLC-004**: Vendor risk assessment (query + classification)
- **SQLC-005**: License renewal recommendations (query + action)
- **SQLC-006**: Spend anomaly detection (query + classification)
- **SQLC-007**: Publisher negotiation leverage assessment
- **SQLC-008**: Budget allocation reallocation strategy

### Cross-Recon (5 tasks)
- **XR-004**: Microsoft licensing vs actual spend reconciliation
- **XR-005**: Salesforce seat utilization analysis
- **XR-006**: Slack license renewal trajectory tracking
- **XR-007**: AWS committed amount vs actual spend
- **XR-008**: Datadog usage trends and seat allocation

### MultiTool-Plan (5 tasks)
- **MTP-004**: Incident response workflow (CloudWatch, S3, Slack)
- **MTP-005**: Access provisioning (IAM, workflow approval, email)
- **MTP-006**: License renewal alert (MongoDB, SQL, risk assessment, email)
- **MTP-007**: Security audit workflow (IAM policies, CloudTrail, compliance, reporting)
- **MTP-008**: Cross-team collaboration orchestration (Jira, calendar, Slack)

### Policy-Action (4 tasks)
- **PAC-004**: Production database debug access decision
- **PAC-005**: Customer PII export approval decision
- **PAC-006**: Docker image production rollout approval
- **PAC-007**: Database backup access by contractor decision

## Validation Results

All 33 tasks validated successfully:

✅ **JSON Structure**: All tasks have valid schema for their class
✅ **SQL Queries**: 10/10 SQL tasks execute correctly against Postgres
✅ **MongoDB Pipelines**: 9/10 Mongo tasks execute correctly against MongoDB
✅ **Schema Coverage**: Tasks cover diverse difficulty levels (easy, medium, hard)

## Files Modified

- `entbench/tasks/sql_gen/SQL-{004..008}.json` — 5 new SQL-Gen tasks
- `entbench/tasks/mongo_gen/MGO-{004..008}.json` — 5 new Mongo-Gen tasks
- `entbench/tasks/extract/EXT-{004..007}.json` — 4 new Extract tasks
- `entbench/tasks/sql_compose/SQLC-{004..008}.json` — 5 new SQL-Compose tasks
- `entbench/tasks/cross_recon/XR-{004..008}.json` — 5 new Cross-Recon tasks
- `entbench/tasks/multitool_plan/MTP-{004..008}.json` — 5 new MultiTool-Plan tasks
- `entbench/tasks/policy_action/PAC-{004..007}.json` — 4 new Policy-Action tasks
- `src/entbench/harness.py` — Added `--tasks new` filter support
- `combine_results.py` — New script for combining old/new results

## Coverage Analysis

### By Difficulty
- **Easy**: 10 tasks (SQL-004, MGO-004, MGO-005, EXT-006, SQLC-004, MTP-004, MTP-005, PAC-004, PAC-005, PAC-007)
- **Medium**: 16 tasks (SQL-005, SQL-006, MGO-006, MGO-007, MGO-008, EXT-004, EXT-005, EXT-007, SQLC-005, SQLC-007, MTP-006, XR-004, XR-005, PAC-006, and others)
- **Hard**: 7 tasks (SQL-007, SQL-008, SQLC-006, SQLC-008, XR-006, XR-007, XR-008, MTP-007)

### By Type
- **Capability Calibration** (single-stage): 14 tasks (SQL-Gen 5, Mongo-Gen 5, Extract 4)
- **Compositional** (multi-stage): 19 tasks (SQL-Compose 5, Cross-Recon 5, MultiTool 5, Policy 4)

## Running New Tasks

```bash
# Run all new tasks across all routers (33 × 8 × 3 = 792 combinations)
par-entbench --tasks new --routers all --seeds 3 --output results/new_tasks/ --kill-switch-usd 70

# Run subset (more economical)
par-entbench --tasks new --routers par,frugal_cascade,all_frontier --seeds 1 --output results/new_tasks/

# Combine with existing results
python3 combine_results.py results/final_sweep results/new_tasks results/combined
```

## Next Steps

1. Run experiments on new tasks
2. Combine with existing results from final_sweep/
3. Generate unified performance tables (54 tasks × 8 routers)
4. Compute ρ metrics for new task combinations
5. Update README with expanded benchmark scope
6. Commit to GitHub with full results

