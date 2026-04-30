"""Helpers shared by every vendor parser.

Keeping these tight means each parser stays small and focused on
walking-and-pairing logic, not formatting trivia.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .types import Usage

__all__ = [
    "parse_iso8601",
    "coerce_content",
    "extract_message_text",
    "extract_usage",
]


def parse_iso8601(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp; return ``None`` if missing or unparseable.

    Accepts the trailing ``Z`` notation Claude Code emits. Anything we cannot
    decode returns ``None`` rather than raising — sessions in the wild
    occasionally include ``timestamp: ""`` for synthetic snapshot records.
    """
    if not value or not isinstance(value, str):
        return None
    try:
        # ``fromisoformat`` accepts ``+00:00`` natively; map ``Z`` first.
        cleaned = value.rstrip()
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        dt = datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    # Force tz-aware UTC so timestamp arithmetic in metrics is well-defined.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def coerce_content(parts: Any) -> str | list[dict[str, Any]]:
    """Normalise a vendor ``message.content`` field into the shape
    :class:`AgentGuard.coding_agent.session.types.Message` expects.

    Strings pass through unchanged. Lists of dicts pass through.
    Anything else is rendered to ``str()`` so the dataclass invariant holds.
    """
    if isinstance(parts, str):
        return parts
    if isinstance(parts, list):
        out: list[dict[str, Any]] = []
        for part in parts:
            if isinstance(part, dict):
                out.append(part)
            else:
                out.append({"type": "text", "text": str(part)})
        return out
    return str(parts)


def extract_message_text(record: dict[str, Any]) -> str:
    """Pull plain text out of a single record's ``message.content`` blocks.

    Used by the auto-detect dispatcher to peek at the shape without building
    a full :class:`Message`.
    """
    msg = record.get("message")
    if not isinstance(msg, dict):
        return ""
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    pieces: list[str] = []
    for part in content:
        if isinstance(part, dict) and part.get("type") == "text":
            text = part.get("text")
            if isinstance(text, str):
                pieces.append(text)
    return "\n".join(pieces)


def extract_usage(message: dict[str, Any] | None) -> Usage:
    """Build a :class:`Usage` from a single ``assistant.message.usage`` block.

    Anthropic's keys: ``input_tokens``, ``output_tokens``,
    ``cache_creation_input_tokens``, ``cache_read_input_tokens``.
    OpenAI-style keys (``prompt_tokens`` / ``completion_tokens``) are also
    accepted for forward-compat with non-Anthropic backends.
    """
    if not isinstance(message, dict):
        return Usage()
    usage = message.get("usage")
    if not isinstance(usage, dict):
        return Usage()
    return Usage(
        prompt_tokens=int(
            usage.get("input_tokens") or usage.get("prompt_tokens") or 0
        ),
        completion_tokens=int(
            usage.get("output_tokens") or usage.get("completion_tokens") or 0
        ),
        cache_read_tokens=int(usage.get("cache_read_input_tokens") or 0),
        cache_write_tokens=int(usage.get("cache_creation_input_tokens") or 0),
        cost_usd=_safe_float(usage.get("cost_usd")),
    )


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
