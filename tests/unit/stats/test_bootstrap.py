"""Bootstrap CI primitive — covers `bootstrap_ci` directly (ADR-005)."""

from __future__ import annotations

import numpy as np
import pytest

from AgentGuard.stats.bootstrap import BootstrapInterval, bootstrap_ci


class TestBootstrapCI:
    def test_returns_namedtuple(self) -> None:
        ci = bootstrap_ci([1.0, 2.0, 3.0], n_resamples=100, random_state=0)
        assert isinstance(ci, BootstrapInterval)
        assert ci.statistic == "mean"
        assert ci.confidence == pytest.approx(0.95)
        assert ci.n_resamples == 100

    def test_ci_brackets_known_mean(self) -> None:
        rng = np.random.default_rng(42)
        sample = rng.normal(loc=5.0, scale=0.5, size=200).tolist()
        ci = bootstrap_ci(sample, n_resamples=500, confidence=0.95, random_state=0)
        assert ci.low < 5.0 < ci.high

    def test_median_statistic(self) -> None:
        ci = bootstrap_ci(
            [1.0, 2.0, 3.0, 4.0, 5.0],
            statistic="median",
            n_resamples=200,
            random_state=0,
        )
        assert ci.statistic == "median"

    def test_proportion_statistic(self) -> None:
        ci = bootstrap_ci(
            [1] * 80 + [0] * 20,
            statistic="proportion",
            n_resamples=500,
            random_state=1,
        )
        assert 0.7 <= ci.low <= 0.85
        assert 0.75 <= ci.high <= 0.9

    def test_callable_statistic(self) -> None:
        ci = bootstrap_ci(
            [1.0, 2.0, 3.0, 4.0],
            statistic=lambda a: float(np.max(a)),
            n_resamples=200,
            random_state=0,
        )
        assert ci.statistic == "<lambda>"

    def test_unknown_statistic_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown statistic"):
            bootstrap_ci([1.0, 2.0], statistic="banana")

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            bootstrap_ci([], statistic="mean")

    def test_invalid_confidence_raises(self) -> None:
        with pytest.raises(ValueError):
            bootstrap_ci([1.0, 2.0], confidence=1.5)
        with pytest.raises(ValueError):
            bootstrap_ci([1.0, 2.0], confidence=0.0)

    def test_invalid_n_resamples_raises(self) -> None:
        with pytest.raises(ValueError):
            bootstrap_ci([1.0, 2.0], n_resamples=0)

    def test_singleton_uses_percentile(self) -> None:
        # Single sample: BCa fails, the implementation falls back to percentile.
        ci = bootstrap_ci([5.0], n_resamples=100, random_state=0)
        # Both endpoints equal 5.0 (no variation) — must not raise.
        assert ci.low == ci.high == pytest.approx(5.0)
