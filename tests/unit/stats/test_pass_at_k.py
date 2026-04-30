"""HumanEval pass@k primitive (Chen et al. 2021)."""

from __future__ import annotations

import math

import pytest

from AgentGuard.stats.pass_at_k import pass_at_k


class TestPassAtKFlat:
    def test_all_passing_one(self) -> None:
        assert pass_at_k([True], k=1) == pytest.approx(1.0)

    def test_none_passing_zero(self) -> None:
        assert pass_at_k([False] * 10, k=1) == pytest.approx(0.0)

    def test_eight_of_ten(self) -> None:
        assert pass_at_k([True] * 8 + [False] * 2, k=1) == pytest.approx(0.8)

    def test_chen_formula(self) -> None:
        # n=10, c=2, k=3 → 1 - C(8,3)/C(10,3)
        expected = 1 - (math.comb(8, 3) / math.comb(10, 3))
        assert pass_at_k([True] * 2 + [False] * 8, k=3) == pytest.approx(expected)

    def test_full_coverage_returns_one(self) -> None:
        assert pass_at_k([True] + [False] * 4, k=5) == pytest.approx(1.0)

    def test_known_value_partial(self) -> None:
        # n=5, c=2, k=3 → 1 - C(3,3)/C(5,3) = 1 - 1/10 = 0.9
        assert pass_at_k([True] * 2 + [False] * 3, k=3) == pytest.approx(0.9, rel=1e-6)


class TestPassAtKNested:
    def test_average_across_problems(self) -> None:
        nested = [[True, True, True], [False, False, False]]
        assert pass_at_k(nested, k=1) == pytest.approx(0.5)

    def test_uneven_per_problem(self) -> None:
        nested = [[True, True], [True, False, False, False]]
        # First problem: pass@1 = 1.0; second: c=1, n=4 → 1 - C(3,1)/C(4,1) = 0.25
        assert pass_at_k(nested, k=1) == pytest.approx((1.0 + 0.25) / 2)


class TestPassAtKInvalid:
    def test_k_zero_raises(self) -> None:
        with pytest.raises(ValueError):
            pass_at_k([True], k=0)

    def test_k_gt_n_raises(self) -> None:
        with pytest.raises(ValueError):
            pass_at_k([True, False], k=3)
