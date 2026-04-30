"""Validates the Phase-2 in-memory A2A roundtrip budget — `p50 ≤ 10 ms / call`.

Source: Phase-2 budget extension. The in-memory A2A path is what unit tests +
deterministic CI suites use (no httpx, no real server). It must beat 10 ms p50
so the `Send Task` / `Wait For Task Completion` keyword pair stays well below
the per-test wall-clock floor users expect from Robot Framework.

This benchmark constructs an `AgentCard` + `Task` envelope via the bridge
helpers in `AgentGuard.subagents.bridges.base` (those *do* exist today even
when the SubAgents library facade is mid-implementation) and asserts a 100x
roundtrip stays inside budget. If the higher-level
`AgentGuard.subagents.library.SubAgentsKeywords` API lands, this test should
be widened to call `Send Task` end-to-end.
"""

from __future__ import annotations

import statistics
import time
from typing import Any

import pytest

# Budget — Phase-2 A2A in-memory roundtrip ceiling.
BUDGET_P50_MS = 10.0


def _percentile(samples: list[float], pct: float) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    k = max(0, min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return ordered[k]


def _roundtrip_once() -> int:
    """One synthetic A2A roundtrip: build skill+card, then a completed Task envelope."""
    from a2a.types import TaskState

    from AgentGuard.subagents.bridges.base import (
        make_agent_card,
        make_agent_skill,
        make_task,
    )

    skill = make_agent_skill(
        skill_id="weather.lookup",
        name="weather lookup",
        description="Look up the weather for a city.",
        tags=["weather"],
    )
    card = make_agent_card(
        name="bench-agent",
        description="Benchmark agent card",
        version="1.0",
        skills=[skill],
    )
    task = make_task(
        task_id="t-1",
        state=TaskState.TASK_STATE_COMPLETED,
        context_id="ctx-1",
        metadata={"source": "bench"},
    )
    # Touch fields so the optimiser can't elide.
    return len(card.skills) + (1 if task.id else 0)


@pytest.mark.benchmark(group="subagents-a2a")
def test_subagents_a2a_inmemory_roundtrip_100x(benchmark: Any) -> None:
    """100 in-memory A2A roundtrips per round — assert p50 ≤ 10 ms / call."""
    try:
        from AgentGuard.subagents.bridges import base  # noqa: F401
        import a2a.types  # noqa: F401
    except ImportError:
        pytest.skip("AgentGuard.subagents.bridges or a2a-sdk not available")

    measured: dict[str, list[float]] = {"durations_ms": []}

    def _run() -> None:
        durations: list[float] = []
        for _ in range(100):
            t0 = time.perf_counter()
            _roundtrip_once()
            durations.append((time.perf_counter() - t0) * 1000.0)
        measured["durations_ms"] = durations

    benchmark.pedantic(_run, rounds=3, iterations=1, warmup_rounds=1)

    samples = measured["durations_ms"]
    assert samples, "no roundtrip samples collected"
    p50 = statistics.median(samples)
    if p50 > BUDGET_P50_MS:
        pytest.fail(
            f"A2A in-memory roundtrip p50 {p50:.3f} ms exceeds budget "
            f"{BUDGET_P50_MS} ms (Phase-2 A2A budget)"
        )
