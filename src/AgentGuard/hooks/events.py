"""Canonical Claude Code hook lifecycle event types (per research §2.3).

Twelve events fire across the agent loop. Per-event default field sets are
kept here so :func:`AgentGuard.hooks.envelope.synthesize_envelope` can fill in
just the keys Claude Code actually sends for that event (e.g. ``tool_name``
only matters for ``PreToolUse``/``PostToolUse``/``PostToolUseFailure``).
"""

from __future__ import annotations

from enum import StrEnum


class HookEvent(StrEnum):
    """The 12 Claude Code hook lifecycle events."""

    USER_PROMPT_SUBMIT = "UserPromptSubmit"
    USER_PROMPT_EXPANSION = "UserPromptExpansion"
    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    POST_TOOL_USE_FAILURE = "PostToolUseFailure"
    POST_TOOL_BATCH = "PostToolBatch"
    NOTIFICATION = "Notification"
    STOP = "Stop"
    SUBAGENT_STOP = "SubagentStop"
    PRE_COMPACT = "PreCompact"
    SESSION_START = "SessionStart"
    CONFIG_CHANGE = "ConfigChange"

    @classmethod
    def parse(cls, value: str | HookEvent) -> HookEvent:
        """Coerce a free-form string into a HookEvent; raise on unknown."""
        if isinstance(value, cls):
            return value
        # Allow case-insensitive lookup for Robot Framework friendliness
        wanted = str(value).strip()
        for ev in cls:
            if ev.value == wanted or ev.value.lower() == wanted.lower():
                return ev
        raise ValueError(f"Unknown hook event {value!r}; expected one of {', '.join(e.value for e in cls)}.")


# ---------------------------------------------------------------------------
# Per-event field sets — what Claude Code actually puts on stdin for each
# event. Used by ``synthesize_envelope`` to omit irrelevant defaults.
# ---------------------------------------------------------------------------

# Fields every event carries.
_BASE_FIELDS: frozenset[str] = frozenset({"session_id", "transcript_path", "cwd", "hook_event_name"})

EVENT_FIELDS: dict[HookEvent, frozenset[str]] = {
    HookEvent.USER_PROMPT_SUBMIT: _BASE_FIELDS | {"prompt"},
    HookEvent.USER_PROMPT_EXPANSION: _BASE_FIELDS | {"prompt", "expanded_prompt"},
    HookEvent.PRE_TOOL_USE: _BASE_FIELDS | {"tool_name", "tool_input"},
    HookEvent.POST_TOOL_USE: _BASE_FIELDS | {"tool_name", "tool_input", "tool_response"},
    HookEvent.POST_TOOL_USE_FAILURE: _BASE_FIELDS | {"tool_name", "tool_input", "tool_response", "error"},
    HookEvent.POST_TOOL_BATCH: _BASE_FIELDS | {"tool_calls"},
    HookEvent.NOTIFICATION: _BASE_FIELDS | {"message"},
    HookEvent.STOP: _BASE_FIELDS | {"stop_hook_active"},
    HookEvent.SUBAGENT_STOP: _BASE_FIELDS | {"stop_hook_active", "subagent_id"},
    HookEvent.PRE_COMPACT: _BASE_FIELDS | {"trigger", "custom_instructions"},
    HookEvent.SESSION_START: _BASE_FIELDS | {"source"},
    HookEvent.CONFIG_CHANGE: _BASE_FIELDS | {"changes"},
}


__all__ = ["HookEvent", "EVENT_FIELDS"]
