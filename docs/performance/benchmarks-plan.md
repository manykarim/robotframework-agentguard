# Phase-1 Benchmarks Plan

> Validates every `[ASSUMPTION → exp_NN]` marker in `budgets.md`, `tier-routing.md`, and `non-determinism-cost-model.md`. Each experiment is small (<1 day eng), has a single numeric pass criterion, and produces a JSON artifact stored under `tests/benchmarks/results/<exp_id>.json`.

---

## 1. Harness

- **`pytest-benchmark`** for per-keyword micro-benchmarks (warmup, calibration, p50/p95/p99 reports). Native CSV/JSON output suitable for CI artifacts.
- **Custom Robot Framework suite** (`atest/perf/perf_suite.robot`) for end-to-end skill-grading wall-clock. Uses the same `OTelListener` the library ships — eats own dogfood.
- **Cost ledger.** All LLM calls go through LiteLLM; the router's `agentguard.route` OTel span is dumped to the cost ledger CSV. No real LLM calls in CI by default — recording mode runs against `mocks/` (canned LiteLLM responses); validation mode runs against live providers behind `RUN_LIVE_BENCH=1`.
- **Memory profiling.** `psutil` RSS sampling at 1 Hz during the suite, plus `tracemalloc` snapshots at suite start/end.
- **Comparison.** All experiments compare against budgets in `budgets.md`. `pytest-benchmark`'s built-in `--benchmark-compare-fail=mean:5%` provides regression detection across runs.

Repo layout (no source-code changes — these are test artifacts under `tests/benchmarks/`):

```
tests/benchmarks/
├── conftest.py                # pytest-benchmark setup + LiteLLM mock fixtures
├── exp_01_mcp_transport.py
├── exp_02_token_mix.py
├── ...
├── results/                   # JSON outputs, gitignored
└── mocks/                     # canned LiteLLM responses
atest/perf/
└── perf_suite.robot           # E2E wall-clock suite
```

---

## 2. Experiments to Run Before Phase-1 GA

| ID | Validates | What it measures | Pass criterion |
|----|-----------|------------------|----------------|
| **exp_01** | `budgets.md §2` MCP transport budgets | Round-trip time for `Call MCP Tool` over in-memory / stdio / HTTP, 10K iters each, on GitHub-hosted Linux runner | in-memory p95 <1 ms; stdio p95 <5 ms; HTTP p95 <50 ms |
| **exp_02** | `budgets.md §4` token mix assumption | Mean input/output tokens for the *judge call* across the 30 reference skills × 10 reps, recorded against Haiku | Mean within ±25% of the assumed 2K-in / 500-out; otherwise update the cost projection |
| **exp_03** | `budgets.md §1` Tier-2 latency | 100 Haiku judge calls, sequential, warm client, eu-central LiteLLM | mean ≤500 ms, p95 ≤900 ms |
| **exp_04** | `budgets.md §5` startup overhead | `python -X importtime -c "from AgentTest import AgentTest; AgentTest()"` | Total <1.0 s; scipy not in import path |
| **exp_05** | `budgets.md §3` parallel reps | 10 concurrent Haiku judge calls via `asyncio.gather` | No 429s; wall-clock ≤2× single-call latency |
| **exp_06** | `budgets.md §6` OTel overhead | Same Tier-1 suite with telemetry on vs. off | Overhead ≤5% of wall-clock |
| **exp_07** | `budgets.md §7` HNSW memory cap | 10K sessions × 384-dim int8 vectors loaded; `psutil` RSS delta | RSS delta ≤350 MB |
| **exp_08** | `tier-routing.md §3` router accuracy | 200 hand-labeled (skill, rubric, expected-tier) tuples scored by router | Router's chosen tier matches human label with κ ≥ 0.7 |
| **exp_09** | `non-determinism-cost-model.md §2 opt #1` cache hit rate | Run 30-skill suite daily for 30 days against frozen rubrics; record cache hits | Hit rate ≥60% after day 7 |
| **exp_10** | `non-determinism-cost-model.md §2 opt #2` adaptive-N stabilization | For each of 30 skills, compute bootstrap-CI half-width at N=3, 5, 10 | ≥50% of skills converge (CI half-width <0.05) at N≤5 |
| **exp_11** | `non-determinism-cost-model.md §2 opt #3` prefilter pass rate | For 100 (subject_output, expected_output) pairs from reference rubrics, measure how many pass the deterministic prefilter (string→regex→AST→cosine≥0.95) | ≥40% pass without LLM judge |
| **exp_12** | `budgets.md §1` cost-ceiling enforcement | Inject a runaway loop that issues 1000 Haiku calls; ensure `Cost Ceiling Should Not Be Exceeded` halts the suite | Suite halts within 50 calls of the ceiling |
| **exp_13** | `budgets.md §3` end-to-end skill grading wall-clock | `atest/perf/perf_suite.robot` runs default-CI config (N=10, Tier-2 judge) on 1 representative skill | Wall-clock ≤60 s (with parallelism), ≤90 s p95 |

---

## 3. Pass/Fail Reporting

- All 13 experiments emit a single-line JSON to `tests/benchmarks/results/<exp_id>.json`: `{"id": "exp_03", "pass": true, "actual": 0.41, "budget": 0.50, "unit": "s", "note": ""}`.
- A roll-up script `scripts/perf_rollup.py` aggregates into `tests/benchmarks/results/_summary.json` with overall pass count.
- Phase-1 GA gate: **all 13 experiments must pass**, OR each failure must have a documented `[KNOWN-LIMIT]` entry in the release notes with a follow-up issue tracked.
- Numbers feed back into `budgets.md` (replacing `[ASSUMPTION → exp_NN]` markers with the measured value and source experiment ID), `tier-routing.md` (router weights tuned per exp_08), and `non-determinism-cost-model.md` (cache/adaptive-N projections re-projected per exp_09 / exp_10).

---

## 4. Continuous Validation Post-GA

After Phase-1 ships, the same harness runs nightly against the canary suite (research §8 risk #6 vendor-side drift). Results are stored as time-series in the existing Grafana stack (`manykarim/robot-framework-reporting` per research §4.5). Mann-Whitney U vs. the prior 7-day window flags vendor-side performance/quality regressions before they break user budgets — closing the loop on the canary pattern Stella Laurenzo informally pioneered (`anthropics/claude-code#42796`).
