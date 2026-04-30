"""Driver registry — name → class factory (ADR-009).

Public entry points used by :mod:`AgentGuard.coding_agent.library`:

- :func:`get_driver(name, **kwargs)` — instantiate by short name.
- :func:`available_drivers()` — list of names whose ``is_available()`` is True.
- :func:`registered_drivers()` — every known name (incl. unavailable stubs).
"""

from __future__ import annotations

import logging
from typing import Any

from AgentGuard.coding_agent.drivers.aider import AiderDriver
from AgentGuard.coding_agent.drivers.base import CodingAgentDriver
from AgentGuard.coding_agent.drivers.claude_code import ClaudeCodeDriver
from AgentGuard.coding_agent.drivers.cline import ClineDriver
from AgentGuard.coding_agent.drivers.codex import CodexDriver
from AgentGuard.coding_agent.drivers.continue_ import ContinueDriver
from AgentGuard.coding_agent.drivers.copilot import CopilotDriver
from AgentGuard.coding_agent.drivers.local import LocalDriver
from AgentGuard.coding_agent.drivers.opencode import OpenCodeDriver

logger = logging.getLogger("AgentGuard.coding_agent.drivers.registry")

DRIVERS: dict[str, type[Any]] = {
    "local": LocalDriver,
    "claude-code": ClaudeCodeDriver,
    "codex": CodexDriver,
    "aider": AiderDriver,
    "opencode": OpenCodeDriver,
    "cline": ClineDriver,
    "continue": ContinueDriver,
    "copilot": CopilotDriver,
}


def _normalise(name: str) -> str:
    return (name or "").strip().lower().replace("_", "-")


def get_driver(name: str, **kwargs: Any) -> CodingAgentDriver:
    """Instantiate the driver registered under ``name``.

    ``kwargs`` are forwarded to the constructor (e.g. ``provider=`` for
    :class:`LocalDriver`). Raises :class:`ValueError` for unknown names.
    """
    key = _normalise(name)
    cls = DRIVERS.get(key)
    if cls is None:
        choices = ", ".join(sorted(DRIVERS))
        raise ValueError(f"Unknown coding-agent driver {name!r}. Choose from: {choices}.")
    return cls(**kwargs)  # type: ignore[no-any-return]


def registered_drivers() -> list[str]:
    """Return every known driver name (alphabetised)."""
    return sorted(DRIVERS)


def available_drivers() -> list[str]:
    """Return only drivers whose ``is_available()`` reports True in this env."""
    out: list[str] = []
    for name, cls in DRIVERS.items():
        try:
            if cls().is_available():
                out.append(name)
        except Exception as exc:  # noqa: BLE001 — never propagate from a probe
            logger.debug("driver %s probe raised: %s", name, exc)
    return sorted(out)


__all__ = [
    "DRIVERS",
    "get_driver",
    "registered_drivers",
    "available_drivers",
]
