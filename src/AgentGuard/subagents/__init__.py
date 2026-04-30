"""SubAgents bounded context — A2A 1.0 lifecycle + framework bridges (ADR-008).

Public surface lives in :mod:`AgentGuard.subagents.library` (SubAgentsKeywords).
Re-exports the most commonly imported types so suites can do
``from AgentGuard.subagents import AgentCard, Task`` without digging into
``types.py``.
"""

from AgentGuard.subagents.exceptions import (
    AgentCardInvalid,
    SubAgentError,
    TaskFailed,
    TaskTimeout,
    TransportError,
)
from AgentGuard.subagents.types import (
    AgentCard,
    AgentSkill,
    Artifact,
    DelegationChain,
    DelegationLink,
    Message,
    MessagePart,
    Task,
    TaskStatus,
    artifact_text,
    text_artifact,
)

__all__ = [
    "AgentCard",
    "AgentCardInvalid",
    "AgentSkill",
    "Artifact",
    "DelegationChain",
    "DelegationLink",
    "Message",
    "MessagePart",
    "SubAgentError",
    "Task",
    "TaskFailed",
    "TaskStatus",
    "TaskTimeout",
    "TransportError",
    "artifact_text",
    "text_artifact",
]
