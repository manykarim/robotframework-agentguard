"""Unit tests for `AgentGuard.coding_agent.session.claude_code` — the
canonical Claude Code JSONL parser (research §6.5 / exp_07).

These pin the load-bearing behaviours: top-level fields are derived from
``message.content[]`` walks, ``toolUseResult`` is paired via either
``tool_use_id`` (modern) or ``parentUuid`` chain (legacy), interrupts come
from both ``permission-mode`` records and the literal text marker, and
hook-lifecycle records land in ``Session.hook_events``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

try:
    from AgentGuard.coding_agent.session.claude_code import parse
    from AgentGuard.coding_agent.session.exceptions import MalformedSessionError
except ImportError:  # pragma: no cover — Phase 3 race
    pytest.skip("phase3: session.claude_code not yet implemented", allow_module_level=True)

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "coding_agent" / "sessions"


def _write(tmp_path: Path, records: list[dict[str, Any]]) -> Path:
    p = tmp_path / "session.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return p


# ---------------------------- bundled fixtures ----------------------------


def test_parse_minimal_fixture() -> None:
    s = parse(FIXTURES / "claude_code_minimal.jsonl")
    assert s.id == "synthetic-min-001"
    assert s.source == "claude-code"
    assert len(s.messages) >= 4
    assert len(s.tool_calls) == 0


def test_parse_with_tools_fixture() -> None:
    s = parse(FIXTURES / "claude_code_with_tools.jsonl")
    assert len(s.tool_calls) > 0
    assert len(s.tool_responses) > 0
    # paired ratio > 0 — the parser must successfully resolve at least one
    # toolUseResult back to its originating tool_use.
    paired = sum(1 for tr in s.tool_responses if tr.tool_call_id)
    assert paired > 0


def test_parse_with_interrupts_fixture() -> None:
    s = parse(FIXTURES / "claude_code_with_interrupts.jsonl")
    assert len(s.interrupts) > 0
    # One should be from the permission_mode transition, one from the literal text marker.
    reasons = {iv.reason for iv in s.interrupts}
    assert any(r and r.startswith("permission_mode:") for r in reasons)
    assert "user_interrupt" in reasons


def test_parse_captures_session_metadata() -> None:
    s = parse(FIXTURES / "claude_code_with_tools.jsonl")
    assert s.cwd is not None
    assert s.metadata.get("parser_confidence") == "high"


# ---------------------------- max_lines ------------------------------------


def test_parse_respects_max_lines(tmp_path: Path) -> None:
    records: list[dict[str, Any]] = [
        {"type": "system", "sessionId": "s", "message": {"role": "system", "content": "hi"}},
        {"type": "user", "sessionId": "s", "message": {"role": "user", "content": "1"}},
        {"type": "user", "sessionId": "s", "message": {"role": "user", "content": "2"}},
        {"type": "user", "sessionId": "s", "message": {"role": "user", "content": "3"}},
    ]
    path = _write(tmp_path, records)
    s = parse(path, max_lines=2)
    # only first 2 records consumed
    assert len(s.messages) <= 2


# ---------------------------- pairing tactics ------------------------------


def test_pair_via_explicit_tool_use_id(tmp_path: Path) -> None:
    """When toolUseResult includes tool_use_id, parser uses it directly."""
    records = [
        {
            "type": "assistant",
            "uuid": "a-1",
            "sessionId": "s1",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "tu-EXPLICIT", "name": "Read", "input": {"path": "x"}}
                ],
                "usage": {"input_tokens": 5, "output_tokens": 3},
            },
        },
        {
            "type": "user",
            "uuid": "u-1",
            "parentUuid": "a-1",
            "sessionId": "s1",
            "toolUseResult": {"tool_use_id": "tu-EXPLICIT", "content": "ok"},
            "message": {"role": "user", "content": []},
        },
    ]
    s = parse(_write(tmp_path, records))
    assert len(s.tool_calls) == 1
    assert len(s.tool_responses) == 1
    assert s.tool_responses[0].tool_call_id == "tu-EXPLICIT"


def test_pair_via_parent_chain_when_id_missing(tmp_path: Path) -> None:
    records = [
        {
            "type": "assistant",
            "uuid": "a-1",
            "sessionId": "s1",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "tu-CHAIN", "name": "Read", "input": {}}
                ],
            },
        },
        {
            "type": "user",
            "uuid": "u-1",
            "parentUuid": "a-1",
            "sessionId": "s1",
            "toolUseResult": "raw string content",  # no dict, no id key
            "message": {"role": "user", "content": []},
        },
    ]
    s = parse(_write(tmp_path, records))
    assert len(s.tool_responses) == 1
    assert s.tool_responses[0].tool_call_id == "tu-CHAIN"


def test_unpaired_tool_result_is_recorded_in_metadata(tmp_path: Path) -> None:
    records = [
        {
            "type": "user",
            "uuid": "u-1",
            "parentUuid": "missing",
            "sessionId": "s1",
            "toolUseResult": "orphan",
            "message": {"role": "user", "content": []},
        }
    ]
    s = parse(_write(tmp_path, records))
    assert len(s.tool_responses) == 0
    assert s.metadata.get("unpaired_tool_results") == 1


# ---------------------------- thinking / interrupts ------------------------


def test_thinking_block_signature_length_captured(tmp_path: Path) -> None:
    records = [
        {
            "type": "assistant",
            "uuid": "a-1",
            "sessionId": "s1",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": "ponder", "signature": "x" * 16}
                ],
            },
        }
    ]
    s = parse(_write(tmp_path, records))
    assert len(s.thinking_blocks) == 1
    assert s.thinking_blocks[0].signature_length == 16


def test_interrupt_marker_in_user_message(tmp_path: Path) -> None:
    records = [
        {
            "type": "user",
            "uuid": "u-1",
            "sessionId": "s1",
            "message": {
                "role": "user",
                "content": "[Request interrupted by user]",
            },
        }
    ]
    s = parse(_write(tmp_path, records))
    assert len(s.interrupts) == 1
    assert s.interrupts[0].reason == "user_interrupt"


def test_interrupt_marker_in_assistant_text_block(tmp_path: Path) -> None:
    records = [
        {
            "type": "assistant",
            "uuid": "a-1",
            "sessionId": "s1",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Hmm. [Request interrupted by user]"}
                ],
            },
        }
    ]
    s = parse(_write(tmp_path, records))
    assert any(i.reason == "user_interrupt" for i in s.interrupts)


def test_permission_mode_emits_hook_event_and_maybe_interrupt(tmp_path: Path) -> None:
    records = [
        {
            "type": "permission-mode",
            "sessionId": "s1",
            "permissionMode": "stopped",
            "timestamp": "2026-04-29T12:00:00Z",
        },
        {
            "type": "permission-mode",
            "sessionId": "s1",
            "permissionMode": "default",
        },
    ]
    s = parse(_write(tmp_path, records))
    # Both produce hook events; only "stopped" produces an interrupt.
    assert len(s.hook_events) == 2
    assert sum(1 for ev in s.hook_events if ev.event == "PermissionMode") == 2
    assert any(i.reason == "permission_mode:stopped" for i in s.interrupts)


def test_hook_lifecycle_event_recorded(tmp_path: Path) -> None:
    records = [
        {
            "type": "Stop",
            "sessionId": "s1",
            "decision": "block",
            "timestamp": "2026-04-29T12:00:00Z",
        }
    ]
    s = parse(_write(tmp_path, records))
    assert any(
        ev.event == "Stop" and ev.decision == "block" for ev in s.hook_events
    )


def test_usage_aggregates_across_assistant_records(tmp_path: Path) -> None:
    records = [
        {
            "type": "assistant",
            "uuid": "a-1",
            "sessionId": "s1",
            "message": {"usage": {"input_tokens": 5, "output_tokens": 3}, "content": []},
        },
        {
            "type": "assistant",
            "uuid": "a-2",
            "sessionId": "s1",
            "message": {"usage": {"input_tokens": 7, "output_tokens": 11}, "content": []},
        },
    ]
    s = parse(_write(tmp_path, records))
    assert s.usage.prompt_tokens == 12
    assert s.usage.completion_tokens == 14


def test_started_and_ended_at_track_extreme_timestamps(tmp_path: Path) -> None:
    records = [
        {
            "type": "user",
            "uuid": "u-1",
            "sessionId": "s1",
            "timestamp": "2026-04-29T10:00:00Z",
            "message": {"role": "user", "content": "first"},
        },
        {
            "type": "user",
            "uuid": "u-2",
            "sessionId": "s1",
            "timestamp": "2026-04-29T11:00:00Z",
            "message": {"role": "user", "content": "second"},
        },
    ]
    s = parse(_write(tmp_path, records))
    assert s.started_at is not None and s.ended_at is not None
    assert s.started_at <= s.ended_at


def test_non_dict_records_are_skipped(tmp_path: Path) -> None:
    p = tmp_path / "weird.jsonl"
    # second line is a JSON list, not a dict — the parser must skip it.
    p.write_text(
        json.dumps({"type": "system", "sessionId": "s", "message": {"role": "system", "content": "x"}})
        + "\n"
        + json.dumps([1, 2, 3])
        + "\n"
    )
    s = parse(p)
    assert s.id == "s"


def test_unknown_session_id_returns_unknown(tmp_path: Path) -> None:
    p = _write(tmp_path, [{"type": "system", "message": {"role": "system", "content": "x"}}])
    s = parse(p)
    assert s.id == "unknown"


def test_malformed_jsonl_raises(tmp_path: Path) -> None:
    p = tmp_path / "bad.jsonl"
    p.write_text("{this is not json}\n")
    with pytest.raises(MalformedSessionError):
        parse(p)
