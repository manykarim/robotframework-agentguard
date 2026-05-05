"""Aider chat-history markdown parser — medium-confidence.

Aider stores its conversation history as Markdown in ``.aider.chat.history.md``.
The format is informal but stable enough to parse with simple block heuristics:

* Sessions begin with a header line matching ``# aider chat started at``.
* User prompts begin with ``####`` and continue until the next blank-line +
  non-prefixed paragraph.
* Assistant responses are everything between user prompts that is NOT a
  fenced code block of edit instructions.
* Tool calls in Aider are filesystem edits expressed as fenced code blocks
  with a leading filename line, e.g. ``path/to/file.py`` then a SEARCH/
  REPLACE block. We surface each as a synthetic ``Edit`` :class:`ToolCall`.

The heuristic is documented inline so future drift is fixable without
re-deriving the parser.
"""

from __future__ import annotations

import re
from pathlib import Path

from .normalise import parse_iso8601
from .types import Message, Session, ToolCall

__all__ = ["parse"]

_SESSION_HEADER_RE = re.compile(r"^#\s+aider\s+chat\s+started\s+at\s+(?P<ts>.+)$", re.IGNORECASE)
_USER_PROMPT_RE = re.compile(r"^####\s+(.*)$")
_FENCE_RE = re.compile(r"^```")
_FILENAME_HINT_RE = re.compile(r"^[A-Za-z0-9_./-]+\.[A-Za-z0-9]+$")


def parse(path: str | Path, *, max_lines: int | None = None) -> Session:
    """Parse an Aider chat history markdown file into a :class:`Session`.

    Args:
        path: Path to ``.aider.chat.history.md``.
        max_lines: Stop after this many lines (used by smoke tests).

    Returns:
        :class:`Session` with ``source='aider'``.
    """
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    if max_lines is not None:
        lines = lines[:max_lines]

    messages: list[Message] = []
    tool_calls: list[ToolCall] = []
    started_at = None
    current_role = "assistant"  # default — text before first prompt is preamble
    buffer: list[str] = []
    in_fence = False
    fence_filename: str | None = None
    fence_buffer: list[str] = []
    edit_index = 0

    def flush_message() -> None:
        if buffer:
            joined = "\n".join(buffer).strip()
            if joined:
                messages.append(Message(role=current_role, content=joined))
            buffer.clear()

    for line in lines:
        header_match = _SESSION_HEADER_RE.match(line)
        if header_match:
            flush_message()
            ts_value = parse_iso8601(header_match.group("ts").strip())
            if ts_value is not None and started_at is None:
                started_at = ts_value
            continue

        if _FENCE_RE.match(line):
            if not in_fence:
                in_fence = True
                # The previous non-empty line may name the target file.
                fence_filename = _peek_filename(buffer)
                fence_buffer = []
            else:
                in_fence = False
                if fence_filename:
                    edit_index += 1
                    tool_calls.append(
                        ToolCall(
                            id=f"aider-edit-{edit_index}",
                            name="Edit",
                            arguments={
                                "file_path": fence_filename,
                                "patch": "\n".join(fence_buffer),
                            },
                        )
                    )
                # Always preserve the fence content in the rendered text
                # so downstream metrics that look for SEARCH/REPLACE markers
                # still find them.
                buffer.append("```")
                buffer.extend(fence_buffer)
                buffer.append("```")
                fence_filename = None
                fence_buffer = []
            continue

        if in_fence:
            fence_buffer.append(line)
            continue

        prompt_match = _USER_PROMPT_RE.match(line)
        if prompt_match:
            flush_message()
            current_role = "user"
            buffer.append(prompt_match.group(1))
            continue

        if current_role == "user" and line.strip() == "":
            flush_message()
            current_role = "assistant"
            continue

        buffer.append(line)

    flush_message()

    return Session(
        id=p.stem,
        source="aider",
        messages=messages,
        tool_calls=tool_calls,
        started_at=started_at,
        raw_path=str(p),
        metadata={"parser_confidence": "medium"},
    )


def _peek_filename(buffer: list[str]) -> str | None:
    """Walk backwards through the assistant buffer to find the most recent
    filename-like line, which Aider uses to label the target of an edit."""
    for line in reversed(buffer):
        stripped = line.strip()
        if not stripped:
            continue
        if _FILENAME_HINT_RE.match(stripped):
            return stripped
        # Stop scanning once we hit a non-blank, non-filename line so we do
        # not bind to something far up the document.
        return None
    return None
