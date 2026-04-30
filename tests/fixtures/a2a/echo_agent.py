"""In-process A2A "echo" agent fixture.

Used by SubAgents unit tests to exercise the lifecycle without a network.
"""

from __future__ import annotations

from typing import Any

from AgentGuard.subagents.a2a_server import ServerHandle, start_server


def make_echo_agent(name: str = "echo-agent") -> ServerHandle:
    """Register an in-process A2A agent that echoes its input back as text."""

    def _echo(message: str | dict[str, Any]) -> str:
        if isinstance(message, dict):
            return str(message.get("text", message))
        return str(message)

    return start_server(
        name,
        _echo,
        description="Echoes incoming message text into a single text artifact.",
        skills=[
            {
                "id": "echo.text",
                "name": "echo.text",
                "description": "Repeat the incoming text verbatim.",
                "tags": ["debug", "test"],
                "examples": ["echo hello world", "say back: foo"],
            }
        ],
        overwrite=True,
    )


__all__ = ["make_echo_agent"]
