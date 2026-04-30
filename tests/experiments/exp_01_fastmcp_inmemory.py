"""Experiment 01: FastMCP supports in-memory client<->server binding (research §2.1, §4.4).

Assumption: FastMCP `Client(server)` can bind to an in-process FastMCP instance
without a transport, enabling deterministic unit tests with negligible overhead.
"""
import asyncio
import time
from fastmcp import FastMCP, Client


def build_server() -> FastMCP:
    server = FastMCP("exp01")

    @server.tool()
    def add(x: int, y: int) -> int:
        """Add two integers."""
        return x + y

    return server


async def run() -> tuple[bool, dict]:
    server = build_server()
    async with Client(server) as client:
        tools = await client.list_tools()
        names = [t.name for t in tools]
        # Functional check
        result = await client.call_tool("add", {"x": 2, "y": 3})
        # FastMCP returns a CallToolResult with a `.data` (or .content) attr
        value = getattr(result, "data", None)
        if value is None:
            content = getattr(result, "content", None)
            if content and len(content) > 0:
                value = getattr(content[0], "text", None)
        # Latency: 100 in-memory calls
        t0 = time.perf_counter()
        for _ in range(100):
            await client.call_tool("add", {"x": 1, "y": 1})
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        per_call_ms = elapsed_ms / 100.0
    ok = ("add" in names) and (str(value) == "5")
    return ok, {
        "tools": names,
        "add_2_3": value,
        "calls": 100,
        "total_ms": round(elapsed_ms, 3),
        "per_call_ms": round(per_call_ms, 4),
    }


def main() -> int:
    ok, evidence = asyncio.run(run())
    print("PASS" if ok else "FAIL", "exp_01_fastmcp_inmemory")
    for k, v in evidence.items():
        print(f"  {k}: {v}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
