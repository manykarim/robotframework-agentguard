"""``Stop-hook violations`` — count of ``Stop`` hook events with decision=block.

Research §2.6 baseline: 0 in healthy sessions; 173 across 17 degraded days
(≈10/day). ADR-010 default threshold 0.
"""

from __future__ import annotations

from typing import Final

from ._session_proto import SessionLike
from .types import MetricResult

__all__ = ["NAME", "DEFAULT_THRESHOLD", "DIRECTION", "compute"]

NAME: Final = "stop_hook_violations"
DEFAULT_THRESHOLD: Final = 0.0
DIRECTION: Final = "below"


def compute(session: SessionLike, *, threshold: float | None = DEFAULT_THRESHOLD) -> MetricResult:
    violations = sum(
        1
        for ev in session.hook_events
        if getattr(ev, "event", None) == "Stop" and getattr(ev, "decision", None) == "block"
    )
    passed = (violations <= threshold) if threshold is not None else None
    return MetricResult(
        name=NAME,
        value=float(violations),
        unit="count",
        threshold=threshold,
        direction=DIRECTION,
        passed=passed,
        details={"violations": violations, "hook_events": len(session.hook_events)},
    )
