"""Unit tests for ``AgentGuard.coding_agent.session.parser`` — auto-detect
dispatcher that routes between vendor parsers.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

try:
    from AgentGuard.coding_agent.session import parser
    from AgentGuard.coding_agent.session.exceptions import UnknownSessionFormatError
except ImportError:  # pragma: no cover — Phase 3 race
    pytest.skip("phase3: session.parser not yet implemented", allow_module_level=True)

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "coding_agent" / "sessions"


def test_detect_claude_code_via_first_record() -> None:
    fmt = parser.detect_format(FIXTURES / "claude_code_minimal.jsonl")
    assert fmt == "claude-code"


def test_detect_aider_via_extension() -> None:
    fmt = parser.detect_format(FIXTURES / "aider_minimal.md")
    assert fmt == "aider"


def test_detect_codex_via_first_record() -> None:
    fmt = parser.detect_format(FIXTURES / "codex_minimal.jsonl")
    assert fmt in {"codex", "opencode"}  # both shapes overlap


def test_explicit_format_alias_is_normalised(tmp_path: Path) -> None:
    p = tmp_path / "x.jsonl"
    p.write_text('{"sessionId":"s","uuid":"u","type":"system","message":{"role":"system","content":"x"}}\n')
    s = parser.parse(p, format="claude")
    assert s.source == "claude-code"


def test_explicit_format_unknown_raises(tmp_path: Path) -> None:
    p = tmp_path / "x.jsonl"
    p.write_text('{"sessionId":"s","uuid":"u","type":"system","message":{"role":"system","content":"x"}}\n')
    with pytest.raises(UnknownSessionFormatError):
        parser.parse(p, format="not-a-format")


def test_unsupported_extension_raises(tmp_path: Path) -> None:
    p = tmp_path / "weird.xyz"
    p.write_text("anything\n")
    with pytest.raises(UnknownSessionFormatError):
        parser.parse(p)


def test_empty_file_raises(tmp_path: Path) -> None:
    p = tmp_path / "empty.jsonl"
    p.write_text("")
    with pytest.raises(UnknownSessionFormatError):
        parser.parse(p)


def test_invalid_first_line_raises(tmp_path: Path) -> None:
    p = tmp_path / "bad.jsonl"
    p.write_text("{this is not json}\n")
    with pytest.raises(UnknownSessionFormatError):
        parser.detect_format(p)


def test_default_to_opencode_for_generic_record(tmp_path: Path) -> None:
    """A record without claude-code or codex hints defaults to opencode."""
    p = tmp_path / "generic.jsonl"
    p.write_text(json.dumps({"foo": "bar", "id": "x"}) + "\n")
    fmt = parser.detect_format(p)
    assert fmt == "opencode"


def test_format_aliases_are_exposed() -> None:
    assert "claude" in parser.FORMAT_ALIASES
    assert parser.FORMAT_ALIASES["claude"] == "claude-code"
    assert parser.FORMAT_ALIASES["sst-opencode"] == "opencode"
