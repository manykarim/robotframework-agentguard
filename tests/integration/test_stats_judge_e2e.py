"""Integration — stats + judge keyword wrappers."""

from __future__ import annotations

import random

import pytest

from AgentGuard.judge.library import JudgeKeywords
from AgentGuard.stats.library import StatsKeywords


@pytest.fixture
def stats() -> StatsKeywords:
    return StatsKeywords()


def test_mannwhitney_detects_shifted_distribution(stats: StatsKeywords) -> None:
    rng = random.Random(42)
    baseline = [rng.gauss(0, 1) for _ in range(60)]
    current = [rng.gauss(0.6, 1) for _ in range(60)]
    stats.mann_whitney_u_should_show_improvement(current, baseline, alpha=0.05)


def test_cliffs_delta_threshold(stats: StatsKeywords) -> None:
    a = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    b = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2]
    stats.cliffs_delta_should_be_at_least(a, b, delta=0.5)


def test_bootstrap_ci_contains_population_mean(stats: StatsKeywords) -> None:
    rng = random.Random(7)
    samples = [rng.gauss(10.0, 2.0) for _ in range(50)]
    low, high = stats.bootstrap_confidence_interval(samples, statistic="mean", confidence=0.95)
    assert low <= 10.0 <= high


def test_pass_at_k_basic(stats: StatsKeywords) -> None:
    outcomes = [True, False, True, True, False, True, True, False, True, True]
    stats.pass_at_k_should_be_above(outcomes, k=1, threshold=0.5)


def test_total_agreement_rate(stats: StatsKeywords) -> None:
    outputs = ["a", "a", "a", "b", "a"]
    stats.total_agreement_rate_should_be_above(outputs, threshold=0.5)


def test_compute_variance_banner(stats: StatsKeywords) -> None:
    runs = [1.0, 1.1, 0.9, 1.05, 0.95]
    banner = stats.compute_variance_banner(runs)
    assert banner["n"] == 5
    assert "mean" in banner and "std" in banner and "cv" in banner


def test_judge_loads_rubric_from_markdown(tmp_path) -> None:
    rubric_md = tmp_path / "r.md"
    rubric_md.write_text(
        "# Correctness\n- Good [1.0]\n- Bad [0.0]\n",
        encoding="utf-8",
    )
    judge = JudgeKeywords()
    rubric = judge.load_rubric(str(rubric_md))
    assert rubric is not None
