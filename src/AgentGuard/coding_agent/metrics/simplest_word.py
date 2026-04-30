"""``"Simplest" word frequency per 1K tool calls`` — proxy for shortcut taking.

Research §2.6 baseline: good 2.7/1K, degraded 6.3/1K. ADR-010 default 5.0.
"""

from __future__ import annotations

import re
from typing import Final

from ._session_proto import SessionLike
from .types import MetricResult

__all__ = ["NAME", "DEFAULT_THRESHOLD", "DIRECTION", "compute"]

NAME: Final = "simplest_word_per_1k"
DEFAULT_THRESHOLD: Final = 5.0
DIRECTION: Final = "below"

_SIMPLEST_RE = re.compile(r"\bsimplest\b", re.IGNORECASE)


def compute(session: SessionLike, *, threshold: float | None = DEFAULT_THRESHOLD) -> MetricResult:
    matches = len(_SIMPLEST_RE.findall(session.text()))
    n_calls = max(len(session.tool_calls), 1)
    per_1k = matches * 1000.0 / n_calls
    passed = (per_1k <= threshold) if threshold is not None else None
    return MetricResult(
        name=NAME,
        value=per_1k,
        unit="per_1k_tool_calls",
        threshold=threshold,
        direction=DIRECTION,
        passed=passed,
        details={"matches": matches, "tool_calls": n_calls},
    )
