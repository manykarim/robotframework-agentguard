"""Unit tests for ``metrics.stop_hook`` — Stop hook block-decision counter."""

from __future__ import annotations

import pytest

try:
    from AgentGuard.coding_agent.metrics import stop_hook
    from AgentGuard.coding_agent.session.types import HookEvent, Session
except ImportError:  # pragma: no cover — Phase 3 race
    pytest.skip("phase3: metrics.stop_hook not yet implemented", allow_module_level=True)


def _session(events: list[HookEvent]) -> Session:
    return Session(id="x", source="claude-code", hook_events=events)


def test_constants() -> None:
    assert stop_hook.NAME == "stop_hook_violations"
    assert stop_hook.DEFAULT_THRESHOLD == 0.0
    assert stop_hook.DIRECTION == "below"


def test_no_events_passes() -> None:
    res = stop_hook.compute(_session([]))
    assert res.value == 0.0
    assert res.passed is True


def test_stop_with_block_counts() -> None:
    res = stop_hook.compute(_session([HookEvent(event="Stop", decision="block")]))
    assert res.value == 1.0
    assert res.passed is False


def test_stop_with_allow_does_not_count() -> None:
    res = stop_hook.compute(_session([HookEvent(event="Stop", decision="allow")]))
    assert res.value == 0.0
    assert res.passed is True


def test_non_stop_events_ignored() -> None:
    res = stop_hook.compute(_session([HookEvent(event="PreToolUse", decision="block")]))
    assert res.value == 0.0


def test_multiple_stop_blocks_accumulate() -> None:
    res = stop_hook.compute(_session([HookEvent(event="Stop", decision="block")] * 3))
    assert res.value == 3.0
    assert res.passed is False


def test_threshold_none_passes_none() -> None:
    res = stop_hook.compute(_session([]), threshold=None)
    assert res.passed is None


def test_details_carry_event_counts() -> None:
    res = stop_hook.compute(
        _session(
            [
                HookEvent(event="Stop", decision="block"),
                HookEvent(event="PreToolUse", decision="allow"),
            ]
        )
    )
    assert res.details == {"violations": 1, "hook_events": 2}
