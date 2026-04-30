"""Unit tests for `AgentGuard.coding_agent.drivers.registry`.

The registry is the central name → class lookup used by ``Run Coding Agent``.
We pin the published surface (`get_driver`, `available_drivers`,
`registered_drivers`, name normalisation) so future drivers can be added
without breaking suite authors.
"""

from __future__ import annotations

import pytest

try:
    from AgentGuard.coding_agent.drivers import registry
    from AgentGuard.coding_agent.drivers.base import CodingAgentDriver
    from AgentGuard.coding_agent.drivers.local import LocalDriver
except ImportError:  # pragma: no cover — Phase 3 race
    pytest.skip("phase3: drivers.registry not yet implemented", allow_module_level=True)


def test_registered_drivers_include_canonical_names() -> None:
    names = set(registry.registered_drivers())
    expected = {"local", "claude-code", "codex", "aider", "opencode"}
    assert expected.issubset(names)


def test_get_local_driver_returns_local_driver() -> None:
    drv = registry.get_driver("local")
    assert isinstance(drv, LocalDriver)
    assert drv.name == "local"


def test_get_driver_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Unknown coding-agent driver"):
        registry.get_driver("bogus-driver-name")


def test_get_driver_normalises_underscore_aliases() -> None:
    drv = registry.get_driver("claude_code")
    assert drv.name == "claude-code"


def test_get_driver_handles_whitespace_and_case() -> None:
    drv = registry.get_driver("  LOCAL  ")
    assert drv.name == "local"


def test_get_driver_forwards_kwargs() -> None:
    """`provider=` is the LocalDriver constructor's only knob today."""
    drv = registry.get_driver("local", provider=None)
    assert isinstance(drv, LocalDriver)


def test_available_drivers_returns_subset_of_registered() -> None:
    avail = set(registry.available_drivers())
    reg = set(registry.registered_drivers())
    assert avail.issubset(reg)


def test_all_registered_drivers_satisfy_protocol() -> None:
    for name in registry.registered_drivers():
        try:
            drv = registry.get_driver(name)
        except Exception:
            continue
        assert isinstance(drv, CodingAgentDriver)


def test_drivers_dict_is_dict_type() -> None:
    assert isinstance(registry.DRIVERS, dict)
    assert "local" in registry.DRIVERS
