"""Bootstrap confidence intervals (research §2.7, §3.4).

Wraps `scipy.stats.bootstrap` with named statistics (``mean``, ``median``,
``proportion``) plus an escape hatch for arbitrary callables. Defaults to
9999 resamples and 95% CI per Hall (1992) / Efron & Tibshirani.

Surface confirmed by `docs/research/experiments/exp_06_scipy_stats.log`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import NamedTuple

import numpy as np

Statistic = str | Callable[[np.ndarray], float]

_NAMED_STATS: dict[str, Callable[[np.ndarray], float]] = {
    "mean": lambda a: float(np.mean(a)),
    "median": lambda a: float(np.median(a)),
    "proportion": lambda a: float(np.mean(a)),  # for 0/1 samples; mean == proportion
    "std": lambda a: float(np.std(a, ddof=1)) if len(a) > 1 else 0.0,
}


class BootstrapInterval(NamedTuple):
    """Returned by :func:`bootstrap_ci`."""

    low: float
    high: float
    confidence: float
    statistic: str
    n_resamples: int


def _resolve_statistic(statistic: Statistic) -> tuple[Callable[[np.ndarray], float], str]:
    if callable(statistic):
        return statistic, getattr(statistic, "__name__", "callable")
    name = statistic.lower()
    if name not in _NAMED_STATS:
        raise ValueError(f"Unknown statistic {statistic!r}. Choose one of {sorted(_NAMED_STATS)} or pass a callable.")
    return _NAMED_STATS[name], name


def bootstrap_ci(
    samples: Sequence[float],
    statistic: Statistic = "mean",
    confidence: float = 0.95,
    n_resamples: int = 9999,
    random_state: int | None = None,
) -> BootstrapInterval:
    """Compute a bootstrap CI for ``samples``.

    Parameters
    ----------
    samples : Sequence[float]
        Observed metric values (must be non-empty).
    statistic : str | Callable, default ``"mean"``
        One of ``"mean" | "median" | "proportion" | "std"`` or a numpy-vectorised
        callable. ``"proportion"`` expects 0/1 valued samples.
    confidence : float, default ``0.95``
        Desired CI level in ``(0, 1)``.
    n_resamples : int, default ``9999``
        Bootstrap iterations (scipy default is 9999, kept here for clarity).
    random_state : int | None
        Optional seed for reproducibility (scipy uses a numpy ``Generator``).

    Returns
    -------
    BootstrapInterval
        ``(low, high, confidence, statistic, n_resamples)``.
    """
    if len(samples) == 0:
        raise ValueError("bootstrap_ci requires at least one sample.")
    if not 0.0 < confidence < 1.0:
        raise ValueError(f"confidence must be in (0, 1); got {confidence!r}.")
    if n_resamples < 1:
        raise ValueError(f"n_resamples must be >= 1; got {n_resamples!r}.")

    stat_fn, stat_name = _resolve_statistic(statistic)
    arr = np.asarray(samples, dtype=float)

    # scipy.stats.bootstrap rejects single-sample inputs; degenerate by definition,
    # so we return the point statistic as a zero-width interval.
    if arr.size < 2:
        point = float(stat_fn(arr))
        return BootstrapInterval(
            low=point,
            high=point,
            confidence=confidence,
            statistic=stat_name,
            n_resamples=n_resamples,
        )

    from scipy import stats as scipy_stats  # lazy import

    rng = np.random.default_rng(random_state)
    res = scipy_stats.bootstrap(
        (arr,),
        stat_fn,
        n_resamples=n_resamples,
        confidence_level=confidence,
        random_state=rng,
        method="BCa",
    )
    return BootstrapInterval(
        low=float(res.confidence_interval.low),
        high=float(res.confidence_interval.high),
        confidence=confidence,
        statistic=stat_name,
        n_resamples=n_resamples,
    )
