"""Unit tests for ``metrics.simplest_word`` — frequency of "simplest" per 1K calls."""

from __future__ import annotations

import pytest

try:
    from AgentGuard.coding_agent.metrics import simplest_word
    from AgentGuard.coding_agent.session.types import Message, Session, ToolCall
except ImportError:  # pragma: no cover — Phase 3 race
    pytest.skip("phase3: metrics.simplest_word not yet implemented", allow_module_level=True)


def _session(*, msg: str, tool_calls: int = 1) -> Session:
    return Session(
        id="x",
        source="claude-code",
        messages=[Message(role="assistant", content=msg)],
        tool_calls=[ToolCall(id=f"t{i}", name="Read", arguments={}) for i in range(tool_calls)],
    )


def test_constants() -> None:
    assert simplest_word.NAME == "simplest_word_per_1k"
    assert simplest_word.DEFAULT_THRESHOLD == 5.0
    assert simplest_word.DIRECTION == "below"


def test_no_simplest_returns_zero() -> None:
    res = simplest_word.compute(_session(msg="this is a complete solution"))
    assert res.value == 0.0


def test_detects_word() -> None:
    res = simplest_word.compute(_session(msg="the simplest fix is", tool_calls=1))
    assert res.value == pytest.approx(1000.0)


def test_case_insensitive() -> None:
    res = simplest_word.compute(_session(msg="SIMPLEST approach", tool_calls=1))
    assert res.value > 0


def test_word_boundary_only() -> None:
    # "supersimplest" should not match — \b enforces boundary
    res = simplest_word.compute(_session(msg="supersimpleststring", tool_calls=1))
    assert res.value == 0.0


def test_above_threshold_fails() -> None:
    # 5 occurrences / 100 calls = 50 per_1k
    msg = "simplest. simplest. simplest. simplest. simplest."
    res = simplest_word.compute(_session(msg=msg, tool_calls=100))
    assert res.passed is False


def test_threshold_none_yields_none_passed() -> None:
    res = simplest_word.compute(_session(msg="simplest"), threshold=None)
    assert res.passed is None
