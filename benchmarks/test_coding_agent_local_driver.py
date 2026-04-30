"""Validates the Phase-3 LocalDriver budget — `total ≤ 1 s` for a 5-turn run.

Source: Phase-3 brief. ``LocalDriver`` is the offline, always-runnable driver
that powers CI smoke tests + the example suite. With a stubbed
:class:`AgentGuard.providers.mock.MockProvider` (no network), a 5-turn ReAct
loop + JSONL emission + parser handoff must total under 1 second wall clock
so the example suite remains snappy.

We measure the *whole* loop (run + parse) in one pedantic round to keep the
budget meaningful. Skips when the LocalDriver or MockProvider cannot be
imported.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

# Budget — Phase-3 LocalDriver mock-provider 5-turn ceiling.
BUDGET_TOTAL_S = 1.0


def _build_mock_provider() -> Any:
    """Stub a 5-turn conversation: 4 tool calls then a final assistant text."""
    from AgentGuard.providers.base import ChatResponse, Usage
    from AgentGuard.providers.mock import MockProvider

    tool_responses = [
        ChatResponse(
            text="",
            tool_calls=[
                {
                    "id": f"call-{i}",
                    "type": "function",
                    "function": {
                        "name": ("read", "edit", "bash", "grep")[i],
                        "arguments": '{"path": "/tmp/x.py"}',
                    },
                }
            ],
            usage=Usage(prompt_tokens=20, completion_tokens=10, cost_usd=Decimal("0")),
        )
        for i in range(4)
    ]
    final = ChatResponse(
        text="Done. Summarised the project layout.",
        tool_calls=[],
        usage=Usage(prompt_tokens=20, completion_tokens=8, cost_usd=Decimal("0")),
    )
    return MockProvider(responses=[*tool_responses, final])


@pytest.mark.benchmark(group="coding-agent-driver")
def test_local_driver_5turn_mock_budget(
    benchmark: Any, tmp_path: Path
) -> None:
    """LocalDriver 5-turn run + JSONL parse — total ≤ 1 s."""
    try:
        from AgentGuard.coding_agent.drivers.base import DriverConfig
        from AgentGuard.coding_agent.drivers.local import LocalDriver
    except ImportError:
        pytest.skip("AgentGuard.coding_agent.drivers.local not implemented yet")

    out_dir = tmp_path / "sessions"
    out_dir.mkdir(parents=True, exist_ok=True)

    def _run_once() -> int:
        # Fresh provider each round so the deque doesn't deplete across rounds.
        provider = _build_mock_provider()
        driver = LocalDriver(provider=provider)
        cfg = DriverConfig(
            model="mock/local",
            cwd=str(tmp_path),
            max_turns=5,
            capture_jsonl=True,
            jsonl_path=str(out_dir / "bench.jsonl"),
        )
        result = driver.run(prompt="Explain the project layout briefly.", config=cfg)
        # Sanity: parse must have wired up the session via parser sibling.
        sess = result.session
        if sess is None:
            return 0
        return len(sess.messages)

    nmsgs = benchmark.pedantic(
        _run_once, rounds=3, iterations=1, warmup_rounds=1
    )
    assert nmsgs > 0, "LocalDriver produced no parsed messages"

    mean_s = float(benchmark.stats.stats.mean)
    if mean_s > BUDGET_TOTAL_S:
        pytest.fail(
            f"LocalDriver mean {mean_s:.3f} s exceeds budget "
            f"{BUDGET_TOTAL_S} s (Phase-3 LocalDriver mock-provider budget)"
        )
