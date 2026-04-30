"""Mann-Whitney U primitive (ADR-005, research §2.7).

Companion to `test_stats_keywords.py`/`test_stats_primitives.py` — focuses on
the standalone `mann_whitney_u` function: API contract, alternative axis,
error paths.
"""

from __future__ import annotations

import pytest

from AgentGuard.stats.mannwhitney import MannWhitneyResult, mann_whitney_u


class TestMannWhitneyResult:
    def test_namedtuple_fields(self) -> None:
        r = MannWhitneyResult(statistic=1.0, pvalue=0.5, alternative="greater")
        assert r.statistic == 1.0
        assert r.pvalue == 0.5
        assert r.alternative == "greater"


class TestMannWhitneyU:
    def test_clear_improvement_p_below_alpha(self) -> None:
        baseline = [0.10, 0.20, 0.15, 0.18, 0.22, 0.19, 0.21, 0.17, 0.16, 0.20]
        current = [0.70, 0.75, 0.72, 0.68, 0.74, 0.69, 0.73, 0.71, 0.70, 0.76]
        res = mann_whitney_u(current, baseline, alternative="greater")
        assert res.pvalue < 0.001
        assert res.statistic > 0
        assert res.alternative == "greater"

    def test_no_improvement_p_above_alpha(self) -> None:
        baseline = [0.5] * 10
        current = [0.5] * 10
        res = mann_whitney_u(current, baseline, alternative="greater")
        assert res.pvalue >= 0.05

    def test_two_sided_alternative(self) -> None:
        cur = [0.5, 0.6, 0.4, 0.55]
        base = [0.51, 0.59, 0.41, 0.54]
        res = mann_whitney_u(cur, base, alternative="two-sided")
        assert res.alternative == "two-sided"

    def test_less_alternative(self) -> None:
        cur = [0.1, 0.2, 0.15]
        base = [0.7, 0.8, 0.75]
        res = mann_whitney_u(cur, base, alternative="less")
        assert res.pvalue < 0.1

    def test_empty_current_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            mann_whitney_u([], [1.0, 2.0], alternative="greater")

    def test_empty_baseline_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            mann_whitney_u([1.0, 2.0], [], alternative="greater")
