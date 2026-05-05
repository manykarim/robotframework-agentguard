"""Direct unit tests for MCPScenarioKeywords — RF-native API surface."""

from __future__ import annotations

from pathlib import Path

import pytest

from AgentGuard.mcp_scenario.library import MCPScenarioKeywords
from AgentGuard.mcp_scenario.types import (
    ScenarioResult,
    ToolCallRecord,
    ToolCallStatistics,
)


@pytest.fixture
def kw() -> MCPScenarioKeywords:
    return MCPScenarioKeywords()


def _scenario(kw: MCPScenarioKeywords):
    sc = kw.create_scenario(
        id="demo",
        prompt="add 2 3",
        expected_outcome="returns 5",
        context="api",
    )
    kw.add_expected_tool(sc, "add", min_calls=1, max_calls=1)
    return sc


def _result_from(records: list[ToolCallRecord], hit_rate: float = 1.0) -> ScenarioResult:
    return ScenarioResult(
        scenario_id="demo",
        success=hit_rate >= 0.8,
        tool_calls=list(records),
        tool_hit_rate=hit_rate,
        total_tool_calls=len(records),
        expected_tool_calls_met=1 if records else 0,
        expected_tool_calls_total=1,
    )


def test_create_scenario_minimal(kw: MCPScenarioKeywords) -> None:
    sc = kw.create_scenario(id="x", prompt="p", expected_outcome="o")
    assert sc.id == "x"
    assert sc.expected_tools == []


def test_add_expected_tool_appends(kw: MCPScenarioKeywords) -> None:
    sc = kw.create_scenario(id="x", prompt="p", expected_outcome="o")
    kw.add_expected_tool(sc, "add")
    kw.add_expected_tool(sc, "log", min_calls=0, max_calls=3, required_params={"level": "INFO"})
    assert [e.tool_name for e in sc.expected_tools] == ["add", "log"]
    assert sc.expected_tools[1].required_params == {"level": "INFO"}


def test_save_and_load_scenario_result_round_trip(tmp_path: Path, kw: MCPScenarioKeywords) -> None:
    res = _result_from([ToolCallRecord(tool_name="add", arguments={"x": 1}, success=True)])
    out = kw.save_scenario_result(res, tmp_path / "r.json")
    assert out.exists()
    loaded = kw.load_scenario_result(out)
    assert loaded.scenario_id == "demo"
    assert loaded.tool_hit_rate == res.tool_hit_rate


def test_tool_hit_rate_from_result(kw: MCPScenarioKeywords) -> None:
    res = _result_from([ToolCallRecord(tool_name="add", arguments={}, success=True)], hit_rate=1.0)
    assert kw.tool_hit_rate(res) == 1.0


def test_tool_hit_rate_with_operator_passes(kw: MCPScenarioKeywords) -> None:
    res = _result_from([ToolCallRecord(tool_name="add", arguments={}, success=True)], hit_rate=0.9)
    # Operator form returns the value AND asserts.
    out = kw.tool_hit_rate(res, assertion_operator=">=", assertion_expected=0.8)
    assert out == 0.9


def test_tool_hit_rate_with_operator_raises(kw: MCPScenarioKeywords) -> None:
    res = _result_from([], hit_rate=0.4)
    with pytest.raises(AssertionError):
        kw.tool_hit_rate(res, assertion_operator=">=", assertion_expected=0.8)


def test_tool_call_count_total(kw: MCPScenarioKeywords) -> None:
    res = _result_from(
        [
            ToolCallRecord(tool_name="a", arguments={}, success=True),
            ToolCallRecord(tool_name="b", arguments={}, success=True),
        ]
    )
    assert kw.tool_call_count(res) == 2


def test_tool_call_count_per_name(kw: MCPScenarioKeywords) -> None:
    res = _result_from(
        [
            ToolCallRecord(tool_name="a", arguments={}, success=True),
            ToolCallRecord(tool_name="a", arguments={}, success=True),
            ToolCallRecord(tool_name="b", arguments={}, success=True),
        ]
    )
    assert kw.tool_call_count(res, name="a") == 2
    assert kw.tool_call_count(res, name="b") == 1
    assert kw.tool_call_count(res, name="c") == 0


def test_tool_call_count_with_operator_ge_passes(kw: MCPScenarioKeywords) -> None:
    res = _result_from([ToolCallRecord(tool_name="x", arguments={}, success=True)] * 4)
    out = kw.tool_call_count(res, assertion_operator=">=", assertion_expected=1)
    assert out == 4


def test_tool_call_count_with_operator_ge_raises_on_low(kw: MCPScenarioKeywords) -> None:
    res = _result_from([ToolCallRecord(tool_name="x", arguments={}, success=True)])
    with pytest.raises(AssertionError):
        kw.tool_call_count(res, assertion_operator=">=", assertion_expected=5)


def test_tool_call_count_with_operator_le_raises_on_high(kw: MCPScenarioKeywords) -> None:
    res = _result_from([ToolCallRecord(tool_name="x", arguments={}, success=True)] * 10)
    with pytest.raises(AssertionError):
        kw.tool_call_count(res, assertion_operator="<=", assertion_expected=3)


def test_failed_tool_call_count_with_operator_passes(kw: MCPScenarioKeywords) -> None:
    res = _result_from([ToolCallRecord(tool_name="a", arguments={}, success=True)])
    out = kw.failed_tool_call_count(res, assertion_operator="<=", assertion_expected=0)
    assert out == 0


def test_failed_tool_call_count_with_operator_raises(kw: MCPScenarioKeywords) -> None:
    res = _result_from([ToolCallRecord(tool_name="a", arguments={}, success=False, error="boom")] * 3)
    with pytest.raises(AssertionError):
        kw.failed_tool_call_count(res, assertion_operator="<=", assertion_expected=1)


def test_failed_tool_call_count_passthrough_returns_int(kw: MCPScenarioKeywords) -> None:
    res = _result_from(
        [
            ToolCallRecord(tool_name="a", arguments={}, success=True),
            ToolCallRecord(tool_name="a", arguments={}, success=False, error="boom"),
        ]
    )
    assert kw.failed_tool_call_count(res) == 1


def test_required_tool_should_have_been_called_with_params_passes(kw: MCPScenarioKeywords) -> None:
    res = _result_from([ToolCallRecord(tool_name="log", arguments={"level": "INFO", "x": 1}, success=True)])
    kw.required_tool_should_have_been_called_with_params(res, "log", {"level": "INFO"})


def test_required_tool_should_have_been_called_with_params_raises(kw: MCPScenarioKeywords) -> None:
    res = _result_from([ToolCallRecord(tool_name="log", arguments={"level": "DEBUG"}, success=True)])
    with pytest.raises(AssertionError, match="required_params"):
        kw.required_tool_should_have_been_called_with_params(res, "log", {"level": "INFO"})


def test_scenario_result_should_be_successful_passes(kw: MCPScenarioKeywords) -> None:
    res = _result_from([ToolCallRecord(tool_name="a", arguments={}, success=True)], hit_rate=1.0)
    kw.scenario_result_should_be_successful(res)


def test_scenario_result_should_be_successful_raises(kw: MCPScenarioKeywords) -> None:
    res = _result_from([], hit_rate=0.0)
    with pytest.raises(AssertionError, match="failed"):
        kw.scenario_result_should_be_successful(res)


def test_tool_call_statistics_returns_dataclass(kw: MCPScenarioKeywords) -> None:
    res = _result_from(
        [
            ToolCallRecord(tool_name="a", arguments={}, success=True),
            ToolCallRecord(tool_name="a", arguments={}, success=False, error="x"),
        ]
    )
    stats = kw.tool_call_statistics(res)
    assert isinstance(stats, ToolCallStatistics)
    assert stats.total_tool_calls == 2
    assert stats.failed_calls == 1
    assert stats.tool_call_counts == {"a": 2}


def test_tool_call_success_rate_with_operator_passes(kw: MCPScenarioKeywords) -> None:
    res = _result_from(
        [
            ToolCallRecord(tool_name="a", arguments={}, success=True),
            ToolCallRecord(tool_name="b", arguments={}, success=True),
        ]
    )
    out = kw.tool_call_success_rate(res, assertion_operator=">=", assertion_expected=0.9)
    assert out == 1.0


def test_tool_call_success_rate_with_operator_raises(kw: MCPScenarioKeywords) -> None:
    res = _result_from(
        [
            ToolCallRecord(tool_name="a", arguments={}, success=True),
            ToolCallRecord(tool_name="b", arguments={}, success=False, error="x"),
        ]
    )
    with pytest.raises(AssertionError):
        kw.tool_call_success_rate(res, assertion_operator=">=", assertion_expected=0.9)


def test_compare_scenarios_pass_rate(kw: MCPScenarioKeywords) -> None:
    results = [
        _result_from([ToolCallRecord(tool_name="a", arguments={}, success=True)], hit_rate=1.0),
        _result_from([ToolCallRecord(tool_name="a", arguments={}, success=True)], hit_rate=1.0),
        _result_from([], hit_rate=0.0),
    ]
    score = kw.compare_scenarios_pass_rate(results, k=1)
    assert 0.0 <= score <= 1.0


def test_run_mcp_scenario_manual_path(kw: MCPScenarioKeywords) -> None:
    sc = _scenario(kw)
    # Build a session manually with one good `add` call so hit rate = 1.
    session = type("FakeSess", (), {})()
    session.records = [ToolCallRecord(tool_name="add", arguments={"x": 2, "y": 3}, success=True)]
    session.started_at = 1.0
    session.ended_at = 2.0
    session.execution_time_seconds = lambda: 1.0  # noqa: E731
    session.end = lambda: None  # noqa: E731
    res = kw.run_mcp_scenario(sc, session=session, driver="manual")
    assert res.tool_hit_rate == 1.0
    assert res.success is True


def test_run_mcp_scenario_unknown_driver_raises(kw: MCPScenarioKeywords) -> None:
    sc = _scenario(kw)
    with pytest.raises(ValueError, match="unknown driver"):
        kw.run_mcp_scenario(sc, driver="bogus")


def test_run_mcp_scenario_manual_requires_session(kw: MCPScenarioKeywords) -> None:
    sc = _scenario(kw)
    with pytest.raises(ValueError, match="requires session"):
        kw.run_mcp_scenario(sc, driver="manual")
