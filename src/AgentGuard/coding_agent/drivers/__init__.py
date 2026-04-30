"""CodingAgentDriver protocol + per-CLI subprocess wrappers (ADR-009).

Public surface:

- :class:`CodingAgentDriver` (Protocol), :class:`DriverConfig`, :class:`DriverResult`
- :class:`LocalDriver` — always-runnable OpenRouter-backed synthetic ReAct loop.
- :class:`ClaudeCodeDriver`, :class:`CodexDriver`, :class:`AiderDriver`,
  :class:`OpenCodeDriver` — subprocess wrappers (skipped when CLI absent).
- :class:`ClineDriver`, :class:`ContinueDriver`, :class:`CopilotDriver` —
  Phase-4 stubs; always report ``is_available() is False``.
- :func:`get_driver`, :func:`available_drivers`, :func:`registered_drivers`,
  :data:`DRIVERS` — factory + introspection helpers.
- Exceptions: :class:`DriverError`, :class:`DriverUnavailable`,
  :class:`DriverTimeout`, :class:`DriverInvocationError`.
"""

from AgentGuard.coding_agent.drivers.aider import AiderDriver
from AgentGuard.coding_agent.drivers.base import (
    CodingAgentDriver,
    DriverConfig,
    DriverResult,
)
from AgentGuard.coding_agent.drivers.claude_code import ClaudeCodeDriver
from AgentGuard.coding_agent.drivers.cline import ClineDriver
from AgentGuard.coding_agent.drivers.codex import CodexDriver
from AgentGuard.coding_agent.drivers.continue_ import ContinueDriver
from AgentGuard.coding_agent.drivers.copilot import CopilotDriver
from AgentGuard.coding_agent.drivers.exceptions import (
    DriverError,
    DriverInvocationError,
    DriverTimeout,
    DriverUnavailable,
)
from AgentGuard.coding_agent.drivers.local import LocalDriver
from AgentGuard.coding_agent.drivers.opencode import OpenCodeDriver
from AgentGuard.coding_agent.drivers.registry import (
    DRIVERS,
    available_drivers,
    get_driver,
    registered_drivers,
)

__all__ = [
    # Protocol + value objects
    "CodingAgentDriver",
    "DriverConfig",
    "DriverResult",
    # Drivers
    "LocalDriver",
    "ClaudeCodeDriver",
    "CodexDriver",
    "AiderDriver",
    "OpenCodeDriver",
    "ClineDriver",
    "ContinueDriver",
    "CopilotDriver",
    # Registry
    "DRIVERS",
    "get_driver",
    "available_drivers",
    "registered_drivers",
    # Exceptions
    "DriverError",
    "DriverUnavailable",
    "DriverTimeout",
    "DriverInvocationError",
]
