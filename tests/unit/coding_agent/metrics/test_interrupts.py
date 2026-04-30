"""Unit tests for ``metrics.interrupts`` — user interrupts per 1K tool calls."""

from __future__ import annotations

import pytest

try:
    from AgentGuard.coding_agent.metrics import interrupts
    from AgentGuard.coding_agent.session.types import Interrupt, Session, ToolCall
except ImportError:  # pragma: no cover — Phase 3 race
    pytest.skip("phase3: metrics.interrupts not yet implemented", allow_module_level=True)


def _session(*, n_interrupts: int, n_calls: int) -> Session:
    return Session(
        id="x",
        source="claude-code",
        tool_calls=[ToolCall(id=f"t{i}", name="Read", arguments={}) for i in range(n_calls)],
        interrupts=[Interrupt(timestamp=None) for _ in range(n_interrupts)],
    )


def test_constants() -> None:
    assert interrupts.NAME == "user_interrupts_per_1k"
    assert interrupts.DEFAULT_THRESHOLD == 2.0
    assert interrupts.DIRECTION == "below"


def test_no_interrupts_passes() -> None:
    res = interrupts.compute(_session(n_interrupts=0, n_calls=10))
    assert res.value == 0.0
    assert res.passed is True


def test_per_1k_normalisation() -> None:
    res = interrupts.compute(_session(n_interrupts=1, n_calls=1))
    assert res.value == pytest.approx(1000.0)


def test_below_threshold_passes() -> None:
    # 1 interrupt / 1000 tool calls = 1.0 per_1k → below 2.0 default
    res = interrupts.compute(_session(n_interrupts=1, n_calls=1000))
    assert res.passed is True


def test_above_threshold_fails() -> None:
    res = interrupts.compute(_session(n_interrupts=5, n_calls=1000))
    assert res.passed is False


def test_zero_calls_does_not_divide_by_zero() -> None:
    res = interrupts.compute(_session(n_interrupts=2, n_calls=0))
    assert res.value == pytest.approx(2000.0)  # 2 / max(1,0) * 1000


def test_threshold_none_passes_none() -> None:
    res = interrupts.compute(_session(n_interrupts=0, n_calls=1), threshold=None)
    assert res.passed is None


def test_details_carry_counts() -> None:
    res = interrupts.compute(_session(n_interrupts=3, n_calls=10))
    assert res.details == {"interrupts": 3, "tool_calls": 10}
