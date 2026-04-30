"""``Token usage per prompt`` — output+prompt tokens divided by user prompts.

Research §2.6 degraded: 64x output / 80x requests vs baseline. The deterministic
threshold is delegated to a baseline comparison (Mann-Whitney lives in
``stats``); when ``threshold`` is ``None`` we return ``passed=None`` so the
keyword layer can do the comparison itself.
"""

from __future__ import annotations

from typing import Final

from ._session_proto import SessionLike
from .types import MetricResult

__all__ = ["NAME", "DEFAULT_THRESHOLD", "DIRECTION", "compute"]

NAME: Final = "token_usage_per_prompt"
#: Token efficiency has no fixed deterministic threshold — pass/fail is
#: delegated to the Mann-Whitney baseline comparison in ``stats``. ``None``
#: means ``compute()`` returns ``passed=None`` and the pack treats this
#: metric as optional.
DEFAULT_THRESHOLD: Final[float | None] = None
DIRECTION: Final = "below"


def _user_prompt_count(session: SessionLike) -> int:
    return sum(
        1 for m in session.messages if getattr(m, "role", None) == "user"
    )


def compute(session: SessionLike, *, threshold: float | None = None) -> MetricResult:
    usage = session.usage
    total = int(getattr(usage, "completion_tokens", 0) + getattr(usage, "prompt_tokens", 0))
    prompts = max(_user_prompt_count(session), 1)
    per_prompt = total / prompts
    passed: bool | None
    if threshold is None:
        passed = None
    else:
        passed = per_prompt <= threshold
    return MetricResult(
        name=NAME,
        value=per_prompt,
        unit="tokens_per_prompt",
        threshold=threshold,
        direction=DIRECTION,
        passed=passed,
        details={"total_tokens": total, "user_prompts": prompts},
    )
