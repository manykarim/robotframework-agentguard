"""Unit tests for ``AgentGuard.hooks.envelope`` — synthesise hook envelopes.

Covers:
* All 12 :class:`HookEvent` kinds get the right per-event default keys.
* Caller overrides win over per-event defaults.
* Unknown event names raise ``ValueError``.
* The base set (``session_id`` / ``transcript_path`` / ``cwd`` /
  ``hook_event_name``) is always present.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import pytest

from AgentGuard.hooks.envelope import synthesize_envelope
from AgentGuard.hooks.events import EVENT_FIELDS, HookEvent

BASE_KEYS = {"session_id", "transcript_path", "cwd", "hook_event_name"}


def test_envelope_base_keys_always_present() -> None:
    env = synthesize_envelope("PreToolUse", tool_name="Bash", tool_input={"command": "ls"})
    assert BASE_KEYS.issubset(env.keys())
    assert env["hook_event_name"] == "PreToolUse"


def test_envelope_session_id_default_is_uuid() -> None:
    env = synthesize_envelope("UserPromptSubmit", prompt="hi")
    # uuid.UUID will raise on a non-uuid string.
    uuid.UUID(env["session_id"])


def test_envelope_cwd_default_is_current_dir() -> None:
    env = synthesize_envelope("UserPromptSubmit", prompt="hi")
    assert env["cwd"] == os.getcwd()


def test_envelope_transcript_path_default_is_writable(tmp_path: Any) -> None:
    env = synthesize_envelope("Stop", stop_hook_active=False)
    # default transcript_path is a tempfile; it should at least exist on disk.
    assert isinstance(env["transcript_path"], str)
    assert os.path.exists(env["transcript_path"])


def test_envelope_caller_overrides_win() -> None:
    env = synthesize_envelope(
        "PreToolUse",
        tool_name="Edit",
        tool_input={"file_path": "/tmp/x"},
        session_id="fixed",
        cwd="/var/tmp",
    )
    assert env["session_id"] == "fixed"
    assert env["cwd"] == "/var/tmp"
    assert env["tool_name"] == "Edit"


def test_envelope_unknown_event_raises() -> None:
    with pytest.raises(ValueError, match="Unknown hook event"):
        synthesize_envelope("BogusEvent")


def test_envelope_accepts_hookevent_enum() -> None:
    env = synthesize_envelope(HookEvent.STOP, stop_hook_active=True)
    assert env["hook_event_name"] == "Stop"
    assert env["stop_hook_active"] is True


def test_envelope_event_name_is_case_insensitive() -> None:
    env = synthesize_envelope("pretooluse", tool_name="Bash")
    assert env["hook_event_name"] == "PreToolUse"


@pytest.mark.parametrize("event", list(HookEvent))
def test_each_event_carries_only_known_default_keys(event: HookEvent) -> None:
    """Every per-event default key must be in the event's allowed-fields set."""
    env = synthesize_envelope(event)
    allowed = EVENT_FIELDS[event]
    # All envelope keys (minus known overrides) must be a subset of allowed.
    for key in env.keys():
        assert key in allowed or key in BASE_KEYS, (
            f"Event {event!r} produced unexpected key {key!r}"
        )


def test_envelope_unknown_field_passes_through() -> None:
    """Future Claude Code keys we don't model should still survive."""
    env = synthesize_envelope("PreToolUse", tool_name="X", tool_input={}, future_field=42)
    assert env["future_field"] == 42


def test_envelope_pretooluse_defaults() -> None:
    env = synthesize_envelope("PreToolUse")
    assert env["tool_name"] == ""
    assert env["tool_input"] == {}


def test_envelope_posttoolbatch_defaults() -> None:
    env = synthesize_envelope("PostToolBatch")
    assert env["tool_calls"] == []


def test_envelope_session_start_default_source() -> None:
    env = synthesize_envelope("SessionStart")
    assert env["source"] == "startup"
