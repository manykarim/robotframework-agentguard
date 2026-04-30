"""Tests for `MCPKeywords` (ADR-002, research §6.1)."""

from __future__ import annotations

from typing import Any

import pytest

from AgentGuard.mcp.exceptions import MCPCapabilityError
from AgentGuard.mcp.library import MCPKeywords
from AgentGuard.mcp.server_handle import ServerHandle
from AgentGuard.mcp.transports import HTTP, MEMORY


@pytest.fixture
def mcp(mock_provider: Any) -> MCPKeywords:
    return MCPKeywords(provider=mock_provider)


@pytest.fixture
def echo_handle(mcp: MCPKeywords, echo_mcp_server: Any) -> ServerHandle:
    handle = ServerHandle(
        name="echo-1",
        transport=MEMORY,
        target=echo_mcp_server,
        instance=echo_mcp_server,
    )
    mcp._handles[handle.name] = handle
    return handle


class TestServerLifecycle:
    def test_connect_to_in_memory_server(self, mcp: MCPKeywords, echo_mcp_server: Any) -> None:
        handle = mcp.connect_to_mcp_server(echo_mcp_server, transport=MEMORY)
        assert handle.transport == MEMORY
        assert handle.instance is echo_mcp_server

    def test_connect_to_url_resolves_http(self, mcp: MCPKeywords) -> None:
        handle = mcp.connect_to_mcp_server("http://localhost/mcp", transport="auto")
        assert handle.transport == HTTP

    def test_stop_server_releases_handle(self, mcp: MCPKeywords, echo_mcp_server: Any) -> None:
        handle = mcp.connect_to_mcp_server(echo_mcp_server, transport=MEMORY)
        rc = mcp.stop_mcp_server(handle)
        assert rc is None or isinstance(rc, int)
        assert handle.name not in mcp._handles


class TestCapabilities:
    def test_get_mcp_capabilities_lists_tools(self, mcp: MCPKeywords, echo_handle: ServerHandle) -> None:
        caps = mcp.get_mcp_capabilities(echo_handle)
        assert "tools" in caps
        assert {"echo", "add", "slow_op"} <= set(caps["tools"])

    def test_should_implement_capabilities_passes(self, mcp: MCPKeywords, echo_handle: ServerHandle) -> None:
        mcp.mcp_server_should_implement_capabilities(echo_handle, "echo", "add")

    def test_should_implement_capabilities_fails(self, mcp: MCPKeywords, echo_handle: ServerHandle) -> None:
        with pytest.raises(MCPCapabilityError):
            mcp.mcp_server_should_implement_capabilities(echo_handle, "nonexistent")


class TestListing:
    def test_list_mcp_tools(self, mcp: MCPKeywords, echo_handle: ServerHandle) -> None:
        tools = mcp.list_mcp_tools(echo_handle)
        names = [t["name"] for t in tools]
        assert {"echo", "add", "slow_op"} <= set(names)

    def test_list_mcp_resources_empty_ok(self, mcp: MCPKeywords, echo_handle: ServerHandle) -> None:
        rs = mcp.list_mcp_resources(echo_handle)
        assert isinstance(rs, list)

    def test_list_mcp_prompts_empty_ok(self, mcp: MCPKeywords, echo_handle: ServerHandle) -> None:
        ps = mcp.list_mcp_prompts(echo_handle)
        assert isinstance(ps, list)


class TestCallMCPTool:
    def test_echo(self, mcp: MCPKeywords, echo_handle: ServerHandle) -> None:
        out = mcp.call_mcp_tool(echo_handle, "echo", {"text": "hello"})
        assert "hello" in str(out.get("data") or out.get("structured_content") or out)

    def test_add(self, mcp: MCPKeywords, echo_handle: ServerHandle) -> None:
        out = mcp.call_mcp_tool(echo_handle, "add", {"x": 2, "y": 3})
        # data may be int 5 or str "5" depending on fastmcp version
        data = out.get("data")
        assert data == 5 or str(data) == "5"

    def test_arguments_as_json_string(self, mcp: MCPKeywords, echo_handle: ServerHandle) -> None:
        out = mcp.call_mcp_tool(echo_handle, "add", '{"x":4,"y":6}')
        assert out.get("data") == 10 or str(out.get("data")) == "10"


class TestSchemaValidation:
    def test_passes_when_payload_matches(self, mcp: MCPKeywords, echo_handle: ServerHandle) -> None:
        out = mcp.call_mcp_tool(echo_handle, "add", {"x": 1, "y": 2})
        mcp.mcp_tool_output_should_match_schema(out, {"type": ["integer", "string"]})

    def test_fails_on_type_mismatch(self, mcp: MCPKeywords, echo_handle: ServerHandle) -> None:
        from AgentGuard.mcp.exceptions import MCPSchemaError

        out = mcp.call_mcp_tool(echo_handle, "echo", {"text": "hi"})
        with pytest.raises(MCPSchemaError):
            mcp.mcp_tool_output_should_match_schema(out, {"type": "integer"})


class TestLatencyMeasurement:
    def test_measures_in_memory_latency(self, mcp: MCPKeywords, echo_handle: ServerHandle) -> None:
        stats = mcp.measure_mcp_tool_latency(echo_handle, "echo", runs=5, arguments={"text": "x"})
        assert stats["runs"] == 5.0
        for k in ("mean", "p50", "p95", "p99", "min", "max"):
            assert k in stats and stats[k] >= 0.0

    def test_zero_runs_raises(self, mcp: MCPKeywords, echo_handle: ServerHandle) -> None:
        from AgentGuard.mcp.exceptions import MCPToolError

        with pytest.raises(MCPToolError):
            mcp.measure_mcp_tool_latency(echo_handle, "echo", runs=0)
