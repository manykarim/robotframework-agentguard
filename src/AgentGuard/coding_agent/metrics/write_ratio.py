"""``Write-vs-Edit mutation ratio`` — % of mutations done as full-file Write.

Research §2.6 baseline: good 4.9%, degraded 11.1%. ADR-010 default 0.06.
"""

from __future__ import annotations

from typing import Final

from ._session_proto import SessionLike
from .types import MetricResult

__all__ = ["NAME", "DEFAULT_THRESHOLD", "DIRECTION", "compute"]

NAME: Final = "write_mutation_ratio"
DEFAULT_THRESHOLD: Final = 0.06
DIRECTION: Final = "below"

_WRITE_NAMES = {"Write", "write"}
_EDIT_NAMES = {"Edit", "edit", "MultiEdit", "multi_edit"}


def compute(session: SessionLike, *, threshold: float | None = DEFAULT_THRESHOLD) -> MetricResult:
    writes = sum(1 for tc in session.tool_calls if tc.name in _WRITE_NAMES)
    edits = sum(1 for tc in session.tool_calls if tc.name in _EDIT_NAMES)
    total_mutations = writes + edits
    ratio = writes / total_mutations if total_mutations else 0.0
    passed = (ratio <= threshold) if threshold is not None else None
    return MetricResult(
        name=NAME,
        value=ratio,
        unit="fraction",
        threshold=threshold,
        direction=DIRECTION,
        passed=passed,
        details={"writes": writes, "edits": edits},
    )
