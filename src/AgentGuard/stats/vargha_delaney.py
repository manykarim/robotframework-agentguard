"""Vargha-Delaney A12 effect-size measure (research §3.4).

A12 = P(x > y) + 0.5 · P(x = y), bounded in ``[0, 1]``::

    A12 = (Σ I(x > y) + 0.5 · Σ I(x == y)) / (n_x · n_y)

Conventional interpretation (Vargha & Delaney 2000):

    |A12 − 0.5| < 0.06     negligible
    0.06 ≤ |·| < 0.14      small
    0.14 ≤ |·| < 0.21      medium
    0.21 ≤ |·|             large

A12 = 0.5 means the two samples are stochastically indistinguishable; A12 > 0.5
means ``x`` tends to outperform ``y`` for higher-is-better metrics.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

A12Magnitude = Literal["negligible", "small", "medium", "large"]


def vargha_delaney_a12(x: Sequence[float], y: Sequence[float]) -> float:
    """Compute the Vargha-Delaney A12 statistic for samples ``x`` and ``y``.

    Returns a value in ``[0.0, 1.0]``. Raises ``ValueError`` if either sample
    is empty (A12 is undefined there — the caller almost certainly has a bug
    if one group has zero observations).
    """
    nx, ny = len(x), len(y)
    if nx == 0 or ny == 0:
        raise ValueError(
            f"vargha_delaney_a12 requires non-empty samples (got nx={nx}, ny={ny})."
        )

    gt = 0
    eq = 0
    for a in x:
        for b in y:
            if a > b:
                gt += 1
            elif a == b:
                eq += 1
    return (gt + 0.5 * eq) / (nx * ny)


def magnitude(a12: float) -> A12Magnitude:
    """Qualitative label for ``a12`` (distance from 0.5)."""
    diff = abs(a12 - 0.5)
    if diff < 0.06:
        return "negligible"
    if diff < 0.14:
        return "small"
    if diff < 0.21:
        return "medium"
    return "large"
