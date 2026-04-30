"""Duck-typed Session protocol — used until the parser agent lands the real
:class:`AgentGuard.coding_agent.session.types.Session`.

Runtime always imports the concrete dataclass; the protocol only exists to
keep ``mypy --strict`` happy when callers stub a Session in unit tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover
    from AgentGuard.coding_agent.session.types import Session as _RealSession  # noqa: F401


@runtime_checkable
class SessionLike(Protocol):
    """Minimal surface every metric calculator needs."""

    id: str
    messages: list[Any]
    tool_calls: list[Any]
    tool_responses: list[Any]
    interrupts: list[Any]
    hook_events: list[Any]
    usage: Any

    def text(self) -> str: ...
