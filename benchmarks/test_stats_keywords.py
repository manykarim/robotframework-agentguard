"""Validates stats-keyword Tier-1 budgets — `mannwhitney`, `cliffs_delta`, `bootstrap`.

| Test                        | Budget               | Source                       |
|-----------------------------|----------------------|------------------------------|
| `mannwhitneyu` n=30/30      | mean ≤ 5 ms          | budgets.md §1 (Tier-1)       |
| `cliffs_delta`  n=30/30     | mean ≤ 5 ms          | budgets.md §1 (Tier-1)       |
| `bootstrap` n=30, 1000 res. | mean ≤ 100 ms        | budgets.md §1 + research §3.4 |

The bootstrap budget is intentionally loose — scipy's BCa bootstrap is the
slowest of these three by an order of magnitude. The 100 ms ceiling still keeps
the keyword "snappy" inside an interactive RF run.
"""

from __future__ import annotations

import random
from typing import Any

import pytest

BUDGET_MWU_MEAN_MS = 5.0
BUDGET_CLIFFS_MEAN_MS = 5.0
BUDGET_BOOTSTRAP_MEAN_MS = 100.0


def _two_samples(seed: int = 42, n: int = 30) -> tuple[list[float], list[float]]:
    """Two synthetic samples with a small location shift, fixed seed."""
    rng = random.Random(seed)
    a = [rng.gauss(mu=0.5, sigma=0.2) for _ in range(n)]
    b = [rng.gauss(mu=0.4, sigma=0.2) for _ in range(n)]
    return a, b


@pytest.mark.benchmark(group="stats")
def test_mann_whitney_u_n30(benchmark: Any) -> None:
    """Mann-Whitney U on n=30/30 — mean ≤ 5 ms."""
    try:
        from AgentGuard.stats.mannwhitney import mann_whitney_u
    except ImportError:
        pytest.skip("AgentGuard.stats.mannwhitney not implemented yet")

    a, b = _two_samples()

    def _call() -> Any:
        return mann_whitney_u(a, b)

    benchmark.pedantic(_call, rounds=50, iterations=1, warmup_rounds=2)
    mean_ms = float(benchmark.stats.stats.mean) * 1000.0
    if mean_ms > BUDGET_MWU_MEAN_MS:
        pytest.fail(
            f"mann_whitney_u mean {mean_ms:.3f} ms exceeds budget "
            f"{BUDGET_MWU_MEAN_MS} ms (budgets.md §1)"
        )


@pytest.mark.benchmark(group="stats")
def test_cliffs_delta_n30(benchmark: Any) -> None:
    """Cliff's delta on n=30/30 — mean ≤ 5 ms."""
    try:
        from AgentGuard.stats.cliffs_delta import cliffs_delta
    except ImportError:
        pytest.skip("AgentGuard.stats.cliffs_delta not implemented yet")

    a, b = _two_samples()

    def _call() -> float:
        return cliffs_delta(a, b)

    benchmark.pedantic(_call, rounds=50, iterations=1, warmup_rounds=2)
    mean_ms = float(benchmark.stats.stats.mean) * 1000.0
    if mean_ms > BUDGET_CLIFFS_MEAN_MS:
        pytest.fail(
            f"cliffs_delta mean {mean_ms:.3f} ms exceeds budget "
            f"{BUDGET_CLIFFS_MEAN_MS} ms (budgets.md §1)"
        )


@pytest.mark.benchmark(group="stats")
def test_bootstrap_n30_1000_resamples(benchmark: Any) -> None:
    """Bootstrap CI on n=30 with 1000 resamples — mean ≤ 100 ms.

    NB: the production default is 9999 resamples; this micro-benchmark uses 1000
    so we are actually probing keyword overhead, not scipy's resampling cost.
    """
    try:
        from AgentGuard.stats.bootstrap import bootstrap_ci
    except ImportError:
        pytest.skip("AgentGuard.stats.bootstrap not implemented yet")

    a, _ = _two_samples()

    def _call() -> Any:
        return bootstrap_ci(a, statistic="mean", n_resamples=1000, random_state=0)

    benchmark.pedantic(_call, rounds=10, iterations=1, warmup_rounds=2)
    mean_ms = float(benchmark.stats.stats.mean) * 1000.0
    if mean_ms > BUDGET_BOOTSTRAP_MEAN_MS:
        pytest.fail(
            f"bootstrap_ci mean {mean_ms:.3f} ms exceeds budget "
            f"{BUDGET_BOOTSTRAP_MEAN_MS} ms (budgets.md §1)"
        )
