"""Exception hierarchy for the SubAgents (A2A) module.

Mirrors the shape of :mod:`AgentGuard.mcp.exceptions` and
:mod:`AgentGuard.hooks.exceptions` — one base class per bounded context so
suite-level ``except`` blocks can opt into a single ancestor.

Robot Framework prints the class name in front of the message, so keep
messages short and prefix-free.
"""

from __future__ import annotations


class SubAgentError(Exception):
    """Base class for any SubAgents-module failure."""


class AgentCardInvalid(SubAgentError):  # noqa: N818 - canonical A2A term
    """An :class:`AgentCard` failed schema validation or could not be parsed.

    Raised by ``Validate Agent Card`` and by ``Get Agent Card`` when the
    fetched JSON cannot be coerced into the canonical dataclass shape.
    """


class TaskTimeout(SubAgentError):  # noqa: N818 - matches A2A spec terminology
    """``Wait For Task Completion`` exceeded its timeout budget.

    The pending :class:`AgentGuard.subagents.types.Task` is attached as
    ``self.task`` so callers can inspect the last-seen status.
    """

    def __init__(self, message: str, *, task: object | None = None) -> None:
        super().__init__(message)
        self.task = task


class TaskFailed(SubAgentError):  # noqa: N818 - matches A2A spec terminology
    """A task transitioned to a terminal failure state (failed/canceled/rejected).

    Raised by ``Task Should Have Status`` when the actual status does not
    match the expected one and is in a terminal-failure family.
    """


class TransportError(SubAgentError):
    """A2A transport could not be established or returned a wire-level error.

    Wraps httpx / a2a-sdk client errors so suites do not have to import
    third-party exception types directly.
    """


__all__ = [
    "AgentCardInvalid",
    "SubAgentError",
    "TaskFailed",
    "TaskTimeout",
    "TransportError",
]
