"""OpenCode (sst.dev) session JSONL parser — secondary, low-confidence.

OpenCode session logs live under ``~/.opencode/sessions/`` and use a
turn-oriented JSONL similar to OpenAI's chat completions. The parser is a
best-effort field walk that records every top-level key it sees so callers
can validate coverage.

Like the Codex parser, this is intentionally permissive — never crash on
an unknown field, just stash it in ``metadata`` and move on.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import jsonlines

from .exceptions import MalformedSessionError
from .normalise import coerce_content, extract_usage, parse_iso8601
from .types import Message, Session, ToolCall, ToolResponse, Usage

__all__ = ["parse"]


def parse(path: str | Path, *, max_lines: int | None = None) -> Session:
    """Parse an OpenCode session JSONL into a canonical :class:`Session`.

    Marks ``metadata['parser_confidence'] = 'low'`` since the schema is not
    yet pinned by an upstream spec.
    """
    p = Path(path)
    messages: list[Message] = []
    tool_calls: list[ToolCall] = []
    tool_responses: list[ToolResponse] = []
    usage = Usage()
    timestamps: list[datetime] = []
    seen_keys: set[str] = set()
    session_id = ""

    try:
        with jsonlines.open(p, mode="r") as reader:
            for index, raw in enumerate(reader):
                if max_lines is not None and index >= max_lines:
                    break
                if not isinstance(raw, dict):
                    continue
                seen_keys.update(raw.keys())
                if not session_id:
                    sid = raw.get("session_id") or raw.get("sessionId") or raw.get("id")
                    if isinstance(sid, str):
                        session_id = sid

                ts = parse_iso8601(raw.get("timestamp") or raw.get("ts"))
                if ts is not None:
                    timestamps.append(ts)

                _ingest_opencode_record(raw, ts, messages, tool_calls, tool_responses, usage)
    except jsonlines.InvalidLineError as exc:  # pragma: no cover - defensive
        raise MalformedSessionError(f"Invalid JSONL line in {p}: {exc}") from exc

    return Session(
        id=session_id or "unknown",
        source="opencode",
        messages=messages,
        tool_calls=tool_calls,
        tool_responses=tool_responses,
        usage=usage,
        started_at=min(timestamps) if timestamps else None,
        ended_at=max(timestamps) if timestamps else None,
        raw_path=str(p),
        metadata={
            "parser_confidence": "low",
            "raw_top_level_keys": sorted(seen_keys),
        },
    )


def _ingest_opencode_record(
    raw: dict[str, Any],
    ts: datetime | None,
    messages: list[Message],
    tool_calls: list[ToolCall],
    tool_responses: list[ToolResponse],
    usage: Usage,
) -> None:
    role = raw.get("role")
    if isinstance(role, str):
        content = raw.get("content") or raw.get("text")
        if isinstance(content, (str, list)):
            messages.append(Message(role=role, content=coerce_content(content), timestamp=ts))
    # OpenAI-shaped tool calls.
    raw_calls = raw.get("tool_calls")
    if isinstance(raw_calls, list):
        for call in raw_calls:
            if not isinstance(call, dict):
                continue
            raw_fn = call.get("function")
            fn: dict[str, Any] = raw_fn if isinstance(raw_fn, dict) else {}
            raw_args = fn.get("arguments")
            args: dict[str, Any] = raw_args if isinstance(raw_args, dict) else {}
            tool_calls.append(
                ToolCall(
                    id=str(call.get("id") or ""),
                    name=str(fn.get("name") or call.get("name") or ""),
                    arguments=args,
                    timestamp=ts,
                )
            )
    if role == "tool":
        tool_responses.append(
            ToolResponse(
                tool_call_id=str(raw.get("tool_call_id") or ""),
                content=raw.get("content"),
                is_error=bool(raw.get("is_error")),
                timestamp=ts,
            )
        )
    msg = raw.get("message") if isinstance(raw.get("message"), dict) else raw
    usage.add(extract_usage(msg))
