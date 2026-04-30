"""Unit tests for ``metrics.write_ratio`` — Write/(Write+Edit) mutation share."""

from __future__ import annotations

import pytest

try:
    from AgentGuard.coding_agent.metrics import write_ratio
    from AgentGuard.coding_agent.session.types import Session, ToolCall
except ImportError:  # pragma: no cover — Phase 3 race
    pytest.skip("phase3: metrics.write_ratio not yet implemented", allow_module_level=True)


def _session(*, writes: int, edits: int) -> Session:
    tcs = []
    for i in range(writes):
        tcs.append(ToolCall(id=f"w{i}", name="Write", arguments={}))
    for i in range(edits):
        tcs.append(ToolCall(id=f"e{i}", name="Edit", arguments={}))
    return Session(id="x", source="claude-code", tool_calls=tcs)


def test_constants() -> None:
    assert write_ratio.NAME == "write_mutation_ratio"
    assert write_ratio.DEFAULT_THRESHOLD == 0.06
    assert write_ratio.DIRECTION == "below"


def test_no_mutations_returns_zero() -> None:
    res = write_ratio.compute(_session(writes=0, edits=0))
    assert res.value == 0.0


def test_all_writes_returns_one() -> None:
    res = write_ratio.compute(_session(writes=5, edits=0))
    assert res.value == pytest.approx(1.0)


def test_all_edits_returns_zero() -> None:
    res = write_ratio.compute(_session(writes=0, edits=5))
    assert res.value == 0.0


def test_balanced_returns_half() -> None:
    res = write_ratio.compute(_session(writes=2, edits=2))
    assert res.value == pytest.approx(0.5)


def test_below_default_threshold_passes() -> None:
    # 1 write / 100 mutations = 0.01 < 0.06
    res = write_ratio.compute(_session(writes=1, edits=99))
    assert res.passed is True


def test_above_default_threshold_fails() -> None:
    # 1 write / 5 mutations = 0.2 > 0.06
    res = write_ratio.compute(_session(writes=1, edits=4))
    assert res.passed is False


def test_threshold_none_passes_none() -> None:
    res = write_ratio.compute(_session(writes=1, edits=1), threshold=None)
    assert res.passed is None


def test_details_carry_counts() -> None:
    res = write_ratio.compute(_session(writes=2, edits=3))
    assert res.details == {"writes": 2, "edits": 3}
