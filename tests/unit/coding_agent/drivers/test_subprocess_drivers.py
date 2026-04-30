"""Unit tests for the subprocess-backed CLI drivers (claude-code, codex,
aider, opencode, cline, continue_, copilot).

Each driver has the same shape:

* ``name`` is a plain class attribute,
* ``is_available()`` returns False when the underlying binary is missing,
* ``run()`` raises :class:`DriverUnavailable` instead of running a missing CLI.

We never actually exec the CLI here — the contract is that ``is_available()``
must be cheap/safe regardless of host setup, and that ``run()`` won't blow up
the test runner when the binary doesn't exist.
"""

from __future__ import annotations

import shutil
from typing import Any

import pytest

try:
    from AgentGuard.coding_agent.drivers import (
        aider as aider_mod,
    )
    from AgentGuard.coding_agent.drivers import (
        claude_code as claude_mod,
    )
    from AgentGuard.coding_agent.drivers import (
        codex as codex_mod,
    )
    from AgentGuard.coding_agent.drivers.base import CodingAgentDriver, DriverConfig
    from AgentGuard.coding_agent.drivers.exceptions import DriverUnavailable
except ImportError:  # pragma: no cover — Phase 3 race
    pytest.skip("phase3: drivers.* not yet implemented", allow_module_level=True)


# Optional drivers — opencode/cline/continue/copilot are optional in this
# harness; we use ``getattr`` to avoid breaking when a driver hasn't shipped.
def _optional_drivers() -> list[type[Any]]:
    out: list[type[Any]] = []
    for mod_name, cls_name in (
        ("AgentGuard.coding_agent.drivers.opencode", "OpenCodeDriver"),
        ("AgentGuard.coding_agent.drivers.cline", "ClineDriver"),
        ("AgentGuard.coding_agent.drivers.continue_", "ContinueDriver"),
        ("AgentGuard.coding_agent.drivers.copilot", "CopilotDriver"),
    ):
        try:
            mod = __import__(mod_name, fromlist=[cls_name])
            out.append(getattr(mod, cls_name))
        except (ImportError, AttributeError):
            continue
    return out


_DRIVERS: list[type[Any]] = [
    claude_mod.ClaudeCodeDriver,
    codex_mod.CodexDriver,
    aider_mod.AiderDriver,
    *_optional_drivers(),
]


@pytest.mark.parametrize("driver_cls", _DRIVERS)
def test_driver_has_required_protocol_attrs(driver_cls: type[Any]) -> None:
    drv = driver_cls()
    assert hasattr(drv, "name") and isinstance(drv.name, str) and drv.name
    assert isinstance(drv, CodingAgentDriver)


@pytest.mark.parametrize("driver_cls", _DRIVERS)
def test_is_available_does_not_raise(driver_cls: type[Any]) -> None:
    """is_available() must be safe to call regardless of host CLI presence."""
    drv = driver_cls()
    # We don't assert True/False — depends on the host. We only assert no raise.
    result = drv.is_available()
    assert isinstance(result, bool)


def _binary_missing(name: str) -> bool:
    return shutil.which(name) is None


@pytest.mark.parametrize(
    ("driver_cls", "binary"),
    [
        (claude_mod.ClaudeCodeDriver, "claude"),
        (codex_mod.CodexDriver, "codex"),
        (aider_mod.AiderDriver, "aider"),
    ],
)
def test_run_raises_driver_unavailable_when_binary_missing(driver_cls: type[Any], binary: str) -> None:
    if not _binary_missing(binary):
        pytest.skip(f"{binary} present on PATH; cannot test missing-binary path")
    drv = driver_cls()
    with pytest.raises(DriverUnavailable):
        drv.run("hello", DriverConfig())


def test_claude_code_driver_default_name() -> None:
    assert claude_mod.ClaudeCodeDriver().name == "claude-code"


def test_codex_driver_default_name() -> None:
    assert codex_mod.CodexDriver().name == "codex"


def test_aider_driver_default_name() -> None:
    assert aider_mod.AiderDriver().name == "aider"
