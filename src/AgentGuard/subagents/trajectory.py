"""Trajectory extraction for A2A tasks (ADR-008 + ADR-004).

Re-exports ``extract_tool_names`` and ``match_sequence`` from
:mod:`AgentGuard.tool_calls.trajectory` so SubAgents-side tests can do
trajectory comparisons without a separate import path. Adds
:func:`extract_a2a_trajectory` which walks a :class:`Task`'s message
history and pulls out tool-call records in the canonical
``[{"name": ..., "arguments": ...}]`` shape that Phase 1's BFCL matcher
consumes.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from AgentGuard.subagents.types import Message, Task
from AgentGuard.tool_calls.trajectory import (
    bfcl_score,
    extract_tool_names,
    match_parallel,
    match_sequence,
    should_not_call_any_tool,
)


def extract_a2a_trajectory(task: Task) -> list[dict[str, Any]]:
    """Flatten an A2A :class:`Task`'s tool-call sequence.

    For each agent message in :attr:`Task.messages`, append every entry of
    ``message.tool_calls`` in order. Returns a list of
    ``{"name": str, "arguments": dict}`` records matching the shape
    consumed by :func:`AgentGuard.tool_calls.trajectory.match_sequence`.

    Servers that produce A2A messages without explicit tool-call metadata
    yield an empty list — callers can fall back to text-mode assertions.
    """
    trajectory: list[dict[str, Any]] = []
    for message in task.messages:
        if not isinstance(message, Message):  # pragma: no cover - defensive
            continue
        for raw in message.tool_calls:
            if not isinstance(raw, dict):
                continue
            fn_raw = raw.get("function")
            function: dict[str, Any] | None = fn_raw if isinstance(fn_raw, dict) else None
            name_raw = raw.get("name")
            if not isinstance(name_raw, str) or not name_raw:
                if function is None:
                    continue
                fn_name = function.get("name")
                if not isinstance(fn_name, str) or not fn_name:
                    continue
                name_raw = fn_name
            args_raw = raw.get("arguments")
            if args_raw is None and function is not None:
                args_raw = function.get("arguments", {})
            if isinstance(args_raw, str):
                import json

                try:
                    args_raw = json.loads(args_raw)
                except Exception:  # noqa: BLE001
                    args_raw = {}
            args: dict[str, Any] = args_raw if isinstance(args_raw, dict) else {}
            trajectory.append({"name": name_raw, "arguments": args})
    return trajectory


def trajectory_names(task: Task) -> list[str]:
    """Just the tool names from :func:`extract_a2a_trajectory`."""
    return [entry["name"] for entry in extract_a2a_trajectory(task)]


def message_dicts(messages: Sequence[Message]) -> list[dict[str, Any]]:
    """Convert :class:`Message`\\ s into the dict-shape that
    :func:`AgentGuard.tool_calls.trajectory.extract_tool_names` consumes.
    """
    out: list[dict[str, Any]] = []
    for m in messages:
        out.append(
            {
                "role": m.role,
                "tool_calls": [dict(tc) for tc in m.tool_calls],
            }
        )
    return out


__all__ = [
    "bfcl_score",
    "extract_a2a_trajectory",
    "extract_tool_names",
    "match_parallel",
    "match_sequence",
    "message_dicts",
    "should_not_call_any_tool",
    "trajectory_names",
]
