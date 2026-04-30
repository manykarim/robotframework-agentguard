"""Validates `docs/performance/budgets.md` §2 — MCP transport latency budgets.

Two transports are exercised:

- **In-memory** (`Client(server)`): `p50 ≤ 5 ms`, `p95 ≤ 10 ms` per row in
  `budgets.md` (loose — `exp_01` observed ~2.22 ms/call on a Linux laptop).
- **stdio**: `p50 ≤ 50 ms` (allows for subprocess + framing overhead).

We use `benchmark.pedantic` so we control rounds + warmup explicitly. Failures
manifest as `pytest.fail()` calls so CI surfaces the actual measured value.
"""

from __future__ import annotations

import asyncio
import statistics
from typing import Any

import pytest

fastmcp = pytest.importorskip("fastmcp")


# Budgets in milliseconds — single source of truth, mirrors budgets.md §2.
BUDGET_INMEMORY_P50_MS = 5.0
BUDGET_INMEMORY_P95_MS = 10.0
BUDGET_STDIO_P50_MS = 50.0


def _percentile(samples: list[float], pct: float) -> float:
    """Plain numpy-free percentile (avoid pulling numpy into a tight loop)."""
    if not samples:
        return 0.0
    ordered = sorted(samples)
    k = max(0, min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return ordered[k]


async def _bench_inmemory(server: Any, iterations: int) -> list[float]:
    durations_ms: list[float] = []
    async with fastmcp.Client(server) as client:
        # Warmup — first call pays connection setup.
        await client.call_tool("echo", {"text": "warm"})
        for _ in range(iterations):
            t0 = asyncio.get_event_loop().time()
            await client.call_tool("echo", {"text": "x"})
            durations_ms.append((asyncio.get_event_loop().time() - t0) * 1000.0)
    return durations_ms


@pytest.mark.benchmark(group="mcp-transport")
def test_mcp_inmemory_roundtrip_100x(benchmark: Any, echo_fastmcp_server: Any) -> None:
    """100x in-memory roundtrip — assert p50/p95 against budgets.md §2."""
    measured: dict[str, list[float]] = {"durations_ms": []}

    def _run() -> None:
        measured["durations_ms"] = asyncio.run(_bench_inmemory(echo_fastmcp_server, iterations=100))

    benchmark.pedantic(_run, rounds=3, iterations=1, warmup_rounds=1)

    samples = measured["durations_ms"]
    assert samples, "no samples collected"
    p50 = statistics.median(samples)
    p95 = _percentile(samples, 95.0)
    if p50 > BUDGET_INMEMORY_P50_MS:
        pytest.fail(f"MCP in-memory p50 {p50:.3f} ms exceeds budget {BUDGET_INMEMORY_P50_MS} ms (budgets.md §2)")
    if p95 > BUDGET_INMEMORY_P95_MS:
        pytest.fail(f"MCP in-memory p95 {p95:.3f} ms exceeds budget {BUDGET_INMEMORY_P95_MS} ms (budgets.md §2)")


@pytest.mark.benchmark(group="mcp-transport")
def test_mcp_stdio_echo_roundtrip(benchmark: Any) -> None:
    """stdio transport roundtrip — skipped until the AgentGuard MCP module ships.

    The required entry-point is `AgentGuard.mcp.transports.spawn_echo_stdio()` (or
    equivalent). When that lands, replace the skip with a real async benchmark
    that spawns a subprocess and asserts `p50 ≤ BUDGET_STDIO_P50_MS`.
    """
    try:
        from AgentGuard import mcp as _mcp  # noqa: F401  (presence-check only)
    except ImportError:
        pytest.skip("AgentGuard.mcp not implemented yet")

    pytest.skip("stdio echo fixture pending AgentGuard.mcp.transports — see budgets.md §2")
