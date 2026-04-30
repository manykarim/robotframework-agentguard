"""Unit tests for ``AgentGuard.hooks.loop_detect`` — Stop-hook loop detection."""

from __future__ import annotations

import pytest

from AgentGuard.hooks.exceptions import HookLoopDetected
from AgentGuard.hooks.loop_detect import detect_stop_loop
from AgentGuard.hooks.types import HookDecision, HookResult


def _result(*, decision: str = "allow", stop_active: bool = False) -> HookResult:
    raw = {"_stop_hook_active": stop_active}
    dec = HookDecision(decision=decision, raw=raw)
    return HookResult(
        handler="x",
        handler_type="command",
        exit_code=2 if decision == "block" else 0,
        stdout="",
        stderr="",
        decision=dec,
    )


def test_no_loop_when_results_empty() -> None:
    assert detect_stop_loop([], window=3) is False


def test_no_loop_when_below_window_threshold() -> None:
    results = [_result(decision="block", stop_active=True)] * 2
    assert detect_stop_loop(results, window=3) is False


def test_loop_detected_at_threshold() -> None:
    results = [_result(decision="block", stop_active=True)] * 5
    assert detect_stop_loop(results, window=5) is True


def test_loop_detected_with_extra_after() -> None:
    results = [_result(decision="block", stop_active=True)] * 5 + [_result(decision="allow")]
    assert detect_stop_loop(results, window=5) is True


def test_no_loop_when_stop_active_false() -> None:
    results = [_result(decision="block", stop_active=False)] * 5
    assert detect_stop_loop(results, window=5) is False


def test_no_loop_when_decision_allow() -> None:
    results = [_result(decision="allow", stop_active=True)] * 5
    assert detect_stop_loop(results, window=5) is False


def test_consecutive_resets_on_break() -> None:
    """A non-blocking entry mid-stream resets the consecutive counter."""
    results = [
        _result(decision="block", stop_active=True),
        _result(decision="block", stop_active=True),
        _result(decision="allow"),
        _result(decision="block", stop_active=True),
        _result(decision="block", stop_active=True),
    ]
    assert detect_stop_loop(results, window=3) is False


def test_raise_on_detect_raises_loop_detected() -> None:
    results = [_result(decision="block", stop_active=True)] * 4
    with pytest.raises(HookLoopDetected, match="Stop-hook loop"):
        detect_stop_loop(results, window=4, raise_on_detect=True)


def test_invalid_window_raises() -> None:
    with pytest.raises(ValueError, match="window must be"):
        detect_stop_loop([], window=0)


def test_window_one_detects_first_block() -> None:
    results = [_result(decision="block", stop_active=True)]
    assert detect_stop_loop(results, window=1) is True
