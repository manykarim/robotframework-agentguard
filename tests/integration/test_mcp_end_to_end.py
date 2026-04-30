"""Integration — exercise the MCP module against the in-memory echo server."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests" / "fixtures" / "mcp"))

from echo_server import mcp as echo_server  # type: ignore[import-not-found]  # noqa: E402

from AgentGuard.mcp.library import MCPKeywords  # noqa: E402


@pytest.fixture
def kw() -> MCPKeywords:
    return MCPKeywords()


def test_connect_list_call_in_memory(kw: MCPKeywords) -> None:
    handle = kw.connect_to_mcp_server(echo_server, transport="memory")
    try:
        tools = kw.list_mcp_tools(handle)
        names = {t["name"] for t in tools}
        assert {"add", "echo", "slow_op"}.issubset(names)
        result = kw.call_mcp_tool(handle, "add", {"x": 5, "y": 3})
        assert result["data"] == 8
        echoed = kw.call_mcp_tool(handle, "echo", {"text": "hi"})
        assert echoed["data"] == "hi"
    finally:
        kw.stop_mcp_server(handle)


def test_capabilities_returns_dict(kw: MCPKeywords) -> None:
    handle = kw.connect_to_mcp_server(echo_server, transport="memory")
    try:
        caps = kw.get_mcp_capabilities(handle)
        assert isinstance(caps, dict)
    finally:
        kw.stop_mcp_server(handle)


def test_measure_latency_within_budget(kw: MCPKeywords) -> None:
    handle = kw.connect_to_mcp_server(echo_server, transport="memory")
    try:
        stats = kw.measure_mcp_tool_latency(handle, "add", runs=20, arguments={"x": 1, "y": 2})
        assert stats["p50"] < 50, stats
        assert stats["mean"] < 50, stats
    finally:
        kw.stop_mcp_server(handle)
