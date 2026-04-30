"""Validates the Phase-3 #42796 metric-pack budget — `mean ≤ 5 ms / pack`.

Source: Phase-3 brief. The pack runs all 12 calculators against a single
:class:`AgentGuard.coding_agent.session.types.Session`. Per
``docs/performance/budgets.md`` §1, every individual calculator is Tier-1
(<1 ms target) — so 12 of them on a 100-msg session must comfortably fit in
the aggregate 5 ms ceiling. If this trips, the offending calculator is the
one to optimise (run with ``--benchmark-columns=mean,median,min,max
--benchmark-sort=mean`` and look at the per-metric breakdown).

Skips cleanly when ``metrics.pack`` is missing (parallel Phase-3 race).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

# Budget — Phase-3 metric-pack ceiling.
BUDGET_MEAN_MS = 5.0


def _build_synthetic_session(n_messages: int = 100) -> Any:
    """Build a 100-message Session with a realistic Read/Edit/Bash mix.

    The mix is chosen so every calculator has non-degenerate input:

    * 60% Read tool calls (read_edit_ratio numerator)
    * 25% Edit tool calls (denominator + edits-without-read window)
    * 10% Bash tool calls (first-run-test feeds off ``pytest`` invocations)
    * 5%  Write tool calls (write_mutation_ratio)

    Plus three repeated edits on the same file (repeated_edits_per_file)
    and a few "I made a mistake" assistant turns (self_admitted_errors).
    """
    from AgentGuard.coding_agent.session.types import (
        Message,
        Session,
        ToolCall,
        ToolResponse,
        Usage,
    )

    now = datetime.now(tz=timezone.utc)
    messages: list[Message] = []
    tool_calls: list[ToolCall] = []
    tool_responses: list[ToolResponse] = []

    for i in range(n_messages):
        if i % 7 == 0:
            messages.append(Message(role="user", content=f"please do step {i}", timestamp=now))
            continue

        # Tool name distribution.
        mod = i % 20
        if mod < 12:
            name, args = "Read", {"file_path": f"/repo/file{i % 30}.py"}
        elif mod < 17:
            name, args = "Edit", {"file_path": f"/repo/file{i % 30}.py", "old": "x", "new": "y"}
        elif mod < 19:
            name, args = "Bash", {"command": "pytest -q"}
        else:
            name, args = "Write", {"file_path": f"/repo/new_{i}.py", "text": "..."}

        tc_id = f"call-{i}"
        tc = ToolCall(id=tc_id, name=name, arguments=args, timestamp=now)
        tool_calls.append(tc)
        tool_responses.append(
            ToolResponse(
                tool_call_id=tc_id,
                content="ok" if name != "Bash" else "5 passed in 0.3s",
                is_error=False,
                timestamp=now,
            )
        )

        text = "Calling tool"
        if i % 23 == 0:
            text = "I made a mistake. Let me fix that."
        elif i % 17 == 0:
            text = "easy fix; just a simple basic change."  # simplest_word feeder
        messages.append(
            Message(
                role="assistant",
                content=[
                    {"type": "text", "text": text},
                    {"type": "tool_use", "id": tc_id, "name": name, "input": args},
                ],
                timestamp=now,
                tool_calls=[tc],
            )
        )

    return Session(
        id="bench-pack-001",
        source="claude-code",
        messages=messages,
        tool_calls=tool_calls,
        tool_responses=tool_responses,
        usage=Usage(prompt_tokens=12_000, completion_tokens=3_000),
        cwd="/tmp/agentguard-bench",
        started_at=now,
        ended_at=now,
    )


@pytest.fixture(scope="module")
def synthetic_session() -> Any:
    return _build_synthetic_session(n_messages=100)


@pytest.mark.benchmark(group="coding-agent-metrics")
def test_compute_42796_pack_100_msg_budget(
    benchmark: Any, synthetic_session: Any
) -> None:
    """Run all 12 calculators on a 100-msg session — mean ≤ 5 ms."""
    try:
        from AgentGuard.coding_agent.metrics import compute_42796_pack
    except ImportError:
        pytest.skip("AgentGuard.coding_agent.metrics not implemented yet")

    def _pack_once() -> int:
        report = compute_42796_pack(synthetic_session)
        return len(report.metrics)

    result = benchmark.pedantic(
        _pack_once, rounds=50, iterations=1, warmup_rounds=2
    )
    assert result == 12, f"expected 12 metrics, got {result}"

    mean_ms = float(benchmark.stats.stats.mean) * 1000.0
    if mean_ms > BUDGET_MEAN_MS:
        pytest.fail(
            f"#42796 pack mean {mean_ms:.3f} ms exceeds budget "
            f"{BUDGET_MEAN_MS} ms (Phase-3 metric-pack budget)"
        )
