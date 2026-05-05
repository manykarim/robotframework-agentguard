"""Hidden 'real' implementation, named verbosely as today's existing classes."""

from __future__ import annotations

from typing import Any

from robot.api.deco import keyword


class MCPKeywords:
    """Original verbose name (mirrors current AgentGuard.mcp.library.MCPKeywords)."""

    ROBOT_LIBRARY_SCOPE = "SUITE"

    def __init__(self, provider: Any = None) -> None:
        self._provider = provider

    @keyword(name="MCP Hello")
    def mcp_hello(self) -> str:
        return f"name-attr-on-class={type(self).__name__}"
