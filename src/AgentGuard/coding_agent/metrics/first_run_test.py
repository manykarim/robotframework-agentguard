"""``First-run test pass rate`` — pass@1 on the project's pre-existing suite.

Heuristic: scan Bash tool calls + their tool_responses for known test runners
(pytest, jest, cargo test, go test, mvn, gradle, robot, npm test). A response
that contains ``PASSED`` / ``passed`` and lacks failure markers counts as a pass.

ADR-010 default threshold 0.9.
"""

from __future__ import annotations

import re
from typing import Final

from ._session_proto import SessionLike
from .types import MetricResult

__all__ = ["NAME", "DEFAULT_THRESHOLD", "DIRECTION", "compute"]

NAME: Final = "first_run_test_pass_rate"
DEFAULT_THRESHOLD: Final = 0.9
DIRECTION: Final = "above"

_RUNNER_RE = re.compile(
    r"\b(pytest|npm test|jest|vitest|cargo test|go test"
    r"|mvn test|gradle test|robot |uv run pytest)\b",
    re.IGNORECASE,
)
_PASS_RE = re.compile(r"\b(PASSED|passed|ok|OK)\b")
_FAIL_RE = re.compile(r"\b(FAILED|failed|ERROR|error|FAIL)\b")


def _is_test_call(name: str, args: dict[str, object]) -> bool:
    if name not in {"Bash", "bash", "Shell", "shell"}:
        return False
    cmd = args.get("command") or args.get("cmd") or ""
    return bool(isinstance(cmd, str) and _RUNNER_RE.search(cmd))


def compute(session: SessionLike, *, threshold: float | None = DEFAULT_THRESHOLD) -> MetricResult:
    by_id = {tr.tool_call_id: tr for tr in session.tool_responses}
    runs = 0
    passes = 0
    for tc in session.tool_calls:
        args = tc.arguments if isinstance(tc.arguments, dict) else {}
        if not _is_test_call(tc.name, args):
            continue
        runs += 1
        tr = by_id.get(tc.id)
        body = "" if tr is None else str(tr.content)
        if tr is None or tr.is_error:
            continue
        if _PASS_RE.search(body) and not _FAIL_RE.search(body):
            passes += 1
    rate = passes / runs if runs else 0.0
    if threshold is None or runs == 0:
        passed: bool | None = None
    else:
        passed = rate >= threshold
    return MetricResult(
        name=NAME,
        value=rate,
        unit="fraction",
        threshold=threshold,
        direction=DIRECTION,
        passed=passed,
        details={"runs": runs, "passes": passes},
    )
