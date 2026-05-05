"""Exception hierarchy for the MCPScenario / TestHarness context (ADR-021)."""

from __future__ import annotations


class ScenarioError(Exception):
    """Base class for all MCPScenario errors."""


class ScenarioYAMLError(ScenarioError):
    """Raised when a Scenario YAML file is malformed or violates the v1 schema."""


class ScenarioRunError(ScenarioError):
    """Raised when ``Run MCP Scenario`` cannot dispatch or execute the run."""


class ScenarioResultError(ScenarioError):
    """Raised on serialisation / deserialisation failures of ``ScenarioResult``."""


__all__ = [
    "ScenarioError",
    "ScenarioResultError",
    "ScenarioRunError",
    "ScenarioYAMLError",
]
