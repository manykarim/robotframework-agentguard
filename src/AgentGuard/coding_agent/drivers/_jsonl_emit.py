"""Claude-Code-shaped JSONL emit helpers used by :class:`LocalDriver`.

Kept in a private module so :mod:`local` stays under the 300-LoC ceiling and
each emitter can be unit-tested in isolation. The shapes mirror the records
observed in ``exp_07`` (research §7.2) so the canonical session-parser
ingests both real Claude Code logs and our synthetic logs uniformly.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import IO, Any

_VERSION = "agentguard-local-0.1"


@dataclass(slots=True)
class RunState:
    """Mutable per-invocation state threaded through emit calls."""

    session_id: str
    parent_uuid: str | None = None
    total_cost: Decimal = Decimal("0")
    prompt_tokens: int = 0
    completion_tokens: int = 0


def now_iso() -> str:
    """ISO-8601 UTC timestamp with millisecond precision and ``Z`` suffix."""
    return datetime.now(tz=UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _safe_args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        try:
            loaded = json.loads(raw)
            return dict(loaded) if isinstance(loaded, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def emit_session_meta(fp: IO[str], state: RunState, cwd: Path, model: str) -> None:
    record = {
        "type": "system",
        "subtype": "session-start",
        "sessionId": state.session_id,
        "timestamp": now_iso(),
        "cwd": str(cwd),
        "version": _VERSION,
        "model": model,
        "isMeta": True,
    }
    fp.write(json.dumps(record) + "\n")


def emit_user_prompt(fp: IO[str], state: RunState, cwd: Path, prompt: str) -> str:
    user_uuid = str(uuid.uuid4())
    record = {
        "type": "user",
        "uuid": user_uuid,
        "parentUuid": None,
        "sessionId": state.session_id,
        "timestamp": now_iso(),
        "cwd": str(cwd),
        "version": _VERSION,
        "userType": "external",
        "isSidechain": False,
        "message": {"role": "user", "content": prompt},
    }
    fp.write(json.dumps(record) + "\n")
    state.parent_uuid = user_uuid
    return user_uuid


def emit_assistant(
    fp: IO[str],
    state: RunState,
    cwd: Path,
    model: str,
    assistant_uuid: str,
    text: str,
    tool_calls: list[dict[str, Any]],
    usage: Any,
) -> None:
    content: list[dict[str, Any]] = []
    if text:
        content.append({"type": "text", "text": text})
    for tc in tool_calls:
        fn = tc.get("function", {}) or {}
        content.append(
            {
                "type": "tool_use",
                "id": tc.get("id", ""),
                "name": fn.get("name", ""),
                "input": _safe_args(fn.get("arguments", "{}")),
            }
        )
    record = {
        "type": "assistant",
        "uuid": assistant_uuid,
        "parentUuid": state.parent_uuid,
        "sessionId": state.session_id,
        "timestamp": now_iso(),
        "cwd": str(cwd),
        "version": _VERSION,
        "isSidechain": False,
        "message": {
            "id": f"msg_{uuid.uuid4().hex[:16]}",
            "role": "assistant",
            "model": model,
            "content": content,
            "usage": {
                "input_tokens": getattr(usage, "prompt_tokens", 0),
                "output_tokens": getattr(usage, "completion_tokens", 0),
            },
        },
    }
    fp.write(json.dumps(record) + "\n")


def emit_tool_result(
    fp: IO[str],
    state: RunState,
    cwd: Path,
    tool_user_uuid: str,
    tool_use_id: str,
    tool_name: str,
    result_text: str,
) -> None:
    record = {
        "type": "user",
        "uuid": tool_user_uuid,
        "parentUuid": state.parent_uuid,
        "sessionId": state.session_id,
        "timestamp": now_iso(),
        "cwd": str(cwd),
        "version": _VERSION,
        "userType": "tool-result",
        "isSidechain": False,
        "toolUseResult": {
            "tool_use_id": tool_use_id,
            "name": tool_name,
            "content": result_text,
        },
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": result_text,
                }
            ],
        },
    }
    fp.write(json.dumps(record) + "\n")


__all__ = [
    "RunState",
    "now_iso",
    "emit_session_meta",
    "emit_user_prompt",
    "emit_assistant",
    "emit_tool_result",
]
