"""Validates Tier-1 hook envelope synthesis budget — `mean ≤ 1 ms / envelope`.

Source: this file extends `docs/performance/budgets.md` §1 (Tier-1 row) with a
Phase-2 line item — envelope synthesis is pure-Python (no LLM, no I/O) and so
must obey the same `<1 ms` throughput floor as every other Tier-1 keyword.

We build envelopes for all 12 Claude Code lifecycle events × 100 iterations per
benchmark round so the per-envelope cost amortises over 1 200 calls per round
and the resulting `mean / 1200` is the metric we assert against the budget.
"""

from __future__ import annotations

from typing import Any

import pytest

# Budget — single source of truth, mirrors budgets.md §1 (Tier-1 keyword class).
BUDGET_MEAN_MS_PER_ENVELOPE = 1.0


# Twelve canonical events, each paired with a representative kwargs payload.
# Mirrors `AgentGuard.hooks.events.HookEvent` so a regression in the per-event
# default table is caught here as well.
_EVENT_FIXTURES: tuple[tuple[str, dict[str, Any]], ...] = (
    ("UserPromptSubmit", {"prompt": "summarise the diff"}),
    ("UserPromptExpansion", {"prompt": "@me", "expanded_prompt": "@manykarim"}),
    ("PreToolUse", {"tool_name": "Bash", "tool_input": {"command": "ls"}}),
    (
        "PostToolUse",
        {
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "tool_response": {"stdout": "README.md\n"},
        },
    ),
    (
        "PostToolUseFailure",
        {
            "tool_name": "Bash",
            "tool_input": {"command": "false"},
            "tool_response": {"stdout": ""},
            "error": "exit 1",
        },
    ),
    (
        "PostToolBatch",
        {
            "tool_calls": [
                {"name": "Read", "arguments": {"file_path": "/tmp/a"}},
                {"name": "Read", "arguments": {"file_path": "/tmp/b"}},
            ]
        },
    ),
    ("Notification", {"message": "Idle for 60s"}),
    ("Stop", {"stop_hook_active": False}),
    ("SubagentStop", {"stop_hook_active": False, "subagent_id": "sa-1"}),
    ("PreCompact", {"trigger": "auto", "custom_instructions": ""}),
    ("SessionStart", {"source": "startup"}),
    ("ConfigChange", {"changes": {"model": "claude-sonnet-4-5"}}),
)


def _build_all_envelopes(iterations: int) -> int:
    """Build 12 envelopes per iteration; return the total count for sanity check."""
    from AgentGuard.hooks.envelope import synthesize_envelope

    count = 0
    for _ in range(iterations):
        for event, fields in _EVENT_FIXTURES:
            env = synthesize_envelope(event, **fields)
            # Touch one field so the optimiser cannot DCE the call.
            count += 1 if env["hook_event_name"] else 0
    return count


@pytest.mark.benchmark(group="hooks-envelope")
def test_hooks_envelope_synthesis_12x100(benchmark: Any) -> None:
    """12 events × 100 iterations per round — mean per envelope ≤ 1 ms."""
    try:
        import AgentGuard.hooks.envelope  # noqa: F401
    except ImportError:
        pytest.skip("AgentGuard.hooks.envelope not implemented yet")

    iterations = 100
    envelopes_per_round = iterations * len(_EVENT_FIXTURES)

    result = benchmark.pedantic(
        _build_all_envelopes,
        args=(iterations,),
        rounds=10,
        iterations=1,
        warmup_rounds=2,
    )
    assert result == envelopes_per_round, f"expected {envelopes_per_round} envelopes built, got {result}"

    mean_round_s = float(benchmark.stats.stats.mean)
    mean_per_env_ms = (mean_round_s * 1000.0) / envelopes_per_round
    if mean_per_env_ms > BUDGET_MEAN_MS_PER_ENVELOPE:
        pytest.fail(
            f"hooks envelope synthesis mean {mean_per_env_ms:.4f} ms/envelope "
            f"exceeds budget {BUDGET_MEAN_MS_PER_ENVELOPE} ms (Tier-1, Phase-2 budget)"
        )
