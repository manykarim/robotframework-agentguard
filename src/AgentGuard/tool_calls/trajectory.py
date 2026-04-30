"""Ordered subsequence + multiset matchers for tool trajectories (ADR-004).

Single-turn parallel: multiset equality of (name, args).
Multi-turn / trajectories: ordered subsequence over the *flattened* tool
sequence, with optional ``"*"`` wildcards that match any single call.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from AgentGuard.tool_calls.bfcl_matcher import (
    ast_equal,
    call_signature,
    coerce_tool_call,
)
from AgentGuard.tool_calls.types import ToolCall

WILDCARD = "*"


# ---------------------------------------------------------------------------
# Trajectory extraction
# ---------------------------------------------------------------------------


def extract_tool_names(messages: Sequence[Mapping[str, Any]]) -> list[str]:
    """Pull tool names out of a chat transcript in call order.

    Walks ``messages`` (assistant/user/tool roles), reads each assistant's
    ``tool_calls`` list, and emits the function name for every call.
    """
    names: list[str] = []
    for message in messages:
        tool_calls = message.get("tool_calls") if isinstance(message, Mapping) else None
        if not tool_calls:
            continue
        for raw_call in tool_calls:
            try:
                call = coerce_tool_call(raw_call)
            except ValueError:
                continue
            names.append(call.name)
    return names


def normalise_trajectory(
    trajectory: Sequence[ToolCall | Mapping[str, Any]],
) -> list[ToolCall]:
    """Coerce each entry to a :class:`ToolCall`, dropping malformed ones."""
    out: list[ToolCall] = []
    for entry in trajectory:
        try:
            out.append(coerce_tool_call(entry))
        except ValueError:
            continue
    return out


# ---------------------------------------------------------------------------
# Parallel match (multiset equality)
# ---------------------------------------------------------------------------


def match_parallel(
    actual: Sequence[ToolCall | Mapping[str, Any]],
    expected: Sequence[ToolCall | Mapping[str, Any]],
) -> bool:
    """Multiset equality on ``(name, normalised_args)`` signatures.

    BFCL parallel category ignores call order but requires exact count for
    each unique ``(name, args)`` combination.
    """
    try:
        actual_sigs = Counter(call_signature(c) for c in actual)
        expected_sigs = Counter(call_signature(c) for c in expected)
    except ValueError:
        return False
    return actual_sigs == expected_sigs


# ---------------------------------------------------------------------------
# Ordered subsequence match (multi-turn trajectories)
# ---------------------------------------------------------------------------


def match_sequence(
    actual_seq: Sequence[ToolCall | Mapping[str, Any] | str],
    expected_seq: Sequence[ToolCall | Mapping[str, Any] | str],
    *,
    wildcards: bool = True,
) -> bool:
    """Ordered subsequence match over tool calls.

    ``expected_seq`` items may be:

    * a string ``"name"`` — match by tool name only,
    * the literal ``"*"`` — match any single call (when ``wildcards=True``),
    * a dict ``{"name": "x", "args": {...}}`` — match by name + AST equality
      on the supplied subset of arguments,
    * a :class:`ToolCall` — full name+args match.

    With ``wildcards=False``, the actual sequence must equal expected
    element-for-element (no skipping of unrelated calls).
    """
    actual_norm = _coerce_seq(actual_seq)
    if not wildcards:
        if len(actual_norm) != len(expected_seq):
            return False
        return all(
            _matches_expected(a, e, wildcards=False) for a, e in zip(actual_norm, expected_seq, strict=False)
        )

    # Subsequence walk with wildcard support.
    i = 0
    for expected in expected_seq:
        if isinstance(expected, str) and expected == WILDCARD:
            if i >= len(actual_norm):
                return False
            i += 1
            continue
        while i < len(actual_norm) and not _matches_expected(actual_norm[i], expected, wildcards=True):
            i += 1
        if i >= len(actual_norm):
            return False
        i += 1
    return True


def should_not_call_any_tool(
    actual_seq: Sequence[ToolCall | Mapping[str, Any]],
) -> bool:
    """BFCL "decide-not-to-act": assert the actual trajectory is empty."""
    return len(_coerce_seq(actual_seq)) == 0


# ---------------------------------------------------------------------------
# Aggregate score (for `BFCL Score Should Be Above`)
# ---------------------------------------------------------------------------


def bfcl_score(
    actual: Sequence[ToolCall | Mapping[str, Any] | str],
    expected: Sequence[ToolCall | Mapping[str, Any] | str],
) -> float:
    """Per-trajectory accuracy in [0, 1] (research §3.1).

    All-or-nothing: 1.0 iff :func:`match_sequence` (with wildcards on) holds,
    else the longest-common-subsequence fraction over tool names. This keeps
    the metric bounded and monotone — a perfect match is 1.0, an empty
    actual against a non-empty expected is 0.0.
    """
    if not expected:
        return 1.0 if not actual else 0.0
    if match_sequence(actual, expected, wildcards=True):
        return 1.0
    actual_names = _names_only(actual)
    expected_names = _names_only(expected)
    if not actual_names:
        return 0.0
    return _lcs_length(actual_names, expected_names) / len(expected_names)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _coerce_seq(
    seq: Sequence[ToolCall | Mapping[str, Any] | str],
) -> list[ToolCall | str]:
    out: list[ToolCall | str] = []
    for entry in seq:
        if isinstance(entry, str):
            out.append(entry)
            continue
        try:
            out.append(coerce_tool_call(entry))
        except ValueError:
            # Best-effort: a malformed entry can't match anything.
            out.append(ToolCall(name="<malformed>"))
    return out


def _matches_expected(
    actual: ToolCall | str,
    expected: ToolCall | Mapping[str, Any] | str,
    *,
    wildcards: bool,
) -> bool:
    if wildcards and isinstance(expected, str) and expected == WILDCARD:
        return True
    actual_name = actual if isinstance(actual, str) else actual.name
    if isinstance(expected, str):
        return actual_name == expected
    if isinstance(expected, ToolCall):
        if isinstance(actual, str):
            return actual == expected.name and not expected.arguments
        return actual.name == expected.name and ast_equal(actual.arguments, expected.arguments)
    if isinstance(expected, Mapping):
        name = expected.get("name")
        if not isinstance(name, str):
            return False
        if isinstance(actual, str):
            return actual == name and not expected.get("args") and not expected.get("arguments")
        if actual.name != name:
            return False
        args = expected.get("args", expected.get("arguments"))
        if args is None:
            return True
        if not isinstance(args, Mapping):
            return False
        return ast_equal(actual.arguments, dict(args))
    return False


def _names_only(seq: Sequence[ToolCall | Mapping[str, Any] | str]) -> list[str]:
    names: list[str] = []
    for entry in _coerce_seq(seq):
        if isinstance(entry, str):
            if entry == WILDCARD:
                continue
            names.append(entry)
        else:
            names.append(entry.name)
    return names


def _lcs_length(a: Sequence[str], b: Sequence[str]) -> int:
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for ai in a:
        curr = [0] * (len(b) + 1)
        for j, bj in enumerate(b, start=1):
            curr[j] = prev[j - 1] + 1 if ai == bj else max(prev[j], curr[j - 1])
        prev = curr
    return prev[-1]


__all__ = [
    "WILDCARD",
    "bfcl_score",
    "extract_tool_names",
    "match_parallel",
    "match_sequence",
    "normalise_trajectory",
    "should_not_call_any_tool",
]
