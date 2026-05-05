"""Façade module — module name `MCP` matches the class name `MCP`.

This proves the canonical pattern for ``Library AgentGuard.MCP``: a
PascalCase Python module that re-exports the existing keyword class with
the same name as the module's last segment.
"""

from __future__ import annotations

from typing import Any

from robot.api.deco import keyword


class MCP:
    """Stand-in for the real MCPKeywords class. RF finds this implicitly
    when ``Library tests.experiments.exp_13b.MCP`` is used — class name
    equals module last segment."""

    ROBOT_LIBRARY_SCOPE = "SUITE"

    def __init__(self, provider: Any = None) -> None:
        self._provider = provider

    @keyword(name="MCP Hello")
    def mcp_hello(self) -> str:
        return "MCP-facade-works"
