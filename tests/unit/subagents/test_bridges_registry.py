"""Unit tests for the framework-bridge registry + lazy availability checks."""

from __future__ import annotations

from typing import Any

import pytest

from AgentGuard.subagents.bridges import BRIDGES, available_bridges, get_bridge
from AgentGuard.subagents.bridges.base import (
    BridgeUnavailable,
    FrameworkBridge,
    find_spec_any,
    make_agent_card,
    make_agent_skill,
    make_task,
)


def test_bridges_registry_keys() -> None:
    assert set(BRIDGES.keys()) == {"langgraph", "crewai", "autogen", "openai_agents"}


def test_get_bridge_unknown_returns_none() -> None:
    assert get_bridge("nope") is None


def test_get_bridge_aliases_dash_to_underscore() -> None:
    """``openai-agents`` should resolve to ``openai_agents`` entry."""
    # Without the package installed, this still returns None — but the
    # name normalisation should not raise.
    result = get_bridge("openai-agents")
    # If openai-agents is installed, we get the class; otherwise None.
    # Either is fine — we just want to confirm no exception.
    assert result is None or hasattr(result, "is_available")


def test_available_bridges_returns_list() -> None:
    available = available_bridges()
    assert isinstance(available, list)
    # Sorted guarantee
    assert available == sorted(available)


def test_find_spec_any_known_module() -> None:
    assert find_spec_any("json") is True


def test_find_spec_any_unknown() -> None:
    assert find_spec_any("nonexistent_module_xyz_123") is False


def test_find_spec_any_empty_args() -> None:
    assert find_spec_any() is False


# ---------------- A2A type construction helpers ----------------


def test_make_agent_skill_minimal() -> None:
    skill = make_agent_skill(skill_id="weather", name="Weather")
    assert skill.id == "weather"
    assert skill.name == "Weather"
    # Tags default to empty list (a2a-sdk type)
    assert hasattr(skill, "tags")


def test_make_agent_skill_with_tags() -> None:
    skill = make_agent_skill(
        skill_id="x",
        name="X",
        description="desc",
        tags=["a", "b"],
    )
    assert "a" in list(skill.tags)
    assert "b" in list(skill.tags)


def test_make_agent_card_minimal() -> None:
    card = make_agent_card(name="planner")
    assert card.name == "planner"
    assert card.version == "1.0"


def test_make_agent_card_with_skills() -> None:
    skills = [make_agent_skill(skill_id="a", name="A"), make_agent_skill(skill_id="b", name="B")]
    card = make_agent_card(name="x", skills=skills)
    assert len(list(card.skills)) == 2


def test_make_task_default_state() -> None:
    task = make_task(task_id="t1")
    assert task.id == "t1"


def test_make_task_with_metadata() -> None:
    task = make_task(task_id="t2", metadata={"key": "value"})
    assert task.id == "t2"


# ---------------- BridgeUnavailable ----------------


def test_bridge_unavailable_carries_install_hint() -> None:
    err = BridgeUnavailable("langgraph", "pip install langgraph")
    assert err.framework == "langgraph"
    assert err.install_hint == "pip install langgraph"
    assert "langgraph" in str(err)


# ---------------- LangGraphBridge (importable but not exercised) ----------------


def test_langgraph_bridge_is_available_returns_bool() -> None:
    """Just check that calling is_available() doesn't crash."""
    from AgentGuard.subagents.bridges.langgraph_bridge import LangGraphBridge

    assert isinstance(LangGraphBridge.is_available(), bool)


def test_langgraph_bridge_protocol_compliance() -> None:
    """LangGraphBridge should structurally implement FrameworkBridge."""
    from AgentGuard.subagents.bridges.langgraph_bridge import LangGraphBridge

    # The Protocol is runtime_checkable but uses static methods, so isinstance
    # may not work cleanly. Just check the surface.
    for method in ("is_available", "to_agent_card", "to_task", "extract_trajectory", "replay"):
        assert hasattr(LangGraphBridge, method)


def test_langgraph_bridge_raises_when_unavailable() -> None:
    """If langgraph isn't installed, calling to_agent_card raises."""
    from AgentGuard.subagents.bridges.langgraph_bridge import LangGraphBridge

    if LangGraphBridge.is_available():
        pytest.skip("langgraph IS installed; this test only runs without it")
    with pytest.raises(BridgeUnavailable, match="langgraph"):
        LangGraphBridge.to_agent_card(object())
