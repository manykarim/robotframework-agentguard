"""Unit tests for ``metrics.reasoning_loops`` — self-correction phrase rate."""

from __future__ import annotations

import pytest

try:
    from AgentGuard.coding_agent.metrics import reasoning_loops
    from AgentGuard.coding_agent.session.types import Message, Session, ToolCall
except ImportError:  # pragma: no cover — Phase 3 race
    pytest.skip("phase3: metrics.reasoning_loops not yet implemented", allow_module_level=True)


def _session(*, msg: str, tool_calls: int = 1) -> Session:
    return Session(
        id="x",
        source="claude-code",
        messages=[Message(role="assistant", content=msg)],
        tool_calls=[ToolCall(id=f"t{i}", name="Read", arguments={}) for i in range(tool_calls)],
    )


def test_constants() -> None:
    assert reasoning_loops.NAME == "reasoning_loops_per_1k"
    assert reasoning_loops.DEFAULT_THRESHOLD == 12.0
    assert reasoning_loops.DIRECTION == "below"


def test_zero_loops_in_clean_message() -> None:
    res = reasoning_loops.compute(_session(msg="Implementation done; tests pass."))
    assert res.value == 0.0
    assert res.passed is True


def test_detects_oh_wait() -> None:
    res = reasoning_loops.compute(_session(msg="oh wait, that was wrong", tool_calls=1))
    assert res.value > 0


def test_detects_actually_phrase() -> None:
    res = reasoning_loops.compute(
        _session(msg="actually, let me reconsider that approach", tool_calls=1)
    )
    assert res.value > 0


def test_per_1k_normalisation() -> None:
    # 1 phrase, 1 tool_call → per_1k=1000
    res = reasoning_loops.compute(_session(msg="oh wait, never mind", tool_calls=1))
    assert res.value == pytest.approx(1000.0)


def test_threshold_breach_marks_failed() -> None:
    res = reasoning_loops.compute(
        _session(msg="oh wait, hmm, actually, on second thought", tool_calls=2)
    )
    assert res.passed is False


def test_threshold_none_yields_none_passed() -> None:
    res = reasoning_loops.compute(
        _session(msg="oh wait, never mind", tool_calls=1), threshold=None
    )
    assert res.passed is None


def test_zero_tool_calls_does_not_divide_by_zero() -> None:
    s = Session(
        id="x",
        source="claude-code",
        messages=[Message(role="assistant", content="oh wait, hmm")],
    )
    res = reasoning_loops.compute(s)
    assert res.value > 0  # divides by max(1, n_calls)


def test_case_insensitive_detection() -> None:
    res = reasoning_loops.compute(_session(msg="OH WAIT, that was lazy", tool_calls=1))
    assert res.value > 0
