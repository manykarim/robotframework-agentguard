"""Integration tests — top-level Library composes all 6 sub-libraries cleanly."""

from __future__ import annotations

import pytest

from AgentGuard import AgentGuard


def test_top_level_library_loads_all_components() -> None:
    ag = AgentGuard(provider="mock")
    info = ag.get_agentguard_info()
    expected = {
        "MCPKeywords",
        "SkillsKeywords",
        "ToolCallKeywords",
        "StatsKeywords",
        "JudgeKeywords",
        "SecurityKeywords",
    }
    assert expected.issubset(set(info["components"]))


def test_top_level_library_exposes_mcp_keywords() -> None:
    ag = AgentGuard(provider="mock")
    for kw in ("Start MCP Server", "List MCP Tools", "Call MCP Tool"):
        assert kw in dir(ag), f"missing {kw}"


def test_top_level_library_exposes_stats_keywords() -> None:
    ag = AgentGuard(provider="mock")
    for kw in ("Mann Whitney U Should Show Improvement", "Bootstrap Confidence Interval", "Pass At K Should Be Above"):
        assert kw in dir(ag), f"missing {kw}"


def test_top_level_library_exposes_security_keywords() -> None:
    ag = AgentGuard(provider="mock")
    for kw in ("Scan Skill", "Redact Trajectory", "AIDefence Should Find No Injection"):
        assert kw in dir(ag), f"missing {kw}"


def test_top_level_library_keyword_count_at_least_50() -> None:
    ag = AgentGuard(provider="mock")
    title_case = [k for k in dir(ag) if not k.startswith("_") and " " in k]
    assert len(title_case) >= 50, f"only {len(title_case)} Title-Case keywords"


@pytest.mark.parametrize(
    "transport",
    ["auto", "memory", "stdio", "http", "sse"],
)
def test_library_accepts_transport_string(transport: str) -> None:
    ag = AgentGuard(provider="mock", transport=transport)
    assert ag.get_agentguard_info()["transport"] == transport
