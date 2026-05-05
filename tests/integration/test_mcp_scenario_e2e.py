"""Integration — full TestHarness flow against the in-memory FastMCP echo server.

Manual driver path. The LocalDriver path with a real LLM is exercised separately
in ``test_mcp_scenario_live.py`` (gated by ``OPENROUTER_API_KEY``).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests" / "fixtures" / "mcp"))

from echo_server import mcp as echo_server  # noqa: E402  type: ignore[import-not-found]

from AgentGuard.mcp.library import MCPKeywords  # noqa: E402
from AgentGuard.mcp_scenario.library import MCPScenarioKeywords  # noqa: E402


@pytest.fixture
def harness() -> tuple[MCPKeywords, MCPScenarioKeywords]:
    return MCPKeywords(), MCPScenarioKeywords()


def test_manual_scenario_against_echo_server(
    harness: tuple[MCPKeywords, MCPScenarioKeywords],
) -> None:
    mcp, scn = harness
    handle = mcp.connect_to_mcp_server(echo_server, transport="memory")
    try:
        # Build the scenario inline — pure RF API, no YAML.
        scenario = scn.create_scenario(
            id="echo_smoke",
            prompt="(unused for manual driver)",
            expected_outcome="add returns 5; echo round-trips text",
            context="api",
            min_tool_hit_rate=0.99,
        )
        scn.add_expected_tool(scenario, "add", min_calls=1, max_calls=2)
        scn.add_expected_tool(scenario, "echo", min_calls=1, max_calls=2)

        session = scn.start_tracked_mcp_session(handle)
        scn.call_tracked_tool(session, "add", {"x": 2, "y": 3})
        scn.call_tracked_tool(session, "echo", {"text": "hello"})
        scn.end_tracked_mcp_session(session)

        result = scn.compute_scenario_result(scenario, session)
        assert result.scenario_id == "echo_smoke"
        assert result.tool_hit_rate == 1.0
        assert result.success is True
        assert result.total_tool_calls == 2
        assert result.expected_tool_calls_met == 2
        scn.scenario_result_should_be_successful(result)
        scn.tool_hit_rate(result, assertion_operator=">=", assertion_expected=0.5)
        scn.failed_tool_call_count(result, assertion_operator="<=", assertion_expected=0)
    finally:
        mcp.stop_mcp_server(handle)


def test_failed_tool_count_records_correctly(
    harness: tuple[MCPKeywords, MCPScenarioKeywords],
) -> None:
    mcp, scn = harness
    handle = mcp.connect_to_mcp_server(echo_server, transport="memory")
    try:
        scenario = scn.create_scenario(
            id="echo_with_bad_call",
            prompt="—",
            expected_outcome="—",
            min_tool_hit_rate=0.0,
        )
        session = scn.start_tracked_mcp_session(handle)
        # Successful call.
        scn.call_tracked_tool(session, "add", {"x": 1, "y": 1})
        # Provoke a transport-level error by calling a tool that does not exist.
        with pytest.raises(Exception):
            scn.call_tracked_tool(session, "nonexistent_tool", {})
        scn.end_tracked_mcp_session(session)

        result = scn.compute_scenario_result(scenario, session)
        assert result.total_tool_calls == 2
        # Both records are present; one is success=False with an error message.
        failed = [r for r in result.tool_calls if not r.success]
        assert len(failed) == 1
        assert failed[0].tool_name == "nonexistent_tool"
        assert failed[0].error
    finally:
        mcp.stop_mcp_server(handle)


def test_save_and_load_scenario_result_drop_in_rf_mcp_shape(
    tmp_path: Path,
    harness: tuple[MCPKeywords, MCPScenarioKeywords],
) -> None:
    """Verify the persisted JSON has rf-mcp's shape (drop-in compatible)."""
    import json

    mcp, scn = harness
    handle = mcp.connect_to_mcp_server(echo_server, transport="memory")
    try:
        scenario = scn.create_scenario(
            id="echo_persist",
            prompt="—",
            expected_outcome="—",
            min_tool_hit_rate=0.5,
        )
        scn.add_expected_tool(scenario, "add", min_calls=1, max_calls=1)
        session = scn.start_tracked_mcp_session(handle)
        scn.call_tracked_tool(session, "add", {"x": 1, "y": 1})
        scn.end_tracked_mcp_session(session)
        result = scn.compute_scenario_result(scenario, session)

        out = scn.save_scenario_result(result, tmp_path / "echo_persist.json")
        payload = json.loads(out.read_text(encoding="utf-8"))
        # rf-mcp v1 fields must be present.
        for key in (
            "scenario_id",
            "success",
            "tool_calls",
            "tool_hit_rate",
            "total_tool_calls",
            "expected_tool_calls_met",
            "expected_tool_calls_total",
            "errors",
            "execution_time_seconds",
            "agent_output",
            "metadata",
        ):
            assert key in payload, f"missing {key!r} in persisted ScenarioResult"
        # Round-trip back via the loader.
        reloaded = scn.load_scenario_result(out)
        assert reloaded.scenario_id == "echo_persist"
    finally:
        mcp.stop_mcp_server(handle)
