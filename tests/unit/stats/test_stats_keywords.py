"""Behavioural tests for the StatsKeywords class.

These tests bypass Robot Framework's runtime — they instantiate
``StatsKeywords`` directly and call its methods, asserting the same shape
that a `.robot` file would observe. Robot's ``BuiltIn().run_keyword`` is only
invoked from ``Run N Times``, which we cover separately in an acceptance
suite (kept out of the unit layer).
"""

from __future__ import annotations

import pytest

from AgentGuard._assertions import AssertionOperator
from AgentGuard.stats.library import StatsKeywords


@pytest.fixture(name="kw")
def _kw() -> StatsKeywords:
    return StatsKeywords()


def test_pass_at_k_returns_value_without_operator(kw: StatsKeywords) -> None:
    out = kw.pass_at_k([True] * 9 + [False], k=1)
    assert out == pytest.approx(0.9)


def test_pass_at_k_passes_with_operator(kw: StatsKeywords) -> None:
    out = kw.pass_at_k([True] * 9 + [False], k=1, assertion_operator=AssertionOperator[">="], assertion_expected=0.5)
    assert out == pytest.approx(0.9)


def test_pass_at_k_string_operator_alias(kw: StatsKeywords) -> None:
    out = kw.pass_at_k([True] * 9 + [False], k=1, assertion_operator=">=", assertion_expected=0.5)
    assert out == pytest.approx(0.9)


def test_pass_at_k_fails_with_operator(kw: StatsKeywords) -> None:
    with pytest.raises(AssertionError):
        kw.pass_at_k([True] + [False] * 9, k=1, assertion_operator=">=", assertion_expected=0.5)


def test_pass_at_k_accepts_string_outcomes(kw: StatsKeywords) -> None:
    # Robot Framework string args like ${TRUE}/${FALSE} → "True"/"False"
    out = kw.pass_at_k(
        ["true", "true", "false", "true", "true"],
        k=1,
        assertion_operator=">=",
        assertion_expected=0.5,
    )
    assert out == pytest.approx(0.8)


def test_total_agreement_rate_raw_returns_value(kw: StatsKeywords) -> None:
    out = kw.total_agreement_rate(["a", "a", "a", "b"], mode="raw")
    assert out == pytest.approx(0.75)


def test_total_agreement_rate_raw_with_operator(kw: StatsKeywords) -> None:
    out = kw.total_agreement_rate(["a", "a", "a", "b"], assertion_operator=">=", assertion_expected=0.5, mode="raw")
    assert out == pytest.approx(0.75)


def test_total_agreement_rate_answer_default_parser(kw: StatsKeywords) -> None:
    out = kw.total_agreement_rate(
        ["YES", "yes", " yes ", "no"],
        assertion_operator=">=",
        assertion_expected=0.5,
        mode="answer",
    )
    assert out == pytest.approx(0.75)


def test_total_agreement_rate_fails_with_operator(kw: StatsKeywords) -> None:
    with pytest.raises(AssertionError):
        kw.total_agreement_rate(
            ["a", "b", "c", "d"],
            assertion_operator=">=",
            assertion_expected=0.9,
            mode="raw",
        )


def test_mann_whitney_passes_for_dominant_sample(kw: StatsKeywords) -> None:
    cur = list(range(10, 30))
    base = list(range(0, 20))
    p = kw.mann_whitney_u_should_show_improvement(cur, base, alpha=0.05)
    assert p < 0.05


def test_mann_whitney_fails_when_no_improvement(kw: StatsKeywords) -> None:
    cur = list(range(10))
    base = list(range(10))
    with pytest.raises(AssertionError):
        kw.mann_whitney_u_should_show_improvement(cur, base, alpha=0.05)


def test_cliffs_delta_keyword(kw: StatsKeywords) -> None:
    out = kw.cliffs_delta_should_be_at_least([10] * 5, [1] * 5, delta=0.5)
    assert out == pytest.approx(1.0)
    with pytest.raises(AssertionError):
        kw.cliffs_delta_should_be_at_least([1, 2, 3], [1, 2, 3], delta=0.1)


def test_vargha_delaney_keyword(kw: StatsKeywords) -> None:
    out = kw.vargha_delaney_a_should_be_at_least([10] * 5, [1] * 5, threshold=0.7)
    assert out == pytest.approx(1.0)
    with pytest.raises(AssertionError):
        kw.vargha_delaney_a_should_be_at_least([1, 2, 3], [1, 2, 3], threshold=0.6)


def test_bootstrap_ci_keyword(kw: StatsKeywords) -> None:
    samples = [0.8, 0.82, 0.79, 0.81, 0.83, 0.78, 0.80, 0.82, 0.81, 0.79]
    low, high = kw.bootstrap_confidence_interval(samples, confidence=0.95, n_resamples=1000)
    assert low < 0.81 < high


def test_bootstrap_ci_should_contain_keyword(kw: StatsKeywords) -> None:
    samples = [0.8] * 10 + [0.81] * 5
    low, high = kw.bootstrap_confidence_interval_should_contain(
        samples, expected_value=0.805, confidence=0.95, n_resamples=1000
    )
    assert low <= 0.805 <= high


def test_bootstrap_ci_should_contain_fails(kw: StatsKeywords) -> None:
    samples = [0.5] * 20
    with pytest.raises(AssertionError):
        kw.bootstrap_confidence_interval_should_contain(samples, expected_value=0.9, confidence=0.95, n_resamples=500)


def test_compute_variance_banner_basic(kw: StatsKeywords) -> None:
    banner = kw.compute_variance_banner([0.80, 0.82, 0.78, 0.81, 0.79])
    assert banner["n"] == 5
    assert banner["mean"] == pytest.approx(0.8, abs=0.01)
    assert banner["std"] > 0
    assert banner["cv"] > 0


def test_compute_variance_banner_handles_non_numeric(kw: StatsKeywords) -> None:
    banner = kw.compute_variance_banner(["foo", "bar"])
    assert banner == {"n": 0, "mean": None, "std": None, "cv": None}


def test_compute_variance_banner_single_value(kw: StatsKeywords) -> None:
    banner = kw.compute_variance_banner([0.7])
    assert banner["n"] == 1
    assert banner["std"] == 0.0
    assert banner["cv"] == 0.0
