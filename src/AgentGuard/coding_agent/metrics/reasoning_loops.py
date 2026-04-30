"""``Reasoning loops per 1K tool calls`` — self-correction phrase frequency.

Research §2.6 baseline: good 8.2/1K, degraded 26.6/1K. ADR-010 default 12.
"""

from __future__ import annotations

import re
from typing import Final

from ._session_proto import SessionLike
from .types import MetricResult

__all__ = ["NAME", "DEFAULT_THRESHOLD", "DIRECTION", "compute"]

NAME: Final = "reasoning_loops_per_1k"
DEFAULT_THRESHOLD: Final = 12.0
DIRECTION: Final = "below"

# Phrases lifted directly from #42796 + commonly observed degraded sessions.
_LOOP_RE = re.compile(
    r"\b(oh wait|actually,|let me reconsider|on second thought|wait,|hmm,)\b",
    re.IGNORECASE,
)


def compute(session: SessionLike, *, threshold: float | None = DEFAULT_THRESHOLD) -> MetricResult:
    text = session.text()
    matches = len(_LOOP_RE.findall(text))
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
