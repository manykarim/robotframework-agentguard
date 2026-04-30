"""TestHarness / MCPScenario bounded context (ADR-021).

Drop-in replacement for ``manykarim/rf-mcp`` ``tests/e2e/`` patterns + a
generalisation that also fits Agent Skills and Coding Agents (per
``docs/ddd/MCPScenario-bounded-context.md``).

Public surface lives in :class:`AgentGuard.mcp_scenario.library.MCPScenarioKeywords`
which is composed into the top-level ``AgentGuard`` library via DynamicCore
(see ``AgentGuard.library._SUB_LIBRARIES``).
"""

from AgentGuard.mcp_scenario.exceptions import (
    ScenarioError,
    ScenarioResultError,
    ScenarioRunError,
    ScenarioYAMLError,
)
from AgentGuard.mcp_scenario.types import (
    ExpectedToolCall,
    Scenario,
    ScenarioContext,
    ScenarioResult,
    ToolCallRecord,
    ToolCallStatistics,
)

__all__ = [
    "ExpectedToolCall",
    "Scenario",
    "ScenarioContext",
    "ScenarioError",
    "ScenarioResult",
    "ScenarioResultError",
    "ScenarioRunError",
    "ScenarioYAMLError",
    "ToolCallRecord",
    "ToolCallStatistics",
]
