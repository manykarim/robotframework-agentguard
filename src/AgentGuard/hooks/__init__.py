"""Hooks bounded context — synthesise + drive the 12 Claude Code hook events.

Public surface lives in :mod:`AgentGuard.hooks.library` (HooksKeywords).
The 12 lifecycle events are defined in :mod:`AgentGuard.hooks.events`, and
the 4 handler types in :mod:`AgentGuard.hooks.handlers`.

ADR-007 — `Hooks` is composed into the top-level ``AgentGuard`` library via
``DynamicCore``.
"""

from AgentGuard.hooks.events import EVENT_FIELDS, HookEvent
from AgentGuard.hooks.exceptions import (
    HookDecisionError,
    HookError,
    HookExecutionError,
    HookLoopDetected,
    HookValidationError,
)
from AgentGuard.hooks.types import (
    DecisionLiteral,
    HookDecision,
    HookEnvelope,
    HookResult,
)

__all__ = [
    "EVENT_FIELDS",
    "DecisionLiteral",
    "HookDecision",
    "HookDecisionError",
    "HookEnvelope",
    "HookError",
    "HookEvent",
    "HookExecutionError",
    "HookLoopDetected",
    "HookResult",
    "HookValidationError",
]
