"""Integration tests — full Session pipeline (parse → metric pack roundtrip).

Walks a real Claude Code JSONL fixture all the way from disk through the
parser into the #42796 metric pack so any regression in either side surfaces
as a single failure.
"""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    from AgentGuard.coding_agent.metrics.pack import compute_42796_pack
    from AgentGuard.coding_agent.metrics.types import BehavioralReport
    from AgentGuard.coding_agent.session import parser
    from AgentGuard.coding_agent.session.types import Session
except ImportError:  # pragma: no cover — Phase 3 race
    pytest.skip("phase3: coding_agent stack not yet implemented", allow_module_level=True)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "coding_agent" / "sessions"


# ---------------------------- parse roundtrip ------------------------------


def test_auto_detect_claude_code_jsonl() -> None:
    fmt = parser.detect_format(FIXTURES / "claude_code_with_tools.jsonl")
    assert fmt == "claude-code"


def test_parse_dispatches_to_claude_code() -> None:
    s = parser.parse(FIXTURES / "claude_code_with_tools.jsonl")
    assert isinstance(s, Session)
    assert s.source == "claude-code"
    assert len(s.tool_calls) > 0


def test_parse_explicit_format_overrides_detection() -> None:
    s = parser.parse(FIXTURES / "claude_code_minimal.jsonl", format="claude-code")
    assert s.id == "synthetic-min-001"


def test_parse_aider_format_via_extension() -> None:
    s = parser.parse(FIXTURES / "aider_minimal.md")
    assert s.source == "aider"


# ---------------------------- pack roundtrip -------------------------------


def test_full_pipeline_minimal_fixture() -> None:
    s = parser.parse(FIXTURES / "claude_code_minimal.jsonl")
    report = compute_42796_pack(s)
    assert isinstance(report, BehavioralReport)
    # No tool calls / no edits → most below-direction metrics pass with 0.0
    # Stop-hook violations must always be 0 in this fixture.
    assert report.metrics["stop_hook_violations"].value == 0.0


def test_full_pipeline_with_tools_fixture() -> None:
    s = parser.parse(FIXTURES / "claude_code_with_tools.jsonl")
    report = compute_42796_pack(s)
    # The fixture has both Reads and Edits; ratio must be a finite positive number.
    res = report.metrics["read_edit_ratio"]
    assert res.value > 0
    assert res.value != float("inf")


def test_full_pipeline_with_interrupts_fixture() -> None:
    s = parser.parse(FIXTURES / "claude_code_with_interrupts.jsonl")
    report = compute_42796_pack(s)
    # Interrupt-bearing fixture must register > 0 in the per-1k metric.
    assert report.metrics["user_interrupts_per_1k"].value > 0


def test_pack_report_preserves_session_id() -> None:
    s = parser.parse(FIXTURES / "claude_code_with_tools.jsonl")
    report = compute_42796_pack(s)
    assert report.session_id == s.id


def test_metric_count_is_exactly_twelve() -> None:
    s = parser.parse(FIXTURES / "claude_code_minimal.jsonl")
    report = compute_42796_pack(s)
    assert len(report.metrics) == 12
