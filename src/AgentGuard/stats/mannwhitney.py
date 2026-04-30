"""Mann-Whitney U test wrapper (research §2.7, §3.4).

Thin shim around `scipy.stats.mannwhitneyu` so the rest of AgentGuard never
imports scipy directly. The two-sample non-parametric test of stochastic
dominance is the recommended baseline-comparison primitive when LLM outputs
are noisy and we cannot assume normality (Atil et al., Song et al.).

scipy 1.17.1 surface confirmed by `docs/research/experiments/exp_06_scipy_stats.log`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, NamedTuple

Alternative = Literal["two-sided", "less", "greater"]


class MannWhitneyResult(NamedTuple):
    """Test outcome — `(U, p)` plus the alternative actually used."""

    statistic: float
    pvalue: float
    alternative: Alternative


def mann_whitney_u(
    current: Sequence[float],
    baseline: Sequence[float],
    alternative: Alternative = "greater",
) -> MannWhitneyResult:
    """Run Mann-Whitney U on `(current, baseline)`.

    Parameters
    ----------
    current : Sequence[float]
        Sample under test (e.g. metric values from N runs of the new agent).
    baseline : Sequence[float]
        Reference sample to beat (e.g. metric values from N runs of the prior agent).
    alternative : Literal["two-sided", "less", "greater"], default ``"greater"``
        ``"greater"`` tests whether `current` stochastically dominates `baseline`,
        which is the usual regression-detection direction for higher-is-better
        metrics.

    Returns
    -------
    MannWhitneyResult
        ``statistic`` is the U value, ``pvalue`` is the p-value under the
        chosen alternative, ``alternative`` echoes the input for traceability.

    Raises
    ------
    ValueError
        If either sample is empty (scipy raises but the message is opaque).
    """
    if len(current) == 0 or len(baseline) == 0:
        raise ValueError("mann_whitney_u requires non-empty samples for both groups.")

    from scipy.stats import mannwhitneyu  # lazy import keeps top-level cheap

    res = mannwhitneyu(current, baseline, alternative=alternative)
    return MannWhitneyResult(
        statistic=float(res.statistic),
        pvalue=float(res.pvalue),
        alternative=alternative,
    )
