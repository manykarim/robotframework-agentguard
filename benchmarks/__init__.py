"""Phase-1 micro-benchmarks for AgentGuard.

Each test in this package validates one row from `docs/performance/budgets.md`
using `pytest-benchmark`'s `benchmark.pedantic` API. Tests fail (not just warn)
when the measured value exceeds the documented hard ceiling.

Modules whose source is not yet implemented are skipped via `pytest.skip` so
benchmarks never block other agents — see `docs/performance/benchmarks-plan.md`.
"""
