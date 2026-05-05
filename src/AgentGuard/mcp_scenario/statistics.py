"""Pure-Python statistics for tool-call records (Tier-1, ADR-021).

All functions are deterministic; none touch an LLM. Hit-rate formula is byte-
equivalent to ``rf-mcp/tests/e2e/metrics_collector.py:57-99`` to preserve
drop-in adoption of historical artifacts.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from AgentGuard.mcp_scenario.types import (
    ExpectedToolCall,
    ToolCallRecord,
    ToolCallStatistics,
)


def calculate_tool_hit_rate(
    records: list[ToolCallRecord],
    expected_tools: list[ExpectedToolCall],
) -> float:
    """Fraction of ``expected_tools`` whose multiplicity + required_params match.

    rf-mcp formula: an expectation is "met" when call count is within
    ``[min_calls, max_calls]`` AND every recorded call's arguments contain the
    declared ``required_params`` key/value pairs.
    """
    if not expected_tools:
        return 1.0
    met = 0
    for expected in expected_tools:
        actual = [r for r in records if r.tool_name == expected.tool_name]
        count = len(actual)
        if count < expected.min_calls:
            continue
        if expected.max_calls is not None and count > expected.max_calls:
            continue
        if expected.required_params:
            params_ok = all(_required_params_in_call(r, expected.required_params) for r in actual)
            if not params_ok:
                continue
        met += 1
    return met / len(expected_tools)


def calculate_expected_met(
    records: list[ToolCallRecord],
    expected_tools: list[ExpectedToolCall],
) -> int:
    """Number of expectations whose count bounds were satisfied (ignores params)."""
    met = 0
    for expected in expected_tools:
        count = sum(1 for r in records if r.tool_name == expected.tool_name)
        if count >= expected.min_calls and (expected.max_calls is None or count <= expected.max_calls):
            met += 1
    return met


def summary_stats(records: list[ToolCallRecord]) -> ToolCallStatistics:
    """Return the rf-mcp-shaped summary over ``records``."""
    total = len(records)
    successful = sum(1 for r in records if r.success)
    counts: dict[str, int] = dict(Counter(r.tool_name for r in records))
    return ToolCallStatistics(
        total_tool_calls=total,
        successful_calls=successful,
        failed_calls=total - successful,
        success_rate=(successful / total) if total else 0.0,
        tool_call_counts=counts,
        unique_tools_called=len(counts),
    )


def required_params_match(records: list[ToolCallRecord], expected: ExpectedToolCall) -> bool:
    """True iff every call to ``expected.tool_name`` had the required params."""
    if not expected.required_params:
        return True
    actuals = [r for r in records if r.tool_name == expected.tool_name]
    if not actuals:
        return False
    return all(_required_params_in_call(r, expected.required_params) for r in actuals)


def _required_params_in_call(record: ToolCallRecord, required: dict[str, Any]) -> bool:
    args = record.arguments or {}
    for key, expected_value in required.items():
        if key not in args or args[key] != expected_value:
            return False
    return True


__all__ = [
    "calculate_expected_met",
    "calculate_tool_hit_rate",
    "required_params_match",
    "summary_stats",
]
