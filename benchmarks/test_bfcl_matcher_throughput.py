"""Validates Tier-1 `BFCL AST match` budget — `mean ≤ 1 ms / call` over 100 cases.

Source: `docs/performance/budgets.md` §1 (Tier-1 row) and `tier-routing.md` §2.1.

Until the real `AgentGuard.tool_calls` BFCLAdapter ships, we benchmark a faithful
*structural* matcher (deep-equal on `(name, arguments)`) so the test still
guards the throughput floor. Once the real adapter lands, swap `_match_one()`
for `tool_calls.bfcl.match_one(predicted, expected)` — the budget is unchanged.
"""

from __future__ import annotations

from typing import Any

import pytest

# Budget: docs/performance/budgets.md §1 — Tier-1 keyword classes.
BUDGET_MEAN_MS_PER_CALL = 1.0


def _structural_match(predicted: dict[str, Any], expected: dict[str, Any]) -> bool:
    """Deep-equal on tool name + sorted arguments — placeholder for BFCL AST."""
    if predicted.get("name") != expected.get("name"):
        return False
    p_args = predicted.get("arguments") or {}
    e_args = expected.get("arguments") or {}
    if set(p_args.keys()) != set(e_args.keys()):
        return False
    return all(p_args[k] == e_args[k] for k in e_args)


def _run_match_batch(cases: list[dict[str, Any]]) -> int:
    matches = 0
    for case in cases:
        if _structural_match(case["predicted"], case["expected"]):
            matches += 1
    return matches


@pytest.mark.benchmark(group="bfcl")
def test_bfcl_ast_match_100_cases(benchmark: Any, golden_calls: list[dict[str, Any]]) -> None:
    """Run the matcher across 100 cases; budget is mean wall-clock ≤ 1 ms / call."""
    # Real adapter swap (when ready):
    # try:
    #     from AgentGuard.tool_calls.bfcl import match_one  # noqa: F401
    # except ImportError:
    #     pytest.skip("AgentGuard.tool_calls.bfcl not implemented yet")

    result = benchmark.pedantic(
        _run_match_batch,
        args=(golden_calls,),
        rounds=20,
        iterations=1,
        warmup_rounds=2,
    )
    assert result == len(golden_calls), "all golden cases should match by construction"

    # benchmark.stats has `mean` (seconds) for the *whole batch* of 100 calls.
    mean_total_s = float(benchmark.stats.stats.mean)
    mean_per_call_ms = (mean_total_s * 1000.0) / len(golden_calls)
    if mean_per_call_ms > BUDGET_MEAN_MS_PER_CALL:
        pytest.fail(
            f"BFCL AST match mean {mean_per_call_ms:.4f} ms/call exceeds budget "
            f"{BUDGET_MEAN_MS_PER_CALL} ms/call (budgets.md §1, Tier-1)"
        )
