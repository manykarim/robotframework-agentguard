"""Unit tests for `AgentGuard.coding_agent.session.aider` (markdown parser).

Aider sessions are markdown chat-history files; the parser uses simple block
heuristics to recover :class:`Session` shape. These tests pin those heuristics.
"""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    from AgentGuard.coding_agent.session.aider import parse
except ImportError:  # pragma: no cover — Phase 3 race
    pytest.skip("phase3: session.aider not yet implemented", allow_module_level=True)

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "coding_agent" / "sessions"


def test_parse_aider_minimal_fixture() -> None:
    s = parse(FIXTURES / "aider_minimal.md")
    assert s.source == "aider"
    assert s.id  # non-empty derived from filename stem


def test_parse_user_prompts_extracted(tmp_path: Path) -> None:
    md = "# aider chat started at 2026-04-29T10:00:00Z\n\n#### make a fix\n\nHere is what I'll do.\n"
    p = tmp_path / "history.md"
    p.write_text(md)
    s = parse(p)
    user_msgs = [m for m in s.messages if m.role == "user"]
    assert any("make a fix" in (m.content if isinstance(m.content, str) else "") for m in user_msgs)


def test_parse_recognises_fenced_edit_block(tmp_path: Path) -> None:
    md = (
        "# aider chat started at 2026-04-29T10:00:00Z\n\n"
        "#### add hello\n\n"
        "Here:\n\n"
        "src/foo.py\n"
        "```\n"
        "def hello():\n    return 'hi'\n"
        "```\n"
    )
    p = tmp_path / "h.md"
    p.write_text(md)
    s = parse(p)
    edits = [tc for tc in s.tool_calls if tc.name == "Edit"]
    assert edits, "Expected at least one synthetic Edit tool_call from fenced block"
    assert edits[0].arguments.get("file_path") == "src/foo.py"


def test_parse_marks_low_or_medium_confidence(tmp_path: Path) -> None:
    p = tmp_path / "tiny.md"
    p.write_text("just a note\n")
    s = parse(p)
    assert s.metadata.get("parser_confidence") in {"low", "medium"}


def test_parse_respects_max_lines(tmp_path: Path) -> None:
    md = "\n".join(
        ["# aider chat started at 2026-04-29T10:00:00Z"]
        + [f"#### prompt {i}" for i in range(20)]
    )
    p = tmp_path / "h.md"
    p.write_text(md)
    s_full = parse(p)
    s_clipped = parse(p, max_lines=3)
    assert len(s_full.messages) >= len(s_clipped.messages)


def test_parse_session_started_at_from_header(tmp_path: Path) -> None:
    md = "# aider chat started at 2026-04-29T10:00:00Z\n\n#### prompt\n\nresponse\n"
    p = tmp_path / "h.md"
    p.write_text(md)
    s = parse(p)
    assert s.started_at is not None
    assert s.started_at.year == 2026
