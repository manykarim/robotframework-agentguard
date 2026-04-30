"""``cline`` workspace-based driver — Phase-4 stub (ADR-009).

Cline is an IDE-extension agent; it persists session state into the workspace
``.cline/`` directory rather than offering a stable headless CLI. A
workspace-aware driver lands in Phase 4. For Phase 3 we publish the class so
``available_drivers()`` shows it as known-but-unavailable.
"""

from __future__ import annotations

from AgentGuard.coding_agent.drivers.base import DriverConfig, DriverResult
from AgentGuard.coding_agent.drivers.exceptions import DriverUnavailable


class ClineDriver:
    """Phase-4 placeholder for the Cline workspace-based driver."""

    name: str = "cline"

    def is_available(self) -> bool:
        return False

    def run(
        self,
        prompt: str,
        config: DriverConfig | None = None,
    ) -> DriverResult:
        raise DriverUnavailable(
            "Phase 4 — workspace-based Cline driver pending implementation."
        )


__all__ = ["ClineDriver"]
