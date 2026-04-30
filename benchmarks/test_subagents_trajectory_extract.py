"""Validates the Phase-2 trajectory-extraction budget — `mean ≤ 5 ms / task`.

Source: Phase-2 budget extension. `extract_tool_names` is the canonical hot
loop downstream of `Send Task` / framework bridges — every assertion that
inspects a delegation trajectory walks the message list once. With realistic
100-message fixtures we want the cost to amortise well under the Tier-1 5 ms
ceiling so test wall-clock does not balloon at scale.
"""

from __future__ import annotations

from typing import Any

import pytest

# Budget — Phase-2 trajectory-extract ceiling.
BUDGET_MEAN_MS_PER_TASK = 5.0


def _build_messages(n: int) -> list[dict[str, Any]]:
    """Synthesise a 100-message agent transcript (realistic mix of roles)."""
    msgs: list[dict[str, Any]] = []
    tools = ("search", "fetch", "summarise", "weather.lookup", "places.search")
    for i in range(n):
        role = "assistant" if i % 2 == 0 else "user"
        if role == "assistant":
            msgs.append(
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": f"call-{i}",
                            "type": "function",
                            "function": {
                                "name": tools[i % len(tools)],
                                "arguments": '{"q": "x"}',
                            },
                        },
                        {
                            "id": f"call-{i}-b",
                            "type": "function",
                            "function": {
                                "name": tools[(i + 1) % len(tools)],
                                "arguments": '{"q": "y"}',
                            },
                        },
                    ],
                }
            )
        else:
            msgs.append({"role": "user", "content": f"please do step {i}"})
    return msgs


def _extract_once(messages: list[dict[str, Any]]) -> int:
    from AgentGuard.tool_calls.trajectory import extract_tool_names

    names = extract_tool_names(messages)
    return len(names)


@pytest.mark.benchmark(group="subagents-trajectory")
def test_subagents_trajectory_extract_100msgs(benchmark: Any) -> None:
    """Extract trajectory from a 100-message task — mean ≤ 5 ms / call."""
    try:
        from AgentGuard.tool_calls.trajectory import extract_tool_names  # noqa: F401
    except ImportError:
        pytest.skip("AgentGuard.tool_calls.trajectory not implemented yet")

    messages = _build_messages(100)
    expected_calls = sum(1 for m in messages if m.get("role") == "assistant") * 2

    result = benchmark.pedantic(
        _extract_once,
        args=(messages,),
        rounds=50,
        iterations=1,
        warmup_rounds=2,
    )
    assert result == expected_calls, f"expected {expected_calls} extracted names, got {result}"

    mean_ms = float(benchmark.stats.stats.mean) * 1000.0
    if mean_ms > BUDGET_MEAN_MS_PER_TASK:
        pytest.fail(
            f"trajectory extract mean {mean_ms:.3f} ms/call exceeds budget "
            f"{BUDGET_MEAN_MS_PER_TASK} ms (Phase-2 trajectory budget)"
        )
