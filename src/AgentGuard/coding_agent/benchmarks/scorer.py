"""Generic pass@k aggregation + per-suite scorers shared by every benchmark.

All benchmark loaders ultimately delegate to this module so the per-loader
``score()`` functions remain trivial (pass-through dicts). The pass@k math
itself lives in :func:`AgentGuard.stats.pass_at_k.pass_at_k` (Phase 1) — we
re-expose it here with a benchmark-friendly signature that takes a flat list
of :class:`RunResult` objects.

The ``per_problem_outcomes`` helper buckets results by ``task_id`` so a
benchmark run with N samples per problem (the canonical HumanEval pass@k
shape) can be scored without callers implementing the bucketing themselves.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from AgentGuard.stats.pass_at_k import pass_at_k as _pass_at_k

from .base import RunResult

__all__ = [
    "pass_rate",
    "per_problem_outcomes",
    "pass_at_k_from_results",
    "first_run_pass_rate",
    "resolved_rate",
]


def pass_rate(results: Iterable[RunResult]) -> float:
    """Fraction of ``results`` with ``passed=True`` (treating empty as 0.0)."""
    materialised = list(results)
    if not materialised:
        return 0.0
    return sum(1 for r in materialised if r.passed) / len(materialised)


def per_problem_outcomes(results: Iterable[RunResult]) -> list[list[bool]]:
    """Bucket ``results`` by ``task_id`` and return a list-of-lists of outcomes.

    The returned shape is exactly what
    :func:`AgentGuard.stats.pass_at_k.pass_at_k` expects in its nested form:
    one inner list per problem, one bool per sample. Bucket order is the
    *first-seen* order of ``task_id`` so the result is deterministic for a
    given input ordering.
    """
    buckets: dict[str, list[bool]] = defaultdict(list)
    order: list[str] = []
    for r in results:
        if r.task_id not in buckets:
            order.append(r.task_id)
        buckets[r.task_id].append(bool(r.passed))
    return [buckets[k] for k in order]


def pass_at_k_from_results(results: Iterable[RunResult], k: int) -> float:
    """HumanEval pass@k over ``results`` (averaged across problems).

    A flat run (one sample per problem) reduces to the plain pass-rate when
    ``k == 1`` because :func:`AgentGuard.stats.pass_at_k.pass_at_k` validates
    ``k <= n_i`` per problem.
    """
    nested = per_problem_outcomes(results)
    if not nested:
        return 0.0
    # Drop problems with fewer than k samples — they cannot contribute to pass@k.
    eligible = [outcomes for outcomes in nested if len(outcomes) >= k]
    if not eligible:
        return 0.0
    return _pass_at_k(eligible, k)


def first_run_pass_rate(results: Iterable[RunResult]) -> float:
    """Aider's "plausible solution" criterion (research §2.5).

    Defined as the fraction of *unique tasks* whose *first attempt* passed —
    this matters when callers re-run failed tasks and want a leakage-free
    signal. We treat the first :class:`RunResult` per ``task_id`` (in
    iteration order) as the first attempt.
    """
    seen: dict[str, bool] = {}
    for r in results:
        if r.task_id not in seen:
            seen[r.task_id] = bool(r.passed)
    if not seen:
        return 0.0
    return sum(1 for ok in seen.values() if ok) / len(seen)


def resolved_rate(results: Iterable[RunResult]) -> float:
    """SWE-bench's headline metric — alias for :func:`pass_rate`.

    Kept as a separate name so the SWE-bench docstring + the code agree on
    terminology (the SWE-bench paper / leaderboards always say "% Resolved").
    """
    return pass_rate(results)
