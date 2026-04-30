"""Unit tests for the secondary (low-confidence) Codex + OpenCode JSONL
parsers.

Both schemas are not yet pinned upstream; the parsers are best-effort field
walks that record every top-level key into ``Session.metadata`` so callers
can validate coverage. We test the load-bearing behaviours: usage
aggregation, tool-call recovery, role-based message creation, and graceful
degradation on unknown shapes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

try:
    from AgentGuard.coding_agent.session import codex, opencode
except ImportError:  # pragma: no cover — Phase 3 race
    pytest.skip("phase3: codex/opencode parsers not yet implemented", allow_module_level=True)

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "coding_agent" / "sessions"


def _write(tmp_path: Path, records: list[dict[str, Any]]) -> Path:
    p = tmp_path / "session.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return p


# ---------------------------- codex ----------------------------------------


def test_codex_parse_minimal_fixture() -> None:
    s = codex.parse(FIXTURES / "codex_minimal.jsonl")
    assert s.source == "codex"
    assert s.metadata.get("parser_confidence") == "low"
    assert "raw_top_level_keys" in s.metadata


def test_codex_user_role_record_becomes_message(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        [{"role": "user", "content": "do the thing", "session_id": "s1"}],
    )
    s = codex.parse(p)
    assert any(m.role == "user" and "do the thing" in m.content for m in s.messages)


def test_codex_inline_tool_calls_extracted(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        [
            {
                "role": "assistant",
                "session_id": "s1",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "search",
                            "arguments": json.dumps({"q": "abc"}),
                        },
                    }
                ],
            }
        ],
    )
    s = codex.parse(p)
    assert len(s.tool_calls) == 1
    assert s.tool_calls[0].name == "search"
    assert s.tool_calls[0].arguments == {"q": "abc"}


def test_codex_tool_role_message_becomes_response(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        [
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "content": "result",
                "session_id": "s1",
            }
        ],
    )
    s = codex.parse(p)
    assert len(s.tool_responses) == 1
    assert s.tool_responses[0].tool_call_id == "call_1"


def test_codex_invalid_arguments_falls_back_to_raw(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        [
            {
                "role": "assistant",
                "session_id": "s1",
                "tool_calls": [
                    {"id": "c1", "function": {"name": "f", "arguments": "not-json"}}
                ],
            }
        ],
    )
    s = codex.parse(p)
    assert s.tool_calls[0].arguments == {"_raw": "not-json"}


def test_codex_session_id_captured_from_first_record(tmp_path: Path) -> None:
    p = _write(tmp_path, [{"role": "user", "content": "hi", "session_id": "abc-123"}])
    s = codex.parse(p)
    assert s.id == "abc-123"


def test_codex_max_lines_respected(tmp_path: Path) -> None:
    p = _write(tmp_path, [{"role": "user", "content": str(i), "session_id": "s"} for i in range(5)])
    s = codex.parse(p, max_lines=2)
    assert len(s.messages) <= 2


def test_codex_unknown_id_returns_unknown(tmp_path: Path) -> None:
    p = _write(tmp_path, [{"role": "user", "content": "hi"}])
    s = codex.parse(p)
    assert s.id == "unknown"


def test_codex_skips_non_dict_records(tmp_path: Path) -> None:
    p = tmp_path / "weird.jsonl"
    p.write_text(
        json.dumps({"role": "user", "content": "ok", "session_id": "s"})
        + "\n"
        + json.dumps([1, 2])
        + "\n"
    )
    s = codex.parse(p)
    assert s.id == "s"


# ---------------------------- opencode -------------------------------------


def test_opencode_parse_marks_low_confidence(tmp_path: Path) -> None:
    p = _write(tmp_path, [{"role": "user", "content": "hi", "session_id": "x"}])
    s = opencode.parse(p)
    assert s.source == "opencode"
    assert s.metadata.get("parser_confidence") == "low"


def test_opencode_user_message_extraction(tmp_path: Path) -> None:
    p = _write(tmp_path, [{"role": "user", "text": "do it", "id": "abc"}])
    s = opencode.parse(p)
    assert any("do it" in m.content for m in s.messages if m.role == "user")
    assert s.id == "abc"


def test_opencode_tool_call_extracted(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        [
            {
                "role": "assistant",
                "session_id": "s",
                "tool_calls": [
                    {
                        "id": "call_X",
                        "function": {"name": "search", "arguments": {"q": "yes"}},
                    }
                ],
            }
        ],
    )
    s = opencode.parse(p)
    assert len(s.tool_calls) == 1
    assert s.tool_calls[0].name == "search"


def test_opencode_tool_response_extracted(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        [
            {
                "role": "tool",
                "tool_call_id": "abc",
                "content": "ok",
                "session_id": "s",
            }
        ],
    )
    s = opencode.parse(p)
    assert len(s.tool_responses) == 1


def test_opencode_records_top_level_keys(tmp_path: Path) -> None:
    p = _write(tmp_path, [{"role": "user", "content": "x", "session_id": "s", "extra": 1}])
    s = opencode.parse(p)
    keys = s.metadata["raw_top_level_keys"]
    assert "extra" in keys


def test_opencode_skips_non_dict(tmp_path: Path) -> None:
    p = tmp_path / "weird.jsonl"
    p.write_text(
        json.dumps({"role": "user", "content": "ok", "session_id": "s"})
        + "\n"
        + json.dumps("string-line")
        + "\n"
    )
    s = opencode.parse(p)
    assert s.id == "s"


def test_opencode_max_lines_respected(tmp_path: Path) -> None:
    p = _write(tmp_path, [{"role": "user", "content": str(i), "session_id": "s"} for i in range(5)])
    s = opencode.parse(p, max_lines=2)
    assert len(s.messages) <= 2
