"""Unit tests for ``metrics.self_admitted`` — apology/regret phrase rate."""

from __future__ import annotations

import pytest

try:
    from AgentGuard.coding_agent.metrics import self_admitted
    from AgentGuard.coding_agent.session.types import Message, Session, ToolCall
except ImportError:  # pragma: no cover — Phase 3 race
    pytest.skip("phase3: metrics.self_admitted not yet implemented", allow_module_level=True)


def _session(*, msg: str, tool_calls: int = 1) -> Session:
    return Session(
        id="x",
        source="claude-code",
        messages=[Message(role="assistant", content=msg)],
        tool_calls=[ToolCall(id=f"t{i}", name="Read", arguments={}) for i in range(tool_calls)],
    )


def test_constants() -> None:
    assert self_admitted.NAME == "self_admitted_errors_per_1k"
    assert self_admitted.DEFAULT_THRESHOLD == 0.2
    assert self_admitted.DIRECTION == "below"


def test_clean_message_zero() -> None:
    res = self_admitted.compute(_session(msg="Implementation complete."))
    assert res.value == 0.0
    assert res.passed is True


def test_detects_youre_right_lazy() -> None:
    res = self_admitted.compute(_session(msg="you're right, that was lazy", tool_calls=1))
    assert res.value > 0


def test_detects_my_apologies() -> None:
    res = self_admitted.compute(_session(msg="my apologies for that", tool_calls=1))
    assert res.value > 0


def test_detects_i_was_wrong() -> None:
    res = self_admitted.compute(_session(msg="I was wrong about that", tool_calls=1))
    assert res.value > 0


def test_threshold_breach_marks_failed() -> None:
    res = self_admitted.compute(_session(msg="my apologies, sorry, I was wrong", tool_calls=1))
    assert res.passed is False


def test_threshold_none_yields_none_passed() -> None:
    res = self_admitted.compute(_session(msg="my apologies"), threshold=None)
    assert res.passed is None


def test_zero_tool_calls_safe() -> None:
    s = Session(
        id="x",
        source="claude-code",
        messages=[Message(role="assistant", content="my apologies")],
    )
    res = self_admitted.compute(s)
    assert res.value > 0
