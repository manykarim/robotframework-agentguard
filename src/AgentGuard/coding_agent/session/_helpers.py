"""Internal helpers used by :mod:`AgentGuard.coding_agent.session.claude_code`.

Split out only to keep the parser file under the 300-line per-file budget
(see ``.swarm-coordination.md``). Public surface stays in ``claude_code``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .normalise import coerce_content
from .types import (
    HookEvent,
    Interrupt,
    Message,
    ThinkingBlock,
    ToolCall,
    ToolResponse,
)

__all__ = [
    "HOOK_LIFECYCLE_TYPES",
    "INTERRUPT_PERMISSION_MODES",
    "INTERRUPT_TEXT_MARKER",
    "build_tool_call",
    "build_thinking_block",
    "build_tool_response",
    "interrupt_from_text",
    "build_user_message",
    "build_simple_message",
]

# Lifecycle event names a Claude Code hook can emit. Mirrors the hooks
# module list but kept inline so the parser hot path has no cross-module
# import overhead.
HOOK_LIFECYCLE_TYPES: frozenset[str] = frozenset(
    {
        "UserPromptSubmit",
        "PreToolUse",
        "PostToolUse",
        "Stop",
        "SubagentStop",
        "SessionStart",
        "SessionEnd",
        "Notification",
        "PreCompact",
        "PostCompact",
        "ConfigChange",
        "ModelChange",
    }
)

# Permission modes that signal an interrupt-like state.
INTERRUPT_PERMISSION_MODES: frozenset[str] = frozenset({"stopped", "denied", "cancelled", "interrupted"})

INTERRUPT_TEXT_MARKER = "[Request interrupted by user]"


def build_tool_call(part: dict[str, Any], ts: datetime | None) -> ToolCall:
    """Construct a :class:`ToolCall` from a ``tool_use`` content block."""
    return ToolCall(
        id=str(part.get("id") or ""),
        name=str(part.get("name") or ""),
        arguments=dict(part.get("input") or {}),
        timestamp=ts,
    )


def build_thinking_block(part: dict[str, Any], ts: datetime | None) -> ThinkingBlock:
    """Construct a :class:`ThinkingBlock`. Captures ``signature_length``
    via the ``signature`` field, falling back to the text length when the
    signature is absent (older Claude Code versions)."""
    text_value = part.get("thinking") or part.get("text") or ""
    signature = part.get("signature") or ""
    sig_len = len(signature) if isinstance(signature, str) else 0
    if sig_len == 0 and isinstance(text_value, str):
        sig_len = len(text_value)
    return ThinkingBlock(
        text=str(text_value),
        signature_length=sig_len,
        timestamp=ts,
    )


def build_tool_response(tool_call_id: str, result: Any, ts: datetime | None) -> ToolResponse:
    """Construct a :class:`ToolResponse` from a paired ``toolUseResult``
    payload. Handles both dict and bare-string content."""
    is_error = False
    content: Any = result
    if isinstance(result, dict):
        is_error = bool(result.get("is_error") or result.get("error"))
        # If a vendor wraps the actual content under ``content``, use that;
        # otherwise pass the whole dict through so callers can introspect.
        if "content" in result:
            content = result["content"]
    return ToolResponse(
        tool_call_id=tool_call_id,
        content=content,
        is_error=is_error,
        timestamp=ts,
    )


def interrupt_from_text(text: str, ts: datetime | None) -> Interrupt | None:
    """Return an :class:`Interrupt` if the literal interrupt marker is in
    ``text``; otherwise ``None``."""
    if INTERRUPT_TEXT_MARKER in text:
        return Interrupt(timestamp=ts, reason="user_interrupt")
    return None


def build_user_message(content: str | list[Any], ts: datetime | None) -> Message:
    """Construct a user :class:`Message`, normalising content shape."""
    return Message(role="user", content=coerce_content(content), timestamp=ts)


def build_simple_message(role: str, content: str | list[Any], ts: datetime | None) -> Message:
    """Construct a non-assistant :class:`Message` (system, tool)."""
    return Message(role=role, content=coerce_content(content), timestamp=ts)


def hook_event_decision(record: dict[str, Any]) -> str | None:
    """Pull a decision string out of a hook-event record. Different
    Claude Code versions stash this in different keys; check the common
    ones in priority order."""
    for key in ("decision", "permission_decision"):
        value = record.get(key)
        if isinstance(value, str):
            return value
    msg = record.get("message")
    if isinstance(msg, dict):
        value = msg.get("decision")
        if isinstance(value, str):
            return value
    return None


def make_hook_event(rtype: str, record: dict[str, Any], ts: datetime | None) -> HookEvent:
    """Build a :class:`HookEvent` from a lifecycle-typed record."""
    return HookEvent(event=rtype, decision=hook_event_decision(record), timestamp=ts)
