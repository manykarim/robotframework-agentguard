"""One-shot ``compute_42796_pack`` — runs all 12 calculators on one Session.

``baseline`` is reserved for the Mann-Whitney comparison wired through the
``stats`` module; this pack only performs deterministic threshold checks.
The keyword layer (``CodingAgentKeywords``) attaches the statistical verdict
on top of the returned :class:`BehavioralReport`.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ._session_proto import SessionLike
from .registry import METRICS
from .types import BehavioralReport, Health, MetricResult

__all__ = ["compute_42796_pack"]

#: Calculators where ``passed=None`` is normal (no deterministic threshold)
#: and therefore must NOT flip overall_health to ``unknown``.
_OPTIONAL: frozenset[str] = frozenset({"token_usage_per_prompt"})


def _aggregate(results: dict[str, MetricResult]) -> Health:
    saw_unknown = False
    for name, res in results.items():
        if res.passed is False:
            return "degraded"
        if res.passed is None and name not in _OPTIONAL:
            saw_unknown = True
    return "unknown" if saw_unknown else "healthy"


def compute_42796_pack(
    session: SessionLike,
    *,
    baseline: BehavioralReport | None = None,  # noqa: ARG001 — reserved for stats hook
) -> BehavioralReport:
    """Run every calculator; aggregate into a :class:`BehavioralReport`."""
    results: dict[str, MetricResult] = {}
    for name, spec in METRICS.items():
        results[name] = spec.compute(session, threshold=spec.default_threshold)
    return BehavioralReport(
        session_id=getattr(session, "id", "unknown"),
        metrics=results,
        overall_health=_aggregate(results),
        computed_at=datetime.now(tz=UTC),
    )
