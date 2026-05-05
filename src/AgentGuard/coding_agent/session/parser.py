"""Auto-detect dispatcher for session-JSONL parsing.

Public entry point. ``Parse Session JSONL`` (the Robot keyword) and the
``CodingAgentDriver`` machinery both call into :func:`parse` here so format
selection lives in exactly one place.

Detection precedence:

1. ``format=`` argument wins.
2. File extension ``.md`` -> aider.
3. File extension ``.jsonl`` -> peek first record; sniff Claude Code first
   (most stable schema), then Codex (``session_id`` + ``turn``-ish), then
   default to OpenCode (catch-all).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import jsonlines

from . import aider, claude_code, codex, opencode
from .exceptions import UnknownSessionFormatError
from .types import Session

__all__ = ["parse", "detect_format", "FORMAT_ALIASES"]

Format = Literal["claude-code", "codex", "aider", "opencode"]

FORMAT_ALIASES: dict[str, Format] = {
    "claude": "claude-code",
    "claude-code": "claude-code",
    "claudecode": "claude-code",
    "codex": "codex",
    "openai-codex": "codex",
    "aider": "aider",
    "opencode": "opencode",
    "sst-opencode": "opencode",
}


def parse(
    path: str | Path,
    *,
    format: str | None = None,
    max_lines: int | None = None,
) -> Session:
    """Parse a coding-agent session into a canonical :class:`Session`.

    Args:
        path: Filesystem path to the session log.
        format: Optional explicit format. When ``None``, the format is
            auto-detected; pass one of ``"claude-code"``, ``"codex"``,
            ``"aider"``, ``"opencode"`` to skip detection.
        max_lines: Optional cap forwarded to the underlying parser.

    Returns:
        A populated :class:`Session`.

    Raises:
        UnknownSessionFormatError: Auto-detection failed.
    """
    p = Path(path)
    fmt = _resolve_format(p, format)
    if fmt == "claude-code":
        return claude_code.parse(p, max_lines=max_lines)
    if fmt == "codex":
        return codex.parse(p, max_lines=max_lines)
    if fmt == "aider":
        return aider.parse(p, max_lines=max_lines)
    if fmt == "opencode":
        return opencode.parse(p, max_lines=max_lines)
    raise UnknownSessionFormatError(f"Unsupported session format: {fmt!r}")


def detect_format(path: str | Path) -> Format:
    """Public detection helper. Useful for callers that want to log the
    detected format before delegating to :func:`parse`."""
    p = Path(path)
    return _resolve_format(p, None)


def _resolve_format(p: Path, explicit: str | None) -> Format:
    if explicit is not None:
        normalised = FORMAT_ALIASES.get(explicit.lower().strip())
        if normalised is None:
            raise UnknownSessionFormatError(f"Unknown format alias: {explicit!r}")
        return normalised

    suffix = p.suffix.lower()
    if suffix == ".md":
        return "aider"
    if suffix not in {".jsonl", ".json", ".log", ""}:
        raise UnknownSessionFormatError(f"Cannot auto-detect format for {p.name!r} (extension {suffix!r})")
    return _sniff_jsonl(p)


def _sniff_jsonl(p: Path, *, max_peek: int = 5) -> Format:
    """Peek at the first ``max_peek`` non-empty records and classify.

    Per exp_07 the very first record of a Claude Code JSONL only has
    ``permissionMode/sessionId/type`` — ``uuid`` first appears on the
    second or third record. Sniffing a small window catches this.
    """
    if not p.exists():
        raise UnknownSessionFormatError(f"Cannot peek nonexistent file: {p}")
    union_keys: set[str] = set()
    seen = 0
    try:
        with jsonlines.open(p, mode="r") as reader:
            for raw in reader:
                if not isinstance(raw, dict):
                    continue
                union_keys.update(raw.keys())
                seen += 1
                if seen >= max_peek:
                    break
    except jsonlines.InvalidLineError as exc:
        raise UnknownSessionFormatError(f"First line of {p.name} is not valid JSON: {exc}") from exc
    if seen == 0:
        raise UnknownSessionFormatError(f"{p.name} contains no JSON records")
    return _classify_keys(union_keys)


def _classify_keys(keys: set[str]) -> Format:
    """Classify based on the union of top-level keys across the peek window."""
    # Claude Code: distinctive combo — sessionId + type appear on every
    # record; uuid + parentUuid appear on most (but not the very first).
    if "sessionId" in keys and "type" in keys and ("uuid" in keys or "parentUuid" in keys or "permissionMode" in keys):
        return "claude-code"
    # Codex: session_id + turn-shaped fields.
    if "session_id" in keys and ("turn" in keys or "role" in keys):
        return "codex"
    # Default catch-all so we never raise for a roughly-OpenAI-shaped log.
    return "opencode"
