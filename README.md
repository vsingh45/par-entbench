# PaR-EntBench

**Planner-as-Router (PaR)** reference implementation and **EntBench** (Enterprise Task Benchmark) for cost-aware multi-agent LLM workflow evaluation.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## What is this?

PaR is an architectural pattern in which the planner agent simultaneously decomposes a user query into subtasks AND assigns each subtask to a specific LLM tier (small, mid, or frontier) at plan time. This removes the need for a separate routing component and lets cost-accuracy tradeoffs be reasoned about with full query context.

EntBench is an enterprise-task benchmark for evaluating cost-aware routing in multi-agent LangGraph workflows. It comprises **54 tasks across 7 classes** (8 SQL-Gen, 8 SQL-Compose, 8 Mongo-Gen, 8 Cross-Recon, 7 Extract, 8 MultiTool-Plan, 7 Policy-Action), evaluated across 8 routers × 3 seeds = 162 runs per router. It is the first benchmark specifically designed to measure per-node tier routing decisions and compounding error (ρ) across multi-step agent workflows with structured enterprise data backends.

## Architecture

### Interactive Diagram (draw.io)
[![Open in draw.io](https://img.shields.io/badge/Open-draw.io-blue?style=flat&logo=diagramsdotnet)](https://app.diagrams.net/?url=https://raw.githubusercontent.com/vsingh45/par-entbench/main/ARCHITECTURE.drawio)

Click the badge above to open the interactive architecture diagram in draw.io viewer. You can:
- Zoom and pan to explore the diagram
- Click to edit (requires draw.io account or download)
- Export as PNG, PDF, or SVG

### Static Diagram (SVG)
![PaR-EntBench Architecture](./ARCHITECTURE.svg)

**Diagram Files:**
- **SVG** ([ARCHITECTURE.svg](./ARCHITECTURE.svg)) — Static image, renders in GitHub
- **draw.io** ([ARCHITECTURE.drawio](./ARCHITECTURE.drawio)) — Interactive, editable format
  - Open: [Click here](https://app.diagrams.net/?url=https://raw.githubusercontent.com/vsingh45/par-entbench/main/ARCHITECTURE.drawio) or use the badge above
  - Edit locally: Download and open in [draw.io](https://app.diagrams.net/) or Diagrams app
  - Export: Save as PNG, PDF, SVG after editing

**System Overview:**
- **Planner** (Haiku 4.5 classifier + BatchPlanner) decomposes queries and assigns model tiers
- **8 Routers** (PaR, PaR-Lite, frugal_cascade, etc.) dispatch subtasks with different strategies
- **6 Specialists** (SQL, Mongo, Extract, Cross-Recon, Multitool, Policy) execute subtasks
- **Evaluation** layer tracks cost, accuracy, and composition penalty (ρ)
- **Outputs** in JSON, CSV, and archive formats for analysis

### System Architecture Diagram

![PaR-EntBench System Architecture](./ARCH_SYSTEM.svg)

**Edit in draw.io:** [Click here](https://app.diagrams.net/?url=https://raw.githubusercontent.com/vsingh45/par-entbench/main/ARCH_SYSTEM.drawio) · **Files:** [SVG](./ARCH_SYSTEM.svg) | [draw.io](./ARCH_SYSTEM.drawio)

*Shows the data flow from user query through planner, routers, specialists, live databases, evaluators, and final analysis. The key insight: **planner (Haiku 4.5) and specialist infrastructure are held fixed** across all routers — only the **tier assignment strategy** changes.*

### Execution-Based Evaluation Pipeline

![Evaluation Pipeline](./EVAL_PIPELINE.svg)

*The six-stage pipeline that makes EntBench execution-based rather than reference-based: task definition → planner + router → specialist execution → live database execution → task-specific evaluator → logged result. Each task's verdict depends on real Postgres/MongoDB execution, not just model output comparison. The reported evaluation uses a 54-task subset (×3 seeds = 162 runs) of the full 300-task benchmark.*

**Key Results (Haiku 4.5 planner, 54-task evaluation subset × 8 routers × 3 seeds = 162 runs per router):**

| Router | Accuracy (54 tasks) | Cost / task | Excl. SQL-Compose (n=138) |
|--------|--------------------:|------------:|--------------------------:|
| `all_frontier` — accuracy upper bound | 24.7% | $0.0189 | 29.0% |
| `source_frontier` | 24.2% | $0.0150 | 28.5% |
| **`par` — proposed** | **22.2%** | **$0.0114** | **26.1%** |
| `sink_frontier` | 21.6% | $0.0125 | 25.4% |
| `all_small` — cost lower bound | 21.0% | $0.0042 | 24.6% |
| `par_lite` | 21.0% | $0.0115 | 24.6% |
| `frugal_cascade` | _pending re-run_ | _pending_ | _pending_ |

- **PaR is Pareto-optimal**: no router achieves both higher accuracy *and* lower cost. PaR strictly dominates `sink_frontier` and `par_lite`, and trades ~10% relative accuracy for ~40% lower cost than `all_frontier`.
- **PaR tier mix**: 45.4% small / 46.4% mid / 8.2% frontier (avg 1.80 subtasks per plan) — the planner routes most work to cheaper tiers and reserves frontier for the hardest 8%.
- **SQL-Compose scores 0% for every router**, so the excl-SQL-Compose column (n=138) is the cleaner routing signal.

> **Notes:** (1) `frugal_cascade` numbers are withheld — the current data predates the cascade-scorer fix, and the fixed re-run still needs a valid run against live databases. (2) The composition penalty ρ (PaR 3.33 vs all_frontier 1.27) was measured on the earlier 21-task pilot and should be recomputed on the 54-task set before publication.

## Quick start

### 1. Install

```bash
git clone https://github.com/vsingh45/par-entbench.git
cd par-entbench
pip install -e ".[dev]"
export ANTHROPIC_API_KEY=your_key_here
```

### 2. Start databases

```bash
docker compose up -d
```

Wait ~30 seconds for containers to initialize.

### 3. Seed databases

```bash
python -m entbench.data.postgres.seed
python -m entbench.data.mongo.seed
```

### 4. Verify setup

```bash
par-entbench --verify-setup
```

Expected output:

```
OK: ANTHROPIC_API_KEY is set
OK: Postgres is accessible
OK: MongoDB is accessible
OK: Anthropic API is accessible

All setup checks passed. Ready to run experiments.
```

### 5. Run experiments

**Standalone sweep** (per-node accuracy baseline for ρ):

```bash
par-entbench --tasks capability_calibration \
    --routers all_tiers --seeds 1 \
    --output results/standalone/
```

**Pilot run** (100-task sanity check):

```bash
par-entbench --tasks pilot_100 \
    --routers all --seeds 1 \
    --output results/pilot/
```

**Full sweep** (overnight):

```bash
par-entbench --tasks all \
    --routers all --seeds 3 \
    --output results/full/
```

**ρ computation**:

```bash
par-entbench --compute-rho results/full/ \
    --standalone results/standalone/ \
    --rho-output results/rho_analysis.json
```

## Project structure

```
par-entbench/
├── src/
│   ├── par/                      # PaR reference implementation
│   │   ├── types.py              # Pydantic schemas
│   │   ├── planner.py            # Planner agent (Sonnet 4.6)
│   │   ├── dispatcher.py         # Tier dispatcher + bounded retry
│   │   └── observability.py      # Cost tracking + kill-switch
│   ├── baselines/                # 5 baseline routers
│   │   └── routers.py
│   └── entbench/
│       ├── harness.py            # Main experiment runner
│       └── evaluators/           # Class-specific evaluators
├── entbench/
│   ├── config.yaml               # Parameterized defaults
│   ├── tasks/                    # 54 task JSON files across 7 classes
│   └── data/                     # DB seed scripts
├── tests/                        # Test suite
├── docs/                         # Dataset card, convention spec, manifest
├── docker-compose.yml            # Postgres + MongoDB containers
├── pyproject.toml                # Project metadata + dependencies
└── results/                      # Output traces (gitignored)
```

## Architecture

PaR routes per-node tier assignments at plan time using a structured `Plan` schema:

```python
class Subtask(BaseModel):
    id: str
    description: str
    specialist: SpecialistType        # sql_gen | mongo_query | extract | ...
    tier: Tier                        # small | mid | frontier
    depends_on: list[str]

class Plan(BaseModel):
    subtasks: list[Subtask]
    cost_rationale: str               # Forces explicit reasoning
```

The planner runs on Claude Sonnet 4.6 across all routers (held constant). The dispatcher routes each subtask to the assigned tier:

| Tier     | Model               | Input / Output (per MTok) |
|----------|---------------------|---------------------------|
| small    | Claude Haiku 4.5    | $1.00 / $5.00             |
| mid      | Claude Sonnet 4.6   | $3.00 / $15.00            |
| frontier | Claude Opus 4.7     | $5.00 / $25.00            |

## Routers

Seven routing strategies are compared:

| Router              | Description                                                  |
|---------------------|--------------------------------------------------------------|
| `par`               | Proposed: planner assigns tier per subtask at plan time     |
| `all_frontier`      | Every node uses Opus 4.7 — accuracy upper bound             |
| `all_small`         | Every node uses Haiku 4.5 — cost lower bound                |
| `sink_frontier`     | Frontier on terminal nodes only                              |
| `source_frontier`   | Frontier on root nodes only                                  |
| `frugal_cascade`    | Small first; an LLM-judge scoring function rates each answer and the cascade escalates to the next tier when confidence is below threshold (FrugalGPT-style cascade with an LLM-judge scorer rather than a trained DistilBERT scorer; the judge's cost is billed) |
| `par_no_rationale`  | Ablation: PaR without cost_rationale (Cross-Recon only)     |

## EntBench task classes

| Class              | Tasks | Type                  | Purpose                                          |
|--------------------|-------|-----------------------|--------------------------------------------------|
| SQL-Gen            | 8     | Capability calibration| Per-tier SQL generation baseline                |
| SQL-Compose        | 8     | Compositional         | SQL feeds downstream LLM-reasoning consumer     |
| Mongo-Gen          | 8     | Capability calibration| Per-tier MongoDB aggregation baseline           |
| Cross-Recon        | 8     | Compositional         | Cross-backend reconciliation (headline class)   |
| Extract            | 7     | Capability calibration| Structured extraction from documents            |
| MultiTool-Plan     | 8     | Compositional         | Plan generation over 25-tool registry           |
| Policy-Action      | 7     | Compositional         | Policy-constrained action selection             |
| **Total**          | **54** | 23 calibration + 31 compositional               |

> The earlier `results/final_sweep` artifacts describe a separate 21-task pilot (3 tasks per class) run during development.

## Cost controls

A hard kill-switch stops execution when cumulative API spend reaches the configured ceiling. Set it conservatively before running — actual spend depends on task mix, model tier distribution, and caching. Configurable via `--kill-switch-usd` flag or `cost.kill_switch_usd` in `entbench/config.yaml`.

## Development

```bash
# Run tests
pytest

# Lint
ruff check src/

# Format
ruff format src/

# Type-check
mypy src/
```

## Reproducing the reported results

All commands assume the virtualenv is active and the databases are seeded (see
Quick start). Raw per-task traces are committed under `results/` so the
aggregate tables can be regenerated without re-running the experiments.

```bash
# 1. Regenerate the aggregate paper statistics (per-router accuracy/cost,
#    per-class matrix, per-seed variance, failure modes) from committed traces
python analyze_for_paper.py results/combined/ > paper_stats.txt

# 2. Re-run the 54-task evaluation from scratch (optional; costs API spend)
par-entbench --tasks all --routers all --seeds 3 --output results/combined/

# 3. Re-score existing traces without new API calls (e.g. after an evaluator fix)
par-entbench --reeval results/combined/

# 4. Composition penalty (ρ) — requires a standalone capability-calibration
#    baseline across all three tiers (see Limitations)
par-entbench --compute-rho results/combined/ \
    --standalone results/standalone/ --rho-output results/rho_analysis.json
```

| Paper artifact | How to regenerate |
|----------------|-------------------|
| Per-router accuracy/cost table | `analyze_for_paper.py` → Section 1–2 |
| Per-class × per-router matrix | `analyze_for_paper.py` → Section 3–4 |
| Per-seed variance | `analyze_for_paper.py` → Section 5 |
| PaR tier-assignment distribution | `analyze_for_paper.py` → Section 7 |
| Failure-mode frequencies | `analyze_for_paper.py` → Section 8 |

## Paper-to-code map

| Concept in the paper | Implementation |
|----------------------|----------------|
| Planner-as-Router (joint decompose + tier assignment) | [src/par/planner.py](src/par/planner.py) |
| Tier dispatcher + bounded retry | [src/par/dispatcher.py](src/par/dispatcher.py) |
| Cost model, pricing, kill-switch | [src/par/observability.py](src/par/observability.py) |
| `Plan` / `Subtask` schemas | [src/par/types.py](src/par/types.py) |
| Baseline routers (AllFrontier, AllSmall, Sink/Source, FrugalGPT) | [src/baselines/routers.py](src/baselines/routers.py) |
| FrugalGPT cascade confidence scorer | [src/baselines/frugal_confidence.py](src/baselines/frugal_confidence.py) |
| EntBench tasks (7 classes) | [entbench/tasks/](entbench/tasks/) |
| Execution-based evaluators | [src/entbench/evaluators/](src/entbench/evaluators/) |
| Experiment runner / CLI | [src/entbench/harness.py](src/entbench/harness.py) |
| DB seed scripts | [entbench/data/](entbench/data/) |

## Limitations

- **Evaluation scale.** Reported results use a **54-task subset** (162 runs per
  router) of the 300-task benchmark design; broader runs are future work.
- **Composition penalty (ρ).** The reported ρ = 3.33 was measured on the earlier
  **21-task calibration pilot**. Recomputing ρ on the 54-task set requires
  standalone per-tier baselines at all three tiers (small/mid/frontier) across
  every specialist; that calibration sweep has not yet been run, so ρ is
  reported as a preliminary indicator rather than a 54-task headline result.
- **FrugalGPT baseline.** The cascade's confidence scorer was recently corrected
  (it previously never escalated); fixed-scorer numbers against live databases
  are pending and are withheld from the results tables until available.
- **Single provider.** All tiers are Anthropic models (Haiku/Sonnet/Opus 4.x);
  cross-provider routing is not evaluated.
- **Domain.** Tasks center on the Software Asset Management (SAM) enterprise
  domain with Postgres/MongoDB backends.

## Citation

If you use PaR or EntBench in your research, please cite:

```bibtex
@article{singh2026par,
  title   = {Planner-as-Router: Cost-Efficient Model Selection in Multi-Agent LangGraph Workflows},
  author  = {Singh, Vivek Kumar},
  journal = {ACM Transactions on Intelligent Systems and Technology},
  year    = {2026},
  note    = {Under submission}
}
```

## License

Apache 2.0 — see [LICENSE](LICENSE).
