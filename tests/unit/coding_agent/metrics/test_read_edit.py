"""Unit tests for ``metrics.read_edit`` — Read:Edit ratio (#42796)."""

from __future__ import annotations

import pytest

try:
    from AgentGuard.coding_agent.metrics import read_edit
    from AgentGuard.coding_agent.session.types import Session, ToolCall
except ImportError:  # pragma: no cover — Phase 3 race
    pytest.skip("phase3: metrics.read_edit not yet implemented", allow_module_level=True)


def _session(*, reads: int, edits: int) -> Session:
    tool_calls: list[ToolCall] = []
    for i in range(reads):
        tool_calls.append(ToolCall(id=f"r{i}", name="Read", arguments={}))
    for i in range(edits):
        tool_calls.append(ToolCall(id=f"e{i}", name="Edit", arguments={}))
    return Session(id="x", source="claude-code", tool_calls=tool_calls)


def test_constants_match_research_baseline() -> None:
    assert read_edit.NAME == "read_edit_ratio"
    assert read_edit.DEFAULT_THRESHOLD == 4.0
    assert read_edit.DIRECTION == "above"


def test_ratio_for_balanced_session() -> None:
    res = read_edit.compute(_session(reads=8, edits=2))
    assert res.value == pytest.approx(4.0)


def test_passes_when_above_threshold() -> None:
    res = read_edit.compute(_session(reads=10, edits=2))  # ratio=5
    assert res.passed is True


def test_fails_when_below_threshold() -> None:
    res = read_edit.compute(_session(reads=4, edits=2))  # ratio=2
    assert res.passed is False


def test_no_edits_returns_inf_when_reads_present() -> None:
    res = read_edit.compute(_session(reads=3, edits=0))
    assert res.value == float("inf")
    assert res.passed is True  # inf >= any threshold


def test_no_calls_returns_zero() -> None:
    res = read_edit.compute(_session(reads=0, edits=0))
    assert res.value == 0.0


def test_threshold_none_passes_none() -> None:
    res = read_edit.compute(_session(reads=2, edits=2), threshold=None)
    assert res.passed is None


def test_write_counts_as_edit_for_ratio() -> None:
    s = Session(
        id="x",
        source="claude-code",
        tool_calls=[
            ToolCall(id="r1", name="Read", arguments={}),
            ToolCall(id="w1", name="Write", arguments={}),
        ],
    )
    res = read_edit.compute(s)
    assert res.value == pytest.approx(1.0)


def test_details_carry_counts() -> None:
    res = read_edit.compute(_session(reads=3, edits=2))
    assert res.details == {"reads": 3, "edits": 2}


def test_unit_is_ratio() -> None:
    res = read_edit.compute(_session(reads=1, edits=1))
    assert res.unit == "ratio"
