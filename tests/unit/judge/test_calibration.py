"""Cohen's κ and Krippendorff's α verification (ADR-011).

The Cohen's κ test below pins the exact hand-computed worked example
documented in ``AgentGuard/judge/calibration.py``::

    rater_a = ['good','good','bad','partial','bad','good']
    rater_b = ['good','partial','bad','partial','bad','good']
    κ = (5/6 − 12/36) / (1 − 12/36) = 0.5 / (2/3) = 0.75

This is the manual κ verification specifically requested by the Stats+Judge
Phase-1 brief.
"""

from __future__ import annotations

import math

import pytest

from AgentGuard.judge.calibration import (
    cohens_kappa,
    krippendorff_alpha,
)


def test_cohens_kappa_known_value() -> None:
    rater_a = ["good", "good", "bad", "partial", "bad", "good"]
    rater_b = ["good", "partial", "bad", "partial", "bad", "good"]
    assert cohens_kappa(rater_a, rater_b) == pytest.approx(0.75, abs=1e-9)


def test_cohens_kappa_perfect_agreement() -> None:
    a = ["x", "y", "z", "x", "y"]
    assert cohens_kappa(a, a) == pytest.approx(1.0)


def test_cohens_kappa_no_better_than_chance() -> None:
    # 50/50 disagreement on a balanced binary set → κ ~ 0
    a = ["yes"] * 10 + ["no"] * 10
    b = ["yes", "no"] * 10
    kappa = cohens_kappa(a, b)
    assert -0.05 < kappa < 0.05


def test_cohens_kappa_negative_when_systematic_disagreement() -> None:
    a = ["yes", "yes", "no", "no"]
    b = ["no", "no", "yes", "yes"]
    assert cohens_kappa(a, b) < 0


def test_cohens_kappa_rejects_length_mismatch() -> None:
    with pytest.raises(ValueError):
        cohens_kappa(["a"], ["a", "b"])


def test_cohens_kappa_rejects_empty() -> None:
    with pytest.raises(ValueError):
        cohens_kappa([], [])


def test_cohens_kappa_single_label_everywhere() -> None:
    # If both raters always pick the same value, κ should be 1.0 (trivially).
    a = ["good"] * 5
    b = ["good"] * 5
    assert cohens_kappa(a, b) == pytest.approx(1.0)


def test_krippendorff_alpha_perfect_agreement() -> None:
    ratings = [["a", "b", "c", "a"], ["a", "b", "c", "a"]]
    assert krippendorff_alpha(ratings) == pytest.approx(1.0)


def test_krippendorff_alpha_complete_disagreement_negative() -> None:
    ratings = [["a", "a", "a"], ["b", "b", "b"]]
    # All disagree across raters; α should be ≤ 0.
    assert krippendorff_alpha(ratings) <= 0.0


def test_krippendorff_alpha_handles_missing() -> None:
    ratings = [["a", "b", None, "c"], ["a", "b", "b", "c"]]
    val = krippendorff_alpha(ratings)
    assert -1.0 <= val <= 1.0
    assert math.isfinite(val)
