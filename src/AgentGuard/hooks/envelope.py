"""Synthesize the canonical Claude Code stdin JSON envelope.

Per research §2.3 / ADR-007 the envelope shape varies by event but always
contains a base set (``session_id``, ``transcript_path``, ``cwd``,
``hook_event_name``). This module builds that shape with sane defaults so a
Robot test author can write::

    ${env}=    Synthesize Hook Input
    ...    event=PreToolUse    tool_name=Bash    tool_input={"command": "ls"}

and get a fully populated dict.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from typing import Any

from AgentGuard.hooks.events import EVENT_FIELDS, HookEvent

# ---------------------------------------------------------------------------
# Per-event default values. Anything not provided by the caller and not in
# this dict is left out of the envelope (matches Claude Code's behaviour:
# unknown event-specific keys are simply absent).
# ---------------------------------------------------------------------------

_PER_EVENT_DEFAULTS: dict[HookEvent, dict[str, Any]] = {
    HookEvent.USER_PROMPT_SUBMIT: {"prompt": ""},
    HookEvent.USER_PROMPT_EXPANSION: {"prompt": "", "expanded_prompt": ""},
    HookEvent.PRE_TOOL_USE: {"tool_name": "", "tool_input": {}},
    HookEvent.POST_TOOL_USE: {
        "tool_name": "",
        "tool_input": {},
        "tool_response": {},
    },
    HookEvent.POST_TOOL_USE_FAILURE: {
        "tool_name": "",
        "tool_input": {},
        "tool_response": {},
        "error": "",
    },
    HookEvent.POST_TOOL_BATCH: {"tool_calls": []},
    HookEvent.NOTIFICATION: {"message": ""},
    HookEvent.STOP: {"stop_hook_active": False},
    HookEvent.SUBAGENT_STOP: {"stop_hook_active": False, "subagent_id": ""},
    HookEvent.PRE_COMPACT: {"trigger": "auto", "custom_instructions": ""},
    HookEvent.SESSION_START: {"source": "startup"},
    HookEvent.CONFIG_CHANGE: {"changes": {}},
}


def _default_transcript_path() -> str:
    """Return a tmpfile path to mimic Claude Code's transcript_path."""
    fd, path = tempfile.mkstemp(prefix="agentguard-hooks-", suffix=".jsonl")
    os.close(fd)
    return path


def synthesize_envelope(event: str | HookEvent, **fields: Any) -> dict[str, Any]:
    """Build a Claude Code hook envelope for ``event``.

    Caller-supplied ``fields`` override defaults. Unknown fields for the
    event are *kept* (so future Claude Code versions that add new keys still
    work) but the standard set is always present.

    Args:
        event: One of the 12 :class:`~AgentGuard.hooks.events.HookEvent`
            values, or its string name (case-insensitive).
        **fields: Override values for any key in the envelope.

    Returns:
        The canonical dict ready to be ``json.dumps``'d to a hook handler.

    Raises:
        ValueError: If ``event`` is not one of the 12 known events.
    """
    ev = HookEvent.parse(event)

    envelope: dict[str, Any] = {
        "session_id": fields.pop("session_id", str(uuid.uuid4())),
        "transcript_path": fields.pop(
            "transcript_path", _default_transcript_path()
        ),
        "cwd": fields.pop("cwd", os.getcwd()),
        "hook_event_name": ev.value,
    }

    # Layer in per-event defaults, only for keys the event actually carries.
    per_event = _PER_EVENT_DEFAULTS.get(ev, {})
    allowed = EVENT_FIELDS[ev]
    for key, value in per_event.items():
        if key in allowed:
            envelope[key] = value

    # Apply caller overrides (after defaults so the caller wins).
    envelope.update(fields)

    return envelope


__all__ = ["synthesize_envelope"]
