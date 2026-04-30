"""Internal helpers for ``stats.library`` — kept here to keep ``library.py`` < 300 lines.

Not part of the public Robot Framework keyword surface; do not import from
outside the ``stats`` subpackage.
"""

from __future__ import annotations

import math
import statistics
from typing import Any

from robot.api import logger


def coerce_outcomes(raw: Any) -> Any:
    """Robot-friendly coercion: ``${TRUE}`` / ``"false"`` / ``"pass"`` → bool.

    Accepts a flat ``list[Any]`` or a nested ``list[list[Any]]`` (one inner
    list per problem) — matches the two shapes accepted by
    :func:`AgentGuard.stats.pass_at_k.pass_at_k`.
    """
    truthy = {"true", "1", "pass", "yes", "y", "t"}
    falsy = {"false", "0", "fail", "no", "n", "f"}

    def _to_bool(v: Any) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(v)
        s = str(v).strip().lower()
        if s in truthy:
            return True
        if s in falsy:
            return False
        raise ValueError(f"Cannot interpret {v!r} as a pass/fail outcome.")

    if not isinstance(raw, list):
        raise TypeError(f"outcomes must be a list; got {type(raw).__name__}.")

    if raw and isinstance(raw[0], (list, tuple)):
        return [[_to_bool(s) for s in inner] for inner in raw]
    return [_to_bool(s) for s in raw]


def variance_banner(runs: list[Any]) -> dict[str, Any]:
    """Build the ADR-005 variance-banner payload (n / mean / std / cv)."""
    numeric: list[float] = []
    for r in runs:
        try:
            numeric.append(float(r))
        except (TypeError, ValueError):
            logger.warn(f"Compute Variance Banner: skipping non-numeric run {r!r}.")

    n = len(numeric)
    if n == 0:
        return {"n": 0, "mean": None, "std": None, "cv": None}
    if n == 1:
        return {"n": 1, "mean": numeric[0], "std": 0.0, "cv": 0.0}

    mean_v = statistics.fmean(numeric)
    std_v = statistics.stdev(numeric)
    cv = (std_v / abs(mean_v)) if mean_v != 0 else math.inf
    banner = {"n": n, "mean": mean_v, "std": std_v, "cv": cv}
    logger.info(f"Variance banner: n={n} mean={mean_v:.4f} std={std_v:.4f} cv={cv:.4f}")
    return banner
