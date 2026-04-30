"""Framework bridges to LangGraph / CrewAI / AutoGen / OpenAI Agents SDK.

Each bridge is lazy-imported so missing optional deps don't break library import.
The public surface is the :class:`FrameworkBridge` Protocol plus the
:func:`get_bridge` / :func:`available_bridges` registry helpers.
"""

from AgentGuard.subagents.bridges.autogen_bridge import AutoGenBridge
from AgentGuard.subagents.bridges.base import (
    BridgeUnavailable,
    FrameworkBridge,
)
from AgentGuard.subagents.bridges.crewai_bridge import CrewAIBridge
from AgentGuard.subagents.bridges.langgraph_bridge import LangGraphBridge
from AgentGuard.subagents.bridges.openai_agents_bridge import OpenAIAgentsBridge
from AgentGuard.subagents.bridges.registry import (
    BRIDGES,
    available_bridges,
    get_bridge,
)

__all__ = [
    "BRIDGES",
    "AutoGenBridge",
    "BridgeUnavailable",
    "CrewAIBridge",
    "FrameworkBridge",
    "LangGraphBridge",
    "OpenAIAgentsBridge",
    "available_bridges",
    "get_bridge",
]
