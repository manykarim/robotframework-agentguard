"""MCP bounded context — Robot keywords for testing MCP servers.

Public surface:

    from AgentGuard.mcp.library import MCPKeywords

ADR-002 (transports), ADR-004 (AST tool-call matching upstream of this module).
The keyword facades are sync; async is encapsulated via `asyncio.run` per call.
"""

from __future__ import annotations

from AgentGuard.mcp.exceptions import (
    MCPCapabilityError,
    MCPConnectionError,
    MCPError,
    MCPInspectorError,
    MCPSchemaError,
    MCPToolError,
    MCPTransportError,
)
from AgentGuard.mcp.server_handle import ServerHandle
from AgentGuard.mcp.transports import (
    AUTO,
    HTTP,
    MEMORY,
    SSE,
    STDIO,
    infer_transport,
)

__all__ = [
    "AUTO",
    "HTTP",
    "MEMORY",
    "MCPCapabilityError",
    "MCPConnectionError",
    "MCPError",
    "MCPInspectorError",
    "MCPSchemaError",
    "MCPToolError",
    "MCPTransportError",
    "SSE",
    "STDIO",
    "ServerHandle",
    "infer_transport",
]
