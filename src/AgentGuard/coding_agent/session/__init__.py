"""Session JSONL parsing — Claude Code, Codex, Aider, OpenCode, ...

Per ``exp_07``, real Claude Code JSONL does NOT have ``tool_calls`` /
``tool_responses`` at the top level — they must be derived by walking
``assistant.message.content[]`` and pairing ``toolUseResult`` records via
``parentUuid``. The parser is the IP.

Public surface:

* :func:`parse` — auto-detecting dispatcher (delegates to the right vendor
  parser based on extension + first-line sniff, or an explicit ``format=``).
* :class:`Session`, :class:`Message`, :class:`ToolCall`, :class:`ToolResponse`,
  :class:`ThinkingBlock`, :class:`Interrupt`, :class:`HookEvent`,
  :class:`Usage` — the canonical data model every metric calculator and
  driver consumes.
* The exception hierarchy under :mod:`.exceptions`.
"""

from __future__ import annotations

from .exceptions import (
    MalformedSessionError,
    SessionParseError,
    UnknownSessionFormatError,
    UnpairedToolCallError,
)
from .parser import detect_format, parse
from .types import (
    HookEvent,
    Interrupt,
    Message,
    Session,
    ThinkingBlock,
    ToolCall,
    ToolResponse,
    Usage,
)

__all__ = [
    # Dispatcher
    "parse",
    "detect_format",
    # Schema
    "Session",
    "Message",
    "ToolCall",
    "ToolResponse",
    "ThinkingBlock",
    "Interrupt",
    "HookEvent",
    "Usage",
    # Exceptions
    "SessionParseError",
    "UnknownSessionFormatError",
    "MalformedSessionError",
    "UnpairedToolCallError",
]
