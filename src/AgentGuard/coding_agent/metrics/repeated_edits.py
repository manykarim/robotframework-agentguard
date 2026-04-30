"""``Repeated edits per file`` — files edited 3+ times in a 5-minute window.

Counts files (not edits) that received >=3 mutations inside any sliding
5-minute window. ADR-010 default threshold per session: 3.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Final

from ._session_proto import SessionLike
from .types import MetricResult

__all__ = ["NAME", "DEFAULT_THRESHOLD", "DIRECTION", "compute"]

NAME: Final = "repeated_edits_per_file"
DEFAULT_THRESHOLD: Final = 3.0
DIRECTION: Final = "below"

_EDIT_NAMES = {"Edit", "edit", "Write", "write", "MultiEdit", "multi_edit"}
_WINDOW = timedelta(minutes=5)


def _path(args: dict[str, Any]) -> str | None:
    for key in ("file_path", "path", "filename"):
        v = args.get(key)
        if isinstance(v, str) and v:
            return v
    return None


def compute(session: SessionLike, *, threshold: float | None = DEFAULT_THRESHOLD) -> MetricResult:
    by_path: dict[str, list[datetime | None]] = {}
    fallback = 0
    for tc in session.tool_calls:
        if tc.name not in _EDIT_NAMES:
            continue
        if not isinstance(tc.arguments, dict):
            fallback += 1
            continue
        path = _path(tc.arguments)
        if path is None:
            continue
        by_path.setdefault(path, []).append(tc.timestamp)

    hot_files = 0
    for stamps in by_path.values():
        # Drop None timestamps but track them as "all in one window" fallback.
        ts = sorted(s for s in stamps if isinstance(s, datetime))
        if not ts:
            if len(stamps) >= 3:
                hot_files += 1
            continue
        i = 0
        for j in range(len(ts)):
            while ts[j] - ts[i] > _WINDOW:
                i += 1
            if j - i + 1 >= 3:
                hot_files += 1
                break
    passed = (hot_files <= threshold) if threshold is not None else None
    return MetricResult(
        name=NAME,
        value=float(hot_files),
        unit="files",
        threshold=threshold,
        direction=DIRECTION,
        passed=passed,
        details={"distinct_files": len(by_path), "hot_files": hot_files},
    )
