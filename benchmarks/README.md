# Phase-1 Micro-Benchmarks

This directory contains `pytest-benchmark`-driven micro-benchmarks that enforce
the hard ceilings in [`docs/performance/budgets.md`](../docs/performance/budgets.md).
Every benchmark *fails the suite* (not just emits a warning) when the measured
value exceeds its documented budget.

## Run

```bash
# Full benchmark sweep, JSON artifact written for the CI uploader
uv run pytest benchmarks/ --benchmark-only \
    --benchmark-json=benchmarks/results.json

# One module
uv run pytest benchmarks/test_stats_keywords.py --benchmark-only -q

# Compare two saved runs
uv run pytest --benchmark-compare --benchmark-compare-fail=mean:5%
```

The `--benchmark-only` flag suppresses non-benchmark tests and is the default for
the CI `bench` job.

## Budgets enforced

| File                              | Validates row in `budgets.md`             |
|-----------------------------------|-------------------------------------------|
| `test_mcp_transport_latency.py`   | §2 MCP in-memory & stdio                  |
| `test_bfcl_matcher_throughput.py` | §1 Tier-1 BFCL AST match                  |
| `test_stats_keywords.py`          | §1 Tier-1 mannwhitney/cliffs/bootstrap    |
| `test_skill_grading_offline.py`   | §3 Fast preflight (mock provider)         |
| `test_judge_offline.py`           | §1 Judge framing overhead                 |
| `test_library_import.py`          | §5 Library import + Suite Setup           |

## Skipping rules

If a source module is not yet implemented, the corresponding benchmark calls
`pytest.skip("not implemented")` so partial CI runs do **not** block other
agents (per `.swarm-coordination.md`). The skip message names the missing
module so the responsible agent sees the gap.

## Reading the output

`pytest-benchmark` emits a comparison table at the end of the run:

```
Name (time in ms)             Min    Mean    Max    StdDev    Median    OPS    Rounds
------------------------------------------------------------------------------------
mann_whitney_u_n30           0.42    0.51   1.10      0.13      0.49   1960     50
bootstrap_n30_1000_resamples 17.0   18.4   23.0      1.4      18.1     54     10
```

A row's `Mean` and the budget literal in the test source are the contract;
**any divergence between this table and `docs/performance/budgets.md` is a
documentation bug**.

## CI artifact

The `bench` job in `.github/workflows/ci.yml` writes
`benchmarks/results.json` and uploads it. The roll-up script
`scripts/perf_rollup.py` (Phase-1 deliverable, see `benchmarks-plan.md` §3)
turns it into the per-experiment summary.
