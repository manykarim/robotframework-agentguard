"""Façade — alias the verbose class to a short module-matching name.

This is the ACTUAL pattern AgentGuard would use: existing keyword classes
keep their internal names (`MCPKeywords`), and the façade module aliases
them to short module-matching names (`MCP`) for the user-facing import.
"""

from tests.experiments.exp_13c._real import MCPKeywords as MCP

__all__ = ["MCP"]
