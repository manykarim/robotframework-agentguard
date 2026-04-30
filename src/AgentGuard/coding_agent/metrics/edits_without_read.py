"""``Edits without prior Read`` — % of edits to a file never previously read.

Research §2.6 baseline: good 6.2%, degraded 33.7%. ADR-010 default 0.10.
"""

from __future__ import annotations

from typing import Any, Final

from ._session_proto import SessionLike
from .types import MetricResult

__all__ = ["NAME", "DEFAULT_THRESHOLD", "DIRECTION", "compute"]

NAME: Final = "edits_without_prior_read"
DEFAULT_THRESHOLD: Final = 0.10
DIRECTION: Final = "below"

_READ_NAMES = {"Read", "read"}
_EDIT_NAMES = {"Edit", "edit", "Write", "write", "MultiEdit", "multi_edit"}


def _path(args: dict[str, Any]) -> str | None:
    for key in ("file_path", "path", "filename"):
        v = args.get(key)
        if isinstance(v, str) and v:
            return v
    return None


def compute(session: SessionLike, *, threshold: float | None = DEFAULT_THRESHOLD) -> MetricResult:
    seen_reads: set[str] = set()
    edits_total = 0
    edits_without_read = 0
    for tc in session.tool_calls:
        path = _path(tc.arguments) if isinstance(tc.arguments, dict) else None
        if tc.name in _READ_NAMES and path is not None:
            seen_reads.add(path)
            continue
        if tc.name in _EDIT_NAMES:
            edits_total += 1
            if path is None or path not in seen_reads:
                edits_without_read += 1
    ratio = edits_without_read / edits_total if edits_total else 0.0
    passed = (ratio <= threshold) if threshold is not None else None
    return MetricResult(
        name=NAME,
        value=ratio,
        unit="fraction",
        threshold=threshold,
        direction=DIRECTION,
        passed=passed,
        details={"edits_total": edits_total, "edits_without_read": edits_without_read},
    )
