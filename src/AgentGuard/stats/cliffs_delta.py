"""Cliff's delta effect-size measure (research §3.4).

scipy does not provide Cliff's δ, so we implement it manually using the
canonical pairwise-comparison formula::

    δ = (Σ I(x > y)  −  Σ I(x < y))  /  (n_x · n_y)

with the standard interpretation thresholds (Romano et al. 2006):

    |δ| < 0.147      negligible
    0.147 ≤ |δ| < 0.33   small
    0.33  ≤ |δ| < 0.474  medium
    0.474 ≤ |δ|          large

Verified by `docs/research/experiments/exp_06_scipy_stats.log` against the
exact same algorithm shape.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

EffectMagnitude = Literal["negligible", "small", "medium", "large"]


def cliffs_delta(x: Sequence[float], y: Sequence[float]) -> float:
    """Compute Cliff's δ for samples ``x`` and ``y``.

    Returns a value in ``[-1.0, 1.0]``. Positive δ means ``x`` tends to be
    larger than ``y`` (i.e. for a higher-is-better metric, ``x`` is the better
    sample). Returns ``0.0`` when both samples are empty (defensive; raises if
    only one is empty so the caller notices the asymmetry).
    """
    nx, ny = len(x), len(y)
    if nx == 0 and ny == 0:
        return 0.0
    if nx == 0 or ny == 0:
        raise ValueError(
            f"cliffs_delta requires both samples non-empty (got nx={nx}, ny={ny})."
        )

    gt = 0
    lt = 0
    for a in x:
        for b in y:
            if a > b:
                gt += 1
            elif a < b:
                lt += 1
    return (gt - lt) / (nx * ny)


def magnitude(delta: float) -> EffectMagnitude:
    """Return the qualitative label for ``delta`` per Romano et al. 2006."""
    abs_d = abs(delta)
    if abs_d < 0.147:
        return "negligible"
    if abs_d < 0.33:
        return "small"
    if abs_d < 0.474:
        return "medium"
    return "large"
