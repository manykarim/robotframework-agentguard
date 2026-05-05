"""``gh copilot`` driver — Phase-4 stub (ADR-009).

GitHub Copilot CLI ships as a ``gh`` extension and does not yet emit a
machine-parseable session log. Real wrapper deferred to Phase 4.
"""

from __future__ import annotations

from AgentGuard.coding_agent.drivers.base import DriverConfig, DriverResult
from AgentGuard.coding_agent.drivers.exceptions import DriverUnavailable


class CopilotDriver:
    """Phase-4 placeholder for the ``gh copilot`` driver."""

    name: str = "copilot"

    def is_available(self) -> bool:
        return False

    def run(
        self,
        prompt: str,
        config: DriverConfig | None = None,
    ) -> DriverResult:
        raise DriverUnavailable("Phase 4 — gh-copilot driver pending implementation.")


__all__ = ["CopilotDriver"]
