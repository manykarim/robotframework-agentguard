"""Scenario runner — dispatch a Scenario to a driver, record + aggregate (ADR-021).

Two paths today:

* ``driver="manual"`` — caller is expected to have called
  :func:`Start Tracked MCP Session` and then driven the tool calls
  themselves (via :func:`Call Tracked Tool`). The runner just gathers the
  recorded calls + scenario expectations into a :class:`ScenarioResult`. This
  is the **offline / deterministic** path — no LLM required.

* ``driver="local"`` — uses :class:`AgentGuard.coding_agent.drivers.local.LocalDriver`
  with the new ``mcp_server`` parameter so every tool call the synthetic
  ReAct loop emits is dispatched to the wrapped MCP server and auto-tracked.
  Requires ``OPENROUTER_API_KEY``.

Other drivers (``claude-code``, ``codex``, ``aider``) are reserved for
Phase 4-B once the ``--mcp-config`` injection lands.
"""

from __future__ import annotations

from typing import Any

from AgentGuard.mcp_scenario.exceptions import ScenarioRunError
from AgentGuard.mcp_scenario.statistics import (
    calculate_expected_met,
    calculate_tool_hit_rate,
)
from AgentGuard.mcp_scenario.tracker import TrackedMCPSession
from AgentGuard.mcp_scenario.types import Scenario, ScenarioResult


def run_manual_scenario(scenario: Scenario, session: TrackedMCPSession) -> ScenarioResult:
    """Build a :class:`ScenarioResult` from a session the caller already drove.

    Used by the offline test pattern where the test author makes explicit
    ``Call Tracked Tool`` invocations and then computes the result.
    """
    if session.ended_at is None:
        session.end()
    return _materialise_result(scenario, session, agent_output=None, metadata=None)


def run_local_scenario(
    scenario: Scenario,
    session: TrackedMCPSession,
    *,
    model: str | None = None,
    max_turns: int = 12,
    extra_metadata: dict[str, Any] | None = None,
) -> ScenarioResult:
    """Drive ``scenario.prompt`` against ``session`` via LocalDriver.

    Every tool the LLM asks for is dispatched through ``session.call_tool``
    and therefore auto-recorded. Returns a :class:`ScenarioResult`.
    """
    try:
        from AgentGuard.coding_agent.drivers.base import DriverConfig
        from AgentGuard.coding_agent.drivers.local import LocalDriver
    except ImportError as exc:  # pragma: no cover — Phase 3 should always be present
        raise ScenarioRunError("LocalDriver unavailable; install Phase-3 coding_agent") from exc

    driver = LocalDriver()
    cfg = DriverConfig(
        model=model,
        max_turns=max_turns,
        capture_jsonl=True,
        extra_args=[],
    )
    # Attach the tracked session via a private hook the LocalDriver respects
    # when it sees ``cfg.mcp_session`` set (added in Phase 4 wiring).
    setattr(cfg, "mcp_session", session)  # noqa: B010 — DriverConfig is open

    try:
        result = driver.run(scenario.prompt, cfg)
    except Exception as exc:  # noqa: BLE001
        if session.ended_at is None:
            session.end()
        raise ScenarioRunError(f"LocalDriver run failed: {exc}") from exc
    finally:
        if session.ended_at is None:
            session.end()

    metadata: dict[str, Any] = {
        "driver": "local",
        "model": model or cfg.model or "openrouter/openai/gpt-4o-mini",
        "duration_ms": result.duration_ms,
        "cost_usd": result.cost_usd,
        "jsonl_path": result.jsonl_path,
    }
    if extra_metadata:
        metadata.update(extra_metadata)

    agent_output = ""
    if result.session is not None and result.session.messages:
        last = result.session.messages[-1]
        agent_output = last.content if isinstance(last.content, str) else str(last.content)

    return _materialise_result(scenario, session, agent_output=agent_output, metadata=metadata)


def _materialise_result(
    scenario: Scenario,
    session: TrackedMCPSession,
    *,
    agent_output: str | None,
    metadata: dict[str, Any] | None,
) -> ScenarioResult:
    """Pure aggregation step shared by manual + driver-orchestrated paths."""
    records = list(session.records)
    hit_rate = calculate_tool_hit_rate(records, scenario.expected_tools)
    met_count = calculate_expected_met(records, scenario.expected_tools)
    errors = [r.error for r in records if r.error]
    success = hit_rate >= scenario.min_tool_hit_rate and not errors
    return ScenarioResult(
        scenario_id=scenario.id,
        success=success,
        tool_calls=records,
        tool_hit_rate=hit_rate,
        total_tool_calls=len(records),
        expected_tool_calls_met=met_count,
        expected_tool_calls_total=len(scenario.expected_tools),
        errors=errors,
        execution_time_seconds=session.execution_time_seconds(),
        agent_output=agent_output,
        metadata=metadata or {},
    )


__all__ = [
    "run_local_scenario",
    "run_manual_scenario",
]
