"""Tests for MCP transport selection (ADR-002).

`AgentGuard.mcp.transports` exposes:
- constants: AUTO, MEMORY, STDIO, HTTP, SSE
- `infer_transport(target)`
- `normalize_transport(transport, target)`
- `make_client(handle)` (lazy fastmcp import)
"""

from __future__ import annotations

import pytest

from AgentGuard.mcp.exceptions import MCPTransportError
from AgentGuard.mcp.server_handle import ServerHandle
from AgentGuard.mcp.transports import (
    AUTO,
    HTTP,
    MEMORY,
    SSE,
    STDIO,
    infer_transport,
    make_client,
    normalize_transport,
)


class TestInferTransport:
    def test_fastmcp_instance_resolves_memory(self, echo_mcp_server) -> None:
        assert infer_transport(echo_mcp_server) == MEMORY

    def test_http_url(self) -> None:
        assert infer_transport("http://localhost:8765/mcp") == HTTP

    def test_https_url(self) -> None:
        assert infer_transport("https://example.com/mcp") == HTTP

    def test_sse_url_emits_deprecation(self) -> None:
        with pytest.warns(DeprecationWarning):
            assert infer_transport("http://localhost:8765/sse") == SSE

    def test_command_string_resolves_stdio(self) -> None:
        assert infer_transport("uv run python my_server.py") == STDIO

    def test_none_target_raises(self) -> None:
        with pytest.raises(MCPTransportError):
            infer_transport(None)

    def test_empty_string_raises(self) -> None:
        with pytest.raises(MCPTransportError):
            infer_transport("   ")


class TestNormalizeTransport:
    def test_auto_resolves(self, echo_mcp_server) -> None:
        assert normalize_transport(AUTO, echo_mcp_server) == MEMORY
        assert normalize_transport(AUTO, "uv run mcp") == STDIO

    def test_explicit_returns_lower(self) -> None:
        assert normalize_transport("MEMORY", "ignored") == MEMORY
        assert normalize_transport("Stdio", "uv run") == STDIO
        assert normalize_transport("http", "http://x") == HTTP

    def test_unknown_transport_raises(self) -> None:
        with pytest.raises(MCPTransportError):
            normalize_transport("carrier-pigeon", "x")

    def test_explicit_sse_emits_deprecation(self) -> None:
        with pytest.warns(DeprecationWarning):
            assert normalize_transport("sse", "http://x/sse") == SSE


class TestMakeClient:
    def test_memory_requires_instance(self) -> None:
        handle = ServerHandle(name="x", transport=MEMORY, target="cmd", instance=None)
        with pytest.raises(MCPTransportError):
            make_client(handle, transport=MEMORY)

    def test_memory_with_instance(self, echo_mcp_server) -> None:
        handle = ServerHandle(name="x", transport=MEMORY, target=echo_mcp_server, instance=echo_mcp_server)
        client = make_client(handle, transport=MEMORY)
        # fastmcp.Client object should be returned (don't open the connection here)
        assert client is not None

    def test_stdio_requires_string_target(self) -> None:
        handle = ServerHandle(name="x", transport=STDIO, target=12345)
        with pytest.raises(MCPTransportError):
            make_client(handle, transport=STDIO)

    def test_stdio_invalid_command_raises(self) -> None:
        handle = ServerHandle(name="x", transport=STDIO, target='broken " quote')
        with pytest.raises(MCPTransportError):
            make_client(handle, transport=STDIO)

    def test_http_with_url(self) -> None:
        handle = ServerHandle(name="x", transport=HTTP, target="http://localhost/mcp")
        client = make_client(handle, transport=HTTP)
        assert client is not None

    def test_http_requires_url_string(self) -> None:
        handle = ServerHandle(name="x", transport=HTTP, target=12345)
        with pytest.raises(MCPTransportError):
            make_client(handle, transport=HTTP)
