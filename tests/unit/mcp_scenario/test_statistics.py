"""Unit tests for MCPScenario statistics (ADR-021)."""

from __future__ import annotations

from AgentGuard.mcp_scenario.statistics import (
    calculate_expected_met,
    calculate_tool_hit_rate,
    required_params_match,
    summary_stats,
)
from AgentGuard.mcp_scenario.types import ExpectedToolCall, ToolCallRecord


def _rec(name: str, *, success: bool = True, args: dict | None = None) -> ToolCallRecord:
    return ToolCallRecord(tool_name=name, arguments=args or {}, success=success)


def test_hit_rate_empty_expectations() -> None:
    assert calculate_tool_hit_rate([], []) == 1.0


def test_hit_rate_all_met() -> None:
    records = [_rec("a"), _rec("a"), _rec("b")]
    expected = [
        ExpectedToolCall(tool_name="a", min_calls=2, max_calls=3),
        ExpectedToolCall(tool_name="b", min_calls=1, max_calls=1),
    ]
    assert calculate_tool_hit_rate(records, expected) == 1.0


def test_hit_rate_under_min_calls() -> None:
    records = [_rec("a")]
    expected = [ExpectedToolCall(tool_name="a", min_calls=2)]
    assert calculate_tool_hit_rate(records, expected) == 0.0


def test_hit_rate_over_max_calls() -> None:
    records = [_rec("a")] * 5
    expected = [ExpectedToolCall(tool_name="a", min_calls=1, max_calls=2)]
    assert calculate_tool_hit_rate(records, expected) == 0.0


def test_hit_rate_required_params_mismatch() -> None:
    records = [_rec("a", args={"level": "DEBUG"})]
    expected = [ExpectedToolCall(tool_name="a", min_calls=1, required_params={"level": "INFO"})]
    assert calculate_tool_hit_rate(records, expected) == 0.0


def test_hit_rate_required_params_match() -> None:
    records = [_rec("a", args={"level": "INFO", "extra": "ok"})]
    expected = [ExpectedToolCall(tool_name="a", min_calls=1, required_params={"level": "INFO"})]
    assert calculate_tool_hit_rate(records, expected) == 1.0


def test_calculate_expected_met_ignores_params() -> None:
    records = [_rec("a", args={"level": "DEBUG"})]
    expected = [ExpectedToolCall(tool_name="a", min_calls=1, required_params={"level": "INFO"})]
    # met-count cares only about the count bounds; required_params is not a count check.
    assert calculate_expected_met(records, expected) == 1


def test_summary_stats_shape() -> None:
    records = [
        _rec("a"),
        _rec("a"),
        _rec("b", success=False),
        _rec("c"),
    ]
    s = summary_stats(records)
    assert s.total_tool_calls == 4
    assert s.successful_calls == 3
    assert s.failed_calls == 1
    assert abs(s.success_rate - 0.75) < 1e-9
    assert s.tool_call_counts == {"a": 2, "b": 1, "c": 1}
    assert s.unique_tools_called == 3


def test_required_params_match_no_calls_means_false() -> None:
    expected = ExpectedToolCall(tool_name="missing", required_params={"x": 1})
    assert required_params_match([], expected) is False


def test_required_params_match_no_required_means_true() -> None:
    expected = ExpectedToolCall(tool_name="anything")
    assert required_params_match([], expected) is True
