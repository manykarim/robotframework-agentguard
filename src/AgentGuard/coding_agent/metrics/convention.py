"""``Convention violation rate`` — thin wrapper over ``skills.conventions``.

The heavy lifting (banned-phrase scanning, mining NEVER/ALWAYS lines from
CLAUDE.md, root-folder write detection) lives in
:mod:`AgentGuard.skills.conventions`. We collect each assistant message's
text (preserving message order so the per-response indexing aligns with
``ConventionReport.rate``) and delegate.

ADR-010 default threshold 0.05 (5% of responses).
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from AgentGuard.skills.conventions import check_responses

from ._session_proto import SessionLike
from .types import MetricResult

__all__ = ["NAME", "DEFAULT_THRESHOLD", "DIRECTION", "compute"]

NAME: Final = "convention_violation_rate"
DEFAULT_THRESHOLD: Final = 0.05
DIRECTION: Final = "below"


def _assistant_texts(session: SessionLike) -> list[str]:
    out: list[str] = []
    for msg in session.messages:
        if getattr(msg, "role", None) != "assistant":
            continue
        content = msg.content
        if isinstance(content, str):
            out.append(content)
            continue
        if isinstance(content, list):
            chunks: list[str] = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text = part.get("text")
                    if isinstance(text, str):
                        chunks.append(text)
            out.append("\n".join(chunks))
    return out


def compute(
    session: SessionLike,
    *,
    threshold: float | None = DEFAULT_THRESHOLD,
    rules: str | Path | None = None,
) -> MetricResult:
    responses = _assistant_texts(session)
    report = check_responses(responses, rules=rules)
    rate = report.rate
    passed = (rate <= threshold) if threshold is not None else None
    return MetricResult(
        name=NAME,
        value=rate,
        unit="fraction",
        threshold=threshold,
        direction=DIRECTION,
        passed=passed,
        details={
            "responses": report.total_responses,
            "violations": len(report.violations),
        },
    )
