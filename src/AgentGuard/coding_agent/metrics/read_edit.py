"""``Read:Edit ratio`` — reads divided by edits.

Research §2.6 baseline: good 6.6, degraded 2.0. ADR-010 default threshold 4.0.
"""

from __future__ import annotations

from typing import Final

from ._session_proto import SessionLike
from .types import MetricResult

__all__ = ["NAME", "DEFAULT_THRESHOLD", "DIRECTION", "compute"]

NAME: Final = "read_edit_ratio"
DEFAULT_THRESHOLD: Final = 4.0
DIRECTION: Final = "above"

_READ_NAMES = {"Read", "read"}
_EDIT_NAMES = {"Edit", "edit", "Write", "write", "MultiEdit", "multi_edit"}


def compute(session: SessionLike, *, threshold: float | None = DEFAULT_THRESHOLD) -> MetricResult:
    reads = sum(1 for tc in session.tool_calls if tc.name in _READ_NAMES)
    edits = sum(1 for tc in session.tool_calls if tc.name in _EDIT_NAMES)
    # Convention: zero edits = "infinitely good" (no surface area to measure).
    if edits == 0:
        ratio = float("inf") if reads > 0 else 0.0
    else:
        ratio = reads / edits
    passed: bool | None
    if threshold is None:
        passed = None
    else:
        passed = ratio >= threshold
    return MetricResult(
        name=NAME,
        value=ratio,
        unit="ratio",
        threshold=threshold,
        direction=DIRECTION,
        passed=passed,
        details={"reads": reads, "edits": edits},
    )
