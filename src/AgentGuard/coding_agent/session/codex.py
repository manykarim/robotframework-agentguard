"""Codex (OpenAI Codex CLI) session JSONL parser — secondary, low-confidence.

The Codex CLI writes session logs into ``~/.codex/sessions/`` but the exact
schema is not pinned in any public spec at the time of writing. This parser
applies the same field-walking pattern as ``claude_code`` and records every
top-level key it encounters into ``Session.metadata['raw_top_level_keys']``
so a downstream consumer can confirm coverage.

Per ADR-009 / ADR-010: do not crash on unknown fields — degrade gracefully
to ``parser_confidence='low'`` and let the metric calculators decide whether
they have enough signal.
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
    """Parse a Codex CLI session JSONL into a canonical :class:`Session`.

    Codex's exact JSONL shape is not yet stable; the parser is best-effort
    and marks ``metadata['parser_confidence'] = 'low'``.
    """
    p = Path(path)
    messages: list[Message] = []
    tool_calls: list[ToolCall] = []
    tool_responses: list[ToolResponse] = []
    usage = Usage()
    timestamps: list[datetime] = []
    seen_keys: set[str] = set()
    session_id = ""
    cwd: str | None = None

    try:
        with jsonlines.open(p, mode="r") as reader:
            for index, raw in enumerate(reader):
                if max_lines is not None and index >= max_lines:
                    break
                if not isinstance(raw, dict):
                    continue
                seen_keys.update(raw.keys())
                if not session_id:
                    sid = raw.get("session_id") or raw.get("sessionId")
                    if isinstance(sid, str):
                        session_id = sid
                if cwd is None:
                    c = raw.get("cwd")
                    if isinstance(c, str):
                        cwd = c

                ts = parse_iso8601(raw.get("timestamp") or raw.get("created_at"))
                if ts is not None:
                    timestamps.append(ts)

                _ingest_codex_record(raw, ts, messages, tool_calls, tool_responses, usage)
    except jsonlines.InvalidLineError as exc:  # pragma: no cover - defensive
        raise MalformedSessionError(f"Invalid JSONL line in {p}: {exc}") from exc

    return Session(
        id=session_id or "unknown",
        source="codex",
        messages=messages,
        tool_calls=tool_calls,
        tool_responses=tool_responses,
        usage=usage,
        cwd=cwd,
        started_at=min(timestamps) if timestamps else None,
        ended_at=max(timestamps) if timestamps else None,
        raw_path=str(p),
        metadata={
            "parser_confidence": "low",
            "raw_top_level_keys": sorted(seen_keys),
        },
    )


def _ingest_codex_record(
    raw: dict[str, Any],
    ts: datetime | None,
    messages: list[Message],
    tool_calls: list[ToolCall],
    tool_responses: list[ToolResponse],
    usage: Usage,
) -> None:
    """Best-effort ingestion. Codex appears to use a ``turn``-style schema
    with ``role`` + ``content`` and inline ``tool_calls``/``tool_results``.
    """
    role = raw.get("role")
    if isinstance(role, str):
        content = raw.get("content")
        if isinstance(content, (str, list)):
            messages.append(Message(role=role, content=coerce_content(content), timestamp=ts))
    # OpenAI-style tool_calls inline on the assistant turn.
    raw_calls = raw.get("tool_calls")
    if isinstance(raw_calls, list):
        for call in raw_calls:
            if not isinstance(call, dict):
                continue
            raw_fn = call.get("function")
            fn: dict[str, Any] = raw_fn if isinstance(raw_fn, dict) else {}
            tool_calls.append(
                ToolCall(
                    id=str(call.get("id") or ""),
                    name=str(fn.get("name") or call.get("name") or ""),
                    arguments=_safe_args(fn.get("arguments") or call.get("arguments")),
                    timestamp=ts,
                )
            )
    # And the OpenAI-style tool message reply.
    if role == "tool":
        tool_responses.append(
            ToolResponse(
                tool_call_id=str(raw.get("tool_call_id") or ""),
                content=raw.get("content"),
                is_error=bool(raw.get("is_error")),
                timestamp=ts,
            )
        )
    # Usage may appear per turn or per session-end record.
    msg = raw.get("message") if isinstance(raw.get("message"), dict) else raw
    usage.add(extract_usage(msg))


def _safe_args(value: Any) -> dict[str, Any]:
    """Codex sometimes ships arguments as a JSON-encoded string. Return a
    dict either way; never raise."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        import json

        try:
            decoded = json.loads(value)
        except ValueError:
            return {"_raw": value}
        return decoded if isinstance(decoded, dict) else {"_raw": value}
    return {}
