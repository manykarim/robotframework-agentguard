"""Reusable FastMCP fixture server with `add`, `echo`, `slow_op` tools.

Importable for in-memory tests:

    from tests.fixtures.mcp.echo_server import build_server
    server = build_server()
    async with Client(server) as c: ...

Runnable for stdio tests:

    uv run python tests/fixtures/mcp/echo_server.py
"""

from __future__ import annotations

import asyncio

from fastmcp import FastMCP


def build_server(name: str = "echo") -> FastMCP:
    """Construct (but do not start) a FastMCP echo server."""
    mcp = FastMCP(name)

    @mcp.tool()
    def add(x: int, y: int) -> int:
        """Add two integers and return the sum."""
        return x + y

    @mcp.tool()
    def echo(text: str) -> str:
        """Return the input text unchanged."""
        return text

    @mcp.tool()
    async def slow_op(ms: int = 100) -> str:
        """Sleep for `ms` milliseconds, then return a confirmation string.

        Used by `Measure MCP Tool Latency` smoke tests.
        """
        await asyncio.sleep(max(0, ms) / 1000.0)
        return f"slept {ms} ms"

    return mcp


# Module-level instance — convenient for `Client(echo_server.mcp)` patterns.
mcp = build_server()


def main() -> int:
    """Run the server over stdio so external tests can spawn it."""
    mcp.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
