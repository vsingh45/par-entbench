# PaR-EntBench

**Planner-as-Router (PaR)** reference implementation and **EntBench** (Enterprise Task Benchmark) for cost-aware multi-agent LLM workflow evaluation.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## What is this?

PaR is an architectural pattern in which the planner agent simultaneously decomposes a user query into subtasks AND assigns each subtask to a specific LLM tier (small, mid, or frontier) at plan time. This removes the need for a separate routing component and lets cost-accuracy tradeoffs be reasoned about with full query context.

EntBench is a 300-task pilot benchmark across 7 task classes for evaluating cost-aware routing in multi-agent LangGraph workflows. It is the first benchmark specifically designed to measure per-node tier routing decisions and compounding error (ρ) across multi-step agent workflows with structured enterprise data backends.

## Quick start

### 1. Install

```bash
git clone https://github.com/vksingh/par-entbench.git
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

**Standalone sweep** (per-node accuracy baseline for ρ, ~$8):

```bash
par-entbench --tasks capability_calibration \
    --routers all_tiers --seeds 1 \
    --output results/standalone/
```

**Pilot run** (100-task sanity check, ~$5):

```bash
par-entbench --tasks pilot_100 \
    --routers all --seeds 1 \
    --output results/pilot/
```

**Full sweep** (overnight, ~$40-55):

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
│   ├── tasks/                    # 300 task JSON files by class
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
| `frugal_cascade`    | Small first; escalate on low confidence (FrugalGPT-style)   |
| `par_no_rationale`  | Ablation: PaR without cost_rationale (Cross-Recon only)     |

## EntBench task classes

| Class              | Tasks | Type                  | Purpose                                          |
|--------------------|-------|-----------------------|--------------------------------------------------|
| SQL-Gen            | 25    | Capability calibration| Per-tier SQL generation baseline                |
| SQL-Compose        | 25    | Compositional         | SQL feeds downstream LLM-reasoning consumer     |
| Mongo-Gen          | 53    | Capability calibration| Per-tier MongoDB aggregation baseline           |
| Cross-Recon        | 60    | Compositional         | Cross-backend reconciliation (headline class)   |
| Extract            | 54    | Capability calibration| Structured extraction from documents            |
| MultiTool-Plan     | 53    | Compositional         | Plan generation over 25-tool registry           |
| Policy-Action      | 30    | Compositional         | Policy-constrained action selection             |
| **Total**          | **300** | 132 calibration + 168 compositional               |

## Cost controls

Hard kill-switch fires at $75 cumulative API spend. Configurable via `--kill-switch-usd` flag or `cost.kill_switch_usd` in `entbench/config.yaml`.

Expected total spend for full sweep: $50-70 with prompt caching enabled.

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
