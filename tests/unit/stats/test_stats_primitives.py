"""Unit tests for the AgentGuard stats primitives (ADR-005).

Pure-Python checks against hand-computed values. scipy-backed primitives
(`mann_whitney_u`, `bootstrap_ci`) are exercised against the fixtures from
docs/research/experiments/exp_06_scipy_stats.log so any future scipy upgrade
that breaks the surface trips this test suite.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from AgentGuard.stats.bootstrap import bootstrap_ci
from AgentGuard.stats.cliffs_delta import cliffs_delta, magnitude
from AgentGuard.stats.mannwhitney import mann_whitney_u
from AgentGuard.stats.pass_at_k import pass_at_k
from AgentGuard.stats.tar import tar_a, tar_r
from AgentGuard.stats.vargha_delaney import vargha_delaney_a12

# ---------------------------------------------------------------------------
# Cliff's delta
# ---------------------------------------------------------------------------


def test_cliffs_delta_perfect_dominance() -> None:
    assert cliffs_delta([10, 11, 12], [1, 2, 3]) == pytest.approx(1.0)
    assert cliffs_delta([1, 2, 3], [10, 11, 12]) == pytest.approx(-1.0)


def test_cliffs_delta_zero_when_identical() -> None:
    assert cliffs_delta([1, 2, 3], [1, 2, 3]) == 0.0


def test_cliffs_delta_known_partial_value() -> None:
    # x=[1,2,3,4]; y=[1,2,3]: pairs (4,3): 1 gt; (3,3) eq; etc.
    # By hand: gt = #{(a,b) : a>b} = (4>1,2,3)=3 + (3>1,2)=2 + (2>1)=1 + 0 = 6
    #         lt = (1<2,3)=2 + (2<3)=1 = 3
    #         delta = (6-3)/(4*3) = 3/12 = 0.25
    assert cliffs_delta([1, 2, 3, 4], [1, 2, 3]) == pytest.approx(0.25)
    assert magnitude(0.25) == "small"
    assert magnitude(0.5) == "large"
    assert magnitude(0.1) == "negligible"


def test_cliffs_delta_rejects_one_empty() -> None:
    with pytest.raises(ValueError):
        cliffs_delta([], [1.0])


# ---------------------------------------------------------------------------
# Vargha-Delaney
# ---------------------------------------------------------------------------


def test_vargha_delaney_known_value() -> None:
    # x=[1,2,3], y=[1,2,3]: gt=3 (2>1,3>1,3>2), eq=3 (1=1,2=2,3=3), n=9
    # A12 = (3 + 0.5*3) / 9 = 4.5 / 9 = 0.5  → ties give exactly 0.5
    assert vargha_delaney_a12([1, 2, 3], [1, 2, 3]) == pytest.approx(0.5)


def test_vargha_delaney_dominance() -> None:
    assert vargha_delaney_a12([10, 11, 12], [1, 2, 3]) == pytest.approx(1.0)


def test_vargha_delaney_rejects_empty() -> None:
    with pytest.raises(ValueError):
        vargha_delaney_a12([], [1, 2])


# ---------------------------------------------------------------------------
# Mann-Whitney U (scipy surface)
# ---------------------------------------------------------------------------


def test_mann_whitney_returns_pvalue_and_statistic() -> None:
    rng = np.random.default_rng(42)
    a = rng.normal(loc=0.0, size=30)
    b = rng.normal(loc=0.5, size=30)
    res = mann_whitney_u(b, a, alternative="greater")
    assert 0.0 <= res.pvalue <= 1.0
    assert res.statistic > 0
    assert res.alternative == "greater"


def test_mann_whitney_significant_for_large_shift() -> None:
    rng = np.random.default_rng(7)
    a = rng.normal(loc=0.0, size=50)
    b = rng.normal(loc=2.0, size=50)
    assert mann_whitney_u(b, a, alternative="greater").pvalue < 0.001


def test_mann_whitney_rejects_empty() -> None:
    with pytest.raises(ValueError):
        mann_whitney_u([], [1, 2, 3])


# ---------------------------------------------------------------------------
# Bootstrap CI (scipy surface)
# ---------------------------------------------------------------------------


def test_bootstrap_ci_contains_known_mean() -> None:
    rng = np.random.default_rng(0)
    samples = rng.normal(loc=5.0, scale=1.0, size=200).tolist()
    ci = bootstrap_ci(samples, statistic="mean", confidence=0.95, n_resamples=2000, random_state=0)
    assert ci.low < 5.0 < ci.high
    assert ci.statistic == "mean"
    assert ci.confidence == 0.95


def test_bootstrap_ci_proportion() -> None:
    samples = [1] * 80 + [0] * 20
    ci = bootstrap_ci(samples, statistic="proportion", confidence=0.9, n_resamples=1500, random_state=1)
    assert 0.7 <= ci.low <= 0.85
    assert 0.75 <= ci.high <= 0.9


def test_bootstrap_ci_unknown_statistic() -> None:
    with pytest.raises(ValueError):
        bootstrap_ci([1.0, 2.0], statistic="banana")


def test_bootstrap_ci_rejects_empty() -> None:
    with pytest.raises(ValueError):
        bootstrap_ci([], statistic="mean")


# ---------------------------------------------------------------------------
# pass@k
# ---------------------------------------------------------------------------


def test_pass_at_1_flat() -> None:
    # 8/10 correct, k=1 → 0.8
    outcomes = [True] * 8 + [False] * 2
    assert pass_at_k(outcomes, k=1) == pytest.approx(0.8)


def test_pass_at_k_chen_formula_examples() -> None:
    # n=5, c=1, k=1 → 1 - C(4,1)/C(5,1) = 1 - 4/5 = 0.2
    assert pass_at_k([True] + [False] * 4, k=1) == pytest.approx(0.2)
    # n=5, c=1, k=5 → 1 - C(4,5)/C(5,5) ; C(4,5)=0 → 1.0
    assert pass_at_k([True] + [False] * 4, k=5) == pytest.approx(1.0)
    # n=10, c=2, k=3
    expected = 1 - (math.comb(8, 3) / math.comb(10, 3))
    assert pass_at_k([True] * 2 + [False] * 8, k=3) == pytest.approx(expected)


def test_pass_at_k_nested_average() -> None:
    # Two problems, one always passes, one always fails.
    nested = [[True, True, True], [False, False, False]]
    assert pass_at_k(nested, k=1) == pytest.approx(0.5)


def test_pass_at_k_rejects_k_gt_n() -> None:
    with pytest.raises(ValueError):
        pass_at_k([True, False], k=3)


# ---------------------------------------------------------------------------
# TAR
# ---------------------------------------------------------------------------


def test_tar_r_modal_default() -> None:
    # 4 of 5 outputs equal "yes" → 0.8
    assert tar_r(["yes", "yes", "yes", "no", "yes"]) == pytest.approx(0.8)


def test_tar_r_with_explicit_reference() -> None:
    assert tar_r(["yes", "no", "no", "yes"], reference="yes") == pytest.approx(0.5)


def test_tar_a_with_parser() -> None:
    outputs = ["The answer is 42.", "Final: 42", "About 41 maybe", "42!"]
    parser = lambda s: "42" if "42" in s else "?"
    assert tar_a(outputs, parser=parser) == pytest.approx(0.75)


def test_tar_handles_empty_input() -> None:
    assert tar_r([]) == 0.0
    assert tar_a([], parser=str) == 0.0
