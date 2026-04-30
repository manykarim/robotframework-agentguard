"""Claude Code JSONL parser — the Phase 3 IP.

Per ``docs/research/experiments/REPORT.md`` exp_07, the canonical
``tool_calls / tool_responses / thinking_blocks / interrupts /
hook_events / usage`` fields are **NOT** at the top level of real Claude
Code JSONL. They must be derived by:

1. Walking ``assistant.message.content[]`` for ``tool_use`` / ``thinking``
   / ``text`` parts.
2. Pairing ``toolUseResult`` records (which appear under ``user`` records)
   back to their originating ``tool_use`` via ``parentUuid`` —
   ``toolUseResult`` records carry no ``tool_use_id`` so the parent chain
   is the only link.
3. Detecting interrupts from ``permission-mode`` records and from the
   literal ``[Request interrupted by user]`` marker.
4. Detecting hook events when the ``type`` field matches a Claude Code
   lifecycle name.

The parser streams the file with ``jsonlines`` so multi-MB sessions do
not load whole.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import jsonlines

from . import _helpers as _h
from .exceptions import MalformedSessionError
from .normalise import coerce_content, extract_usage, parse_iso8601
from .types import HookEvent, Interrupt, Message, Session, Usage

__all__ = ["parse"]


def parse(path: str | Path, *, max_lines: int | None = None) -> Session:
    """Parse a Claude Code session JSONL into a canonical :class:`Session`.

    Args:
        path: Filesystem path to the ``.jsonl`` file.
        max_lines: Optional cap for unit tests / smoke runs. ``None`` reads
            the whole file (streamed line-by-line, never fully buffered).

    Returns:
        Fully populated :class:`Session` with ``source="claude-code"``.

    Raises:
        MalformedSessionError: First line cannot be decoded as JSON.
    """
    p = Path(path)
    state = _ParserState(raw_path=str(p))

    try:
        with jsonlines.open(p, mode="r") as reader:
            for index, raw in enumerate(reader):
                if max_lines is not None and index >= max_lines:
                    break
                if not isinstance(raw, dict):
                    continue
                state.ingest(raw)
    except jsonlines.InvalidLineError as exc:  # pragma: no cover - defensive
        raise MalformedSessionError(f"Invalid JSONL line in {p}: {exc}") from exc

    return state.finalize()


class _ParserState:
    """Mutable buffer for a single :func:`parse` invocation."""

    def __init__(self, *, raw_path: str) -> None:
        self.raw_path = raw_path
        self.session_id: str = ""
        self.cwd: str | None = None
        self.git_branch: str | None = None
        self.version: str | None = None
        # uuid -> tool_call_id, so a downstream toolUseResult can resolve.
        self.uuid_to_tool_call: dict[str, str] = {}
        # uuid -> parent_uuid, so we can walk the chain when needed.
        self.parent_chain: dict[str, str] = {}
        self.messages: list[Message] = []
        self.tool_calls: list[Any] = []
        self.tool_responses: list[Any] = []
        self.thinking_blocks: list[Any] = []
        self.interrupts: list[Interrupt] = []
        self.hook_events: list[HookEvent] = []
        self.usage: Usage = Usage()
        self.timestamps: list[datetime] = []
        self.unpaired_results: int = 0

    def ingest(self, record: dict[str, Any]) -> None:
        """Single-record dispatch."""
        rtype = record.get("type", "")
        self._capture_invariants(record)
        ts = parse_iso8601(record.get("timestamp"))
        if ts is not None:
            self.timestamps.append(ts)

        # Track parentUuid early so subsequent toolUseResult lookups work
        # even when records arrive out of timestamp order.
        uuid = record.get("uuid")
        parent = record.get("parentUuid")
        if isinstance(uuid, str) and isinstance(parent, str):
            self.parent_chain[uuid] = parent

        if rtype == "assistant":
            self._ingest_assistant(record, ts)
        elif rtype == "user":
            self._ingest_user(record, ts)
        elif rtype == "system":
            self._ingest_simple(record, ts, role="system")
        elif rtype == "permission-mode":
            self._ingest_permission_mode(record, ts)
        elif rtype in _h.HOOK_LIFECYCLE_TYPES:
            self.hook_events.append(_h.make_hook_event(rtype, record, ts))
        # Other types (file-history-snapshot, last-prompt, attachment, ...)
        # carry no signal for the 12 #42796 metrics — intentionally skipped.

    def _capture_invariants(self, record: dict[str, Any]) -> None:
        if not self.session_id:
            sid = record.get("sessionId")
            if isinstance(sid, str):
                self.session_id = sid
        if self.cwd is None:
            cwd = record.get("cwd")
            if isinstance(cwd, str):
                self.cwd = cwd
        if self.git_branch is None:
            gb = record.get("gitBranch")
            if isinstance(gb, str):
                self.git_branch = gb
        if self.version is None:
            v = record.get("version")
            if isinstance(v, str):
                self.version = v

    def _ingest_assistant(
        self, record: dict[str, Any], ts: datetime | None
    ) -> None:
        message = record.get("message")
        if not isinstance(message, dict):
            return
        self.usage.add(extract_usage(message))
        content = message.get("content")
        if isinstance(content, str):
            self.messages.append(
                Message(role="assistant", content=content, timestamp=ts)
            )
            return
        if not isinstance(content, list):
            return

        msg_tool_calls = []
        for part in content:
            if not isinstance(part, dict):
                continue
            ptype = part.get("type")
            if ptype == "tool_use":
                tc = _h.build_tool_call(part, ts)
                msg_tool_calls.append(tc)
                self.tool_calls.append(tc)
                # Index by the surrounding record's uuid so the user's
                # follow-up toolUseResult can find us.
                uuid = record.get("uuid")
                if isinstance(uuid, str):
                    self.uuid_to_tool_call[uuid] = tc.id
            elif ptype == "thinking":
                self.thinking_blocks.append(_h.build_thinking_block(part, ts))
            elif ptype == "text":
                text = part.get("text")
                if isinstance(text, str):
                    interrupt = _h.interrupt_from_text(text, ts)
                    if interrupt is not None:
                        self.interrupts.append(interrupt)

        self.messages.append(
            Message(
                role="assistant",
                content=coerce_content(content),
                timestamp=ts,
                tool_calls=msg_tool_calls,
            )
        )

    def _ingest_user(self, record: dict[str, Any], ts: datetime | None) -> None:
        # toolUseResult lives at the TOP level of the user record (exp_07).
        result = record.get("toolUseResult")
        if result is not None:
            self._pair_tool_result(record, result, ts)
            # Continue — record may also carry a follow-up message.

        message = record.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str):
                interrupt = _h.interrupt_from_text(content, ts)
                if interrupt is not None:
                    self.interrupts.append(interrupt)
                self.messages.append(_h.build_user_message(content, ts))
            elif isinstance(content, list):
                self.messages.append(_h.build_user_message(content, ts))

    def _ingest_simple(
        self, record: dict[str, Any], ts: datetime | None, *, role: str
    ) -> None:
        message = record.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, (str, list)):
                self.messages.append(_h.build_simple_message(role, content, ts))
                return
        # Some system records carry only top-level ``content``.
        c = record.get("content")
        if isinstance(c, str):
            self.messages.append(_h.build_simple_message(role, c, ts))

    def _ingest_permission_mode(
        self, record: dict[str, Any], ts: datetime | None
    ) -> None:
        mode = record.get("permissionMode") or record.get("mode")
        if isinstance(mode, str):
            if mode.lower() in _h.INTERRUPT_PERMISSION_MODES:
                self.interrupts.append(
                    Interrupt(timestamp=ts, reason=f"permission_mode:{mode}")
                )
            self.hook_events.append(
                HookEvent(event="PermissionMode", decision=mode, timestamp=ts)
            )

    def _pair_tool_result(
        self,
        record: dict[str, Any],
        result: Any,
        ts: datetime | None,
    ) -> None:
        """Resolve the originating ``ToolCall.id`` and record the response."""
        tool_call_id: str | None = None
        if isinstance(result, dict):
            candidate = result.get("tool_use_id") or result.get("id")
            if isinstance(candidate, str) and candidate:
                tool_call_id = candidate

        if tool_call_id is None:
            tool_call_id = self._resolve_via_parent_chain(record)

        if tool_call_id is None:
            self.unpaired_results += 1
            return

        self.tool_responses.append(_h.build_tool_response(tool_call_id, result, ts))

    def _resolve_via_parent_chain(
        self, record: dict[str, Any], max_hops: int = 16
    ) -> str | None:
        cursor = record.get("parentUuid")
        if not isinstance(cursor, str):
            return None
        for _ in range(max_hops):
            if cursor in self.uuid_to_tool_call:
                return self.uuid_to_tool_call[cursor]
            cursor = self.parent_chain.get(cursor, "")
            if not cursor:
                return None
        return None

    def finalize(self) -> Session:
        meta: dict[str, Any] = {"parser_confidence": "high"}
        if self.version is not None:
            meta["claude_code_version"] = self.version
        if self.unpaired_results:
            meta["unpaired_tool_results"] = self.unpaired_results
        return Session(
            id=self.session_id or "unknown",
            source="claude-code",
            messages=self.messages,
            tool_calls=self.tool_calls,
            tool_responses=self.tool_responses,
            thinking_blocks=self.thinking_blocks,
            interrupts=self.interrupts,
            hook_events=self.hook_events,
            usage=self.usage,
            cwd=self.cwd,
            git_branch=self.git_branch,
            started_at=min(self.timestamps) if self.timestamps else None,
            ended_at=max(self.timestamps) if self.timestamps else None,
            raw_path=self.raw_path,
            metadata=meta,
        )
