"""``User interrupts per 1K tool calls`` — Esc / [Request interrupted] events.

Research §2.6 baseline: good 0.9/1K, degraded 11.4/1K. ADR-010 default 2.0.
"""

from __future__ import annotations

from typing import Final

from ._session_proto import SessionLike
from .types import MetricResult

__all__ = ["NAME", "DEFAULT_THRESHOLD", "DIRECTION", "compute"]

NAME: Final = "user_interrupts_per_1k"
DEFAULT_THRESHOLD: Final = 2.0
DIRECTION: Final = "below"


def compute(session: SessionLike, *, threshold: float | None = DEFAULT_THRESHOLD) -> MetricResult:
    n_interrupts = len(session.interrupts)
    n_calls = max(len(session.tool_calls), 1)
    per_1k = n_interrupts * 1000.0 / n_calls
    passed = (per_1k <= threshold) if threshold is not None else None
    return MetricResult(
        name=NAME,
        value=per_1k,
        unit="per_1k_tool_calls",
        threshold=threshold,
        direction=DIRECTION,
        passed=passed,
        details={"interrupts": n_interrupts, "tool_calls": n_calls},
    )
