"""Exception hierarchy for the CodingAgent Robot Framework surface.

Mirrors the ``HookError`` / ``SessionParseError`` / ``DriverError`` pattern in
:mod:`AgentGuard.hooks.exceptions`, :mod:`AgentGuard.coding_agent.session
.exceptions`, and :mod:`AgentGuard.coding_agent.drivers.exceptions` so suite
authors can opt into a single base ``except`` clause.

``MetricThresholdViolated`` derives from :class:`AssertionError` so Robot
Framework's reporter renders it as a normal test failure (not a library
exception) — this matches the contract used by every other ``... Should ...``
keyword in :mod:`AgentGuard.stats.library`.
"""

from __future__ import annotations


class CodingAgentError(Exception):
    """Base class for every CodingAgent library failure."""


class DriverDispatchError(CodingAgentError):
    """``Run Coding Agent`` could not resolve / build / invoke a driver.

    Wraps :class:`AgentGuard.coding_agent.drivers.exceptions.DriverError`
    when the underlying driver subsystem rejects the request, plus the
    keyword-level missing-sibling case (``phase3 module not yet wired``).
    """


class SessionParseFailed(CodingAgentError):
    """``Parse Session JSONL`` / ``Load Session Snapshot`` could not produce a
    valid :class:`AgentGuard.coding_agent.session.types.Session`.

    Wraps :class:`AgentGuard.coding_agent.session.exceptions.SessionParseError`
    plus the JSON snapshot decode error path.
    """


class SessionSchemaInvalid(CodingAgentError):
    """``Validate Session Schema`` found a structural defect in a Session
    that is otherwise loadable (e.g. empty ``id``, no messages)."""


class MetricThresholdViolated(AssertionError):
    """A ``... Should Be Above|Below|Zero`` keyword failed its threshold check.

    Inherits from :class:`AssertionError` so Robot reports it as a normal
    test failure. Carries ``metric``, ``value``, and ``threshold`` for
    structured listeners (ADR-012).
    """

    def __init__(
        self,
        message: str,
        *,
        metric: str | None = None,
        value: float | None = None,
        threshold: float | None = None,
    ) -> None:
        super().__init__(message)
        self.metric = metric
        self.value = value
        self.threshold = threshold


__all__ = [
    "CodingAgentError",
    "DriverDispatchError",
    "SessionParseFailed",
    "SessionSchemaInvalid",
    "MetricThresholdViolated",
]
