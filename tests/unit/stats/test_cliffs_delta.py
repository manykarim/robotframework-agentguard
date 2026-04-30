"""Cliff's δ primitive + magnitude classifier (ADR-005, Romano et al. 2006)."""

from __future__ import annotations

import pytest

from AgentGuard.stats.cliffs_delta import cliffs_delta, magnitude


class TestCliffsDelta:
    def test_identical_samples_zero(self) -> None:
        assert cliffs_delta([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(0.0)

    def test_x_strictly_greater_one(self) -> None:
        assert cliffs_delta([10, 11, 12], [1, 2, 3]) == pytest.approx(1.0)

    def test_y_strictly_greater_minus_one(self) -> None:
        assert cliffs_delta([1, 2, 3], [10, 11, 12]) == pytest.approx(-1.0)

    def test_known_partial_value(self) -> None:
        # Per docstring of stats: x=[1,2,3,4]; y=[1,2,3] → δ = (6−3)/12 = 0.25
        assert cliffs_delta([1, 2, 3, 4], [1, 2, 3]) == pytest.approx(0.25)

    def test_both_empty_returns_zero(self) -> None:
        assert cliffs_delta([], []) == 0.0

    def test_one_empty_raises(self) -> None:
        with pytest.raises(ValueError):
            cliffs_delta([], [1.0])
        with pytest.raises(ValueError):
            cliffs_delta([1.0], [])

    def test_in_unit_range(self) -> None:
        import random

        rng = random.Random(0)
        x = [rng.gauss(0, 1) for _ in range(50)]
        y = [rng.gauss(0.5, 1) for _ in range(50)]
        d = cliffs_delta(x, y)
        assert -1.0 <= d <= 1.0


class TestMagnitude:
    @pytest.mark.parametrize(
        "delta,expected",
        [
            (0.05, "negligible"),
            (-0.10, "negligible"),
            (0.20, "small"),
            (-0.20, "small"),
            (0.40, "medium"),
            (-0.40, "medium"),
            (0.60, "large"),
            (-0.99, "large"),
        ],
    )
    def test_known_thresholds(self, delta: float, expected: str) -> None:
        assert magnitude(delta) == expected

    def test_boundary_values(self) -> None:
        # 0.147 is the "small" threshold; just-below stays negligible.
        assert magnitude(0.146) == "negligible"
        assert magnitude(0.147) == "small"
        assert magnitude(0.329) == "small"
        assert magnitude(0.33) == "medium"
        assert magnitude(0.473) == "medium"
        assert magnitude(0.474) == "large"
