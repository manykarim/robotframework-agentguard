"""Canonical Session schema used by every coding-agent driver and metric.

Per ADR-010, every coding-agent JSONL is normalised into this single shape.
The 12 #42796 metric calculators consume :class:`Session` directly — they
never touch raw vendor records. New drivers (Codex, Aider, OpenCode, Cline,
Continue, Copilot) only need to write a parser.

All dataclasses are mypy --strict clean. ``Session`` is mutable so parsers
can build it incrementally; everything below it is mutable too because most
fields are populated post-init.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

__all__ = [
    "Usage",
    "ToolCall",
    "ToolResponse",
    "ThinkingBlock",
    "Interrupt",
    "HookEvent",
    "Message",
    "Session",
]


@dataclass
class Usage:
    """Aggregated token + cost usage across an entire session.

    Cache fields follow Anthropic's nomenclature: ``cache_read_tokens`` =
    cache hits (cheap), ``cache_write_tokens`` = cache writes (expensive
    on first call, cheap thereafter).
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float | None = None

    def add(self, other: Usage) -> None:
        """In-place sum — used by parsers walking per-assistant ``message.usage``."""
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.cache_read_tokens += other.cache_read_tokens
        self.cache_write_tokens += other.cache_write_tokens
        if other.cost_usd is not None:
            self.cost_usd = (self.cost_usd or 0.0) + other.cost_usd


@dataclass
class ToolCall:
    """A single ``tool_use`` block from an assistant turn."""

    id: str
    name: str
    arguments: dict[str, Any]
    timestamp: datetime | None = None


@dataclass
class ToolResponse:
    """The execution result paired back to a :class:`ToolCall` via ``tool_call_id``.

    For Claude Code, pairing is via ``parentUuid`` — the parser walks the
    parent chain until it finds the ``assistant`` record that emitted the
    matching ``tool_use``.
    """

    tool_call_id: str
    content: Any
    is_error: bool = False
    timestamp: datetime | None = None


@dataclass
class ThinkingBlock:
    """An extended-thinking block from ``message.content[].type == 'thinking'``.

    ``signature_length`` is what powers the Pearson r=0.971 correlation in
    issue #42796 — it must be captured even when the thinking text is
    redacted, because Anthropic ships only the signature in some modes.
    """

    text: str
    signature_length: int = 0
    timestamp: datetime | None = None


@dataclass
class Interrupt:
    """A user-initiated interruption (Esc key, ``[Request interrupted by user]``,
    or a permission-mode transition that signals a stop)."""

    timestamp: datetime | None
    reason: str | None = None


@dataclass
class HookEvent:
    """A Claude Code hook lifecycle event captured in the JSONL.

    ``event`` is one of the 12 lifecycle names handled by
    :mod:`AgentGuard.hooks.events`; ``decision`` is ``block``/``allow``/
    ``escalate``/``ask``/``deny`` when a handler decision is recorded.
    """

    event: str
    decision: str | None = None
    timestamp: datetime | None = None


@dataclass
class Message:
    """One conversation turn.

    ``content`` keeps the raw vendor shape (``str`` for the simple case,
    ``list[dict]`` for Anthropic-style content blocks) so parsers do not
    lose information. Use :meth:`Session.text` for a plain-text rendering.
    """

    role: str
    content: str | list[dict[str, Any]]
    timestamp: datetime | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass
class Session:
    """The canonical post-parse representation of a coding-agent session.

    Field order mirrors ADR-010 §"Decision". Every #42796 calculator consumes
    this dataclass — no calculator may peek at vendor-specific fields.
    """

    id: str
    source: str
    messages: list[Message] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_responses: list[ToolResponse] = field(default_factory=list)
    thinking_blocks: list[ThinkingBlock] = field(default_factory=list)
    interrupts: list[Interrupt] = field(default_factory=list)
    hook_events: list[HookEvent] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    cwd: str | None = None
    git_branch: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    raw_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def text(self) -> str:
        """All message content rendered as plain text.

        Used by reasoning-loop and self-admitted-errors metrics; tool_use /
        tool_result blocks are skipped because they are tracked separately
        in :attr:`tool_calls` / :attr:`tool_responses`.
        """
        chunks: list[str] = []
        for msg in self.messages:
            if isinstance(msg.content, str):
                if msg.content:
                    chunks.append(msg.content)
                continue
            for part in msg.content:
                if not isinstance(part, dict):
                    continue
                ptype = part.get("type")
                if ptype == "text":
                    text = part.get("text")
                    if isinstance(text, str) and text:
                        chunks.append(text)
                elif ptype == "thinking":
                    text = part.get("thinking") or part.get("text")
                    if isinstance(text, str) and text:
                        chunks.append(text)
        return "\n".join(chunks)
