"""Registry of framework bridges — name lookup + availability filtering.

Usage::

    from AgentGuard.subagents.bridges import get_bridge, available_bridges

    bridge = get_bridge("langgraph")
    if bridge is None:
        pytest.skip("langgraph not installed")
    card = bridge.to_agent_card(my_graph)
"""

from __future__ import annotations

from AgentGuard.subagents.bridges.autogen_bridge import AutoGenBridge
from AgentGuard.subagents.bridges.base import FrameworkBridge
from AgentGuard.subagents.bridges.crewai_bridge import CrewAIBridge
from AgentGuard.subagents.bridges.langgraph_bridge import LangGraphBridge
from AgentGuard.subagents.bridges.openai_agents_bridge import OpenAIAgentsBridge

__all__ = [
    "BRIDGES",
    "available_bridges",
    "get_bridge",
]


BRIDGES: dict[str, type[FrameworkBridge]] = {
    "langgraph": LangGraphBridge,
    "crewai": CrewAIBridge,
    "autogen": AutoGenBridge,
    "openai_agents": OpenAIAgentsBridge,
}
"""Canonical name → bridge-class registry.

Names are lowercase, snake_case. ``openai_agents`` (not ``openai-agents``)
is used to match the import path of the underlying ``agents`` package.
"""


def get_bridge(name: str) -> type[FrameworkBridge] | None:
    """Return the bridge class for ``name`` iff its framework dep is installed.

    Returns ``None`` when the name is unknown *or* the framework dep is missing,
    so callers can do ``if bridge is None: pytest.skip(...)``.
    """
    bridge_cls = BRIDGES.get(name.lower().replace("-", "_"))
    if bridge_cls is None:
        return None
    if not bridge_cls.is_available():
        return None
    return bridge_cls


def available_bridges() -> list[str]:
    """Return the sorted list of bridge names whose deps are installed."""
    return sorted(name for name, cls in BRIDGES.items() if cls.is_available())
