"""``continue`` workspace-based driver — Phase-4 stub (ADR-009).

Module is named ``continue_.py`` because ``continue`` is a Python keyword.
The registry maps the public driver name ``"continue"`` to this class.
"""

from __future__ import annotations

from AgentGuard.coding_agent.drivers.base import DriverConfig, DriverResult
from AgentGuard.coding_agent.drivers.exceptions import DriverUnavailable


class ContinueDriver:
    """Phase-4 placeholder for the Continue workspace-based driver."""

    name: str = "continue"

    def is_available(self) -> bool:
        return False

    def run(
        self,
        prompt: str,
        config: DriverConfig | None = None,
    ) -> DriverResult:
        raise DriverUnavailable("Phase 4 — workspace-based Continue driver pending implementation.")


__all__ = ["ContinueDriver"]
