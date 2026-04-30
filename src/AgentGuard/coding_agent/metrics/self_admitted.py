"""``Self-admitted errors per 1K tool calls`` — ``"you're right, that was lazy"``.

Research §2.6 baseline: good 0.1/1K, degraded 0.5/1K. ADR-010 default 0.2.
"""

from __future__ import annotations

import re
from typing import Final

from ._session_proto import SessionLike
from .types import MetricResult

__all__ = ["NAME", "DEFAULT_THRESHOLD", "DIRECTION", "compute"]

NAME: Final = "self_admitted_errors_per_1k"
DEFAULT_THRESHOLD: Final = 0.2
DIRECTION: Final = "below"

_ADMIT_RE = re.compile(
    r"\b("
    r"you'?re right.*?(lazy|wrong|sloppy|sorry|my (apologies|mistake))"
    r"|i (was|am) wrong"
    r"|that was (sloppy|lazy|wrong)"
    r"|sorry,? (i|that)"
    r"|my (apologies|mistake)"
    r")\b",
    re.IGNORECASE | re.DOTALL,
)


def compute(session: SessionLike, *, threshold: float | None = DEFAULT_THRESHOLD) -> MetricResult:
    text = session.text()
    matches = len(_ADMIT_RE.findall(text))
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
