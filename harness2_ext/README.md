# Harness² integration (paper 2)

`entbench-adapter.patch` adds EntBench as a benchmark (`--bench eb`) to Google Research's
[Harness²](https://github.com/google-research/harness2). It is kept here, on the `paper2`
branch, so all paper-2 code lives in one place; `main` stays as the paper-1 artifact.

The patch applies to upstream commit `1cfe254e8d25b15f37048c3730134686abe60335`.

## What it changes in Harness²

| File | Change |
|---|---|
| `harness2/benchmarks/entbench.py` | New `EntBenchAdapter` and `ParSubstrate` |
| `harness2/core/prompts.py` | Editor guidance for the PaR surface (`par`) |
| `harness2/core/spec.py` | Install mode `par_harness` |
| `harness2/cli/_common.py`, `cli/check.py`, `cli/setup.py`, `preflight.py` | Register `eb` |
| `tests/test_entbench.py` | End-to-end tests against this repo, with API and DB faked |
| `docs/BENCHMARKS.md` | EntBench setup section |

## Apply

```bash
git clone https://github.com/google-research/harness2.git
cd harness2
git checkout 1cfe254e8d25b15f37048c3730134686abe60335
git apply /path/to/par-entbench/harness2_ext/entbench-adapter.patch
uv venv --python 3.12 .venv && source .venv/bin/activate && uv pip install -e .
```

## Run

```bash
# in par-entbench (this repo, paper2 branch)
python -m venv .venv && .venv/bin/pip install -e . && docker compose up -d

# in harness2
export ENTBENCH_REPO=/path/to/par-entbench ANTHROPIC_API_KEY=...
export HARNESS2_IMPROVER_MODEL=anthropic/<model>     # the improver runs in OpenCode
harness2-setup eb                                     # installs OpenCode only
harness2-check --bench eb
harness2 --bench eb --k 1 --mode parallel --only-domains sql_gen --max-tasks 1
harness2-judge --bench eb --k 1 --mode parallel
```

Verify the patch with `ENTBENCH_REPO=/path/to/par-entbench python -m pytest tests` in
harness2 (no API key or database needed).

## Regenerating the patch

If the adapter changes, apply the patch to a clean checkout at the commit above, make the
edits, and re-export with `git diff --binary 1cfe254e8d25 > entbench-adapter.patch`.
