"""Result + report dataclasses for the #42796 metric pack.

Per ADR-010: every calculator returns a :class:`MetricResult`; the one-shot
:func:`AgentGuard.coding_agent.metrics.pack.compute_42796_pack` aggregates
them into a :class:`BehavioralReport`.

Both are mutable so the Robot Framework keyword layer can attach extra
context (e.g. a Mann-Whitney p-value) before logging.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

__all__ = ["MetricResult", "BehavioralReport", "Direction", "Health"]

#: Whether the metric is "good" when above (e.g. Read:Edit ratio) or below
#: (e.g. Stop-hook violations).
Direction = Literal["above", "below"]

#: Aggregate verdict for the full 12-metric pack.
Health = Literal["healthy", "degraded", "unknown"]


@dataclass
class MetricResult:
    """One #42796 metric calculation outcome.

    ``passed`` is ``None`` when no threshold was supplied (typical for
    ``Token Usage Per Prompt`` which only meaningfully passes/fails against
    a baseline distribution — Mann-Whitney lives in ``stats``).
    """

    name: str
    value: float
    unit: str
    threshold: float | None = None
    direction: Direction = "below"
    passed: bool | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class BehavioralReport:
    """Aggregate report returned by :func:`compute_42796_pack`."""

    session_id: str
    metrics: dict[str, MetricResult]
    overall_health: Health
    computed_at: datetime
