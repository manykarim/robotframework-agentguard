"""Convenience façade — ``Library AgentGuard.MCP``.

PROPOSAL-library-import-structure §3: re-exports the existing keyword class
under a short PascalCase name matching this module's last segment, so
Robot Framework's class-name lookup (``getattr(module, 'MCP')``) finds it.
"""

from AgentGuard.mcp.library import MCPKeywords as MCP  # noqa: N814

__all__ = ["MCP"]
