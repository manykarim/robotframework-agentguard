"""exp_13 — façade proof: does ``Library AgentGuard.<Name>`` resolve to a
PascalCase Python module that aliases the existing sub-library class?

This file is a sandbox import target — RF's library importer should pick up
the class named ``Probe`` from this module when called with
``Library tests.experiments.exp_13_facade_proof``.

Goal: demonstrate the pattern without touching ``src/`` (no implementation).
"""

from __future__ import annotations

from typing import Any

from robot.api.deco import keyword

# In real adoption this becomes:
#   from AgentGuard.mcp.library import MCPKeywords as MCP
# Here we synthesise a tiny class to prove the resolution.


class Probe:
    """Stand-in for the user-facing façade class. RF instantiates this when
    ``Library tests.experiments.exp_13_facade_proof.Probe`` (or
    ``Library tests.experiments.exp_13_facade_proof`` if RF's class-name
    matching finds ``Probe``)."""

    ROBOT_LIBRARY_SCOPE = "SUITE"

    def __init__(self, provider: Any = None) -> None:
        self._provider = provider

    @keyword(name="Probe Get Info")
    def probe_get_info(self) -> dict[str, str]:
        return {"facade": "Probe", "module": __name__}

    @keyword(name="Probe Add")
    def probe_add(self, x: int, y: int) -> int:
        return int(x) + int(y)
