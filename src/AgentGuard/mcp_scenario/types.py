"""Canonical types for the TestHarness / MCPScenario context (ADR-021).

Field shapes are byte-equivalent to ``manykarim/rf-mcp/tests/e2e/models.py``
(rf-mcp v1 schema) so YAMLs and JSON artifacts round-trip without translation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal

ScenarioContext = Literal["web", "api", "mobile", "desktop", "generic"]


@dataclass
class ExpectedToolCall:
    """Aggregate-counting expectation for a single tool name in a scenario.

    Distinct from :class:`AgentGuard.tool_calls.types.ExpectedCall` (BFCL) which
    asserts on a *single* call's AST. Here we assert: "this tool was invoked
    between ``min_calls`` and ``max_calls`` times, and every invocation
    included these required parameters".
    """

    tool_name: str
    min_calls: int = 1
    max_calls: int | None = None
    required_params: dict[str, Any] | None = None


@dataclass
class Scenario:
    """Declarative description of a multi-step agent task.

    Identical field set to rf-mcp ``models.Scenario``.
    """

    id: str
    name: str
    description: str
    prompt: str
    expected_outcome: str
    context: ScenarioContext = "generic"
    expected_tools: list[ExpectedToolCall] = field(default_factory=list)
    min_tool_hit_rate: float = 0.8
    tags: list[str] = field(default_factory=list)


@dataclass
class ToolCallRecord:
    """Immutable record of a single tool invocation captured during a run."""

    tool_name: str
    arguments: dict[str, Any]
    success: bool
    result: dict[str, Any] | None = None
    error: str | None = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class ToolCallStatistics:
    """Summary stats over a list of :class:`ToolCallRecord`.

    Mirrors rf-mcp ``MetricsCollector.get_summary_stats`` shape.
    """

    total_tool_calls: int
    successful_calls: int
    failed_calls: int
    success_rate: float
    tool_call_counts: dict[str, int]
    unique_tools_called: int


@dataclass
class ScenarioResult:
    """Persisted artifact of a single scenario run.

    Field set is byte-equivalent to rf-mcp ``models.ScenarioResult``; AgentGuard
    additions live under ``metadata`` (open dict) so JSONs round-trip cleanly.
    """

    scenario_id: str
    success: bool
    tool_calls: list[ToolCallRecord]
    tool_hit_rate: float
    total_tool_calls: int
    expected_tool_calls_met: int
    expected_tool_calls_total: int
    errors: list[str] = field(default_factory=list)
    execution_time_seconds: float = 0.0
    agent_output: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "ExpectedToolCall",
    "Scenario",
    "ScenarioContext",
    "ScenarioResult",
    "ToolCallRecord",
    "ToolCallStatistics",
]
