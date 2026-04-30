"""MCP exception hierarchy — surfaced from `MCPKeywords` to Robot reports.

Keep messages short and prefix-free; Robot prints the class name automatically.
"""

from __future__ import annotations


class MCPError(Exception):
    """Base class for any MCP-module failure."""


class MCPTransportError(MCPError):
    """Could not start, infer, or wire up an MCP transport."""


class MCPConnectionError(MCPError):
    """Could not establish a client session against the requested target."""


class MCPCapabilityError(MCPError):
    """Server is missing one or more requested capabilities."""


class MCPToolError(MCPError):
    """A tool call returned `is_error=True` or raised."""


class MCPSchemaError(MCPError):
    """Tool output did not validate against the supplied JSON Schema."""


class MCPInspectorError(MCPError):
    """`npx @modelcontextprotocol/inspector --cli` failed (non-zero exit / not on PATH)."""
