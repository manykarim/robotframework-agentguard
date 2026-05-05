"""Contract test for the 11 ``Library AgentGuard.<Name>`` façade modules.

PROPOSAL §7 Risk R4 — class-name-equals-module-name discipline must hold for
every façade. If we ever ship a façade that imports the internal class without
``as <Name>`` aliasing, Robot Framework's ``getattr(module, name)`` lookup
silently warns "contains no keywords" (observed in ``tests/experiments/exp_13``).
This test walks every façade and asserts:

1. The module imports.
2. ``getattr(module, last_segment)`` resolves to a class.
3. The class is instantiable with no required args (passes ``provider=None``
   when the constructor accepts it; otherwise no-arg construction is required).
4. The class exposes at least one ``@keyword``-decorated method (i.e. an
   attribute carrying the ``robot_name`` marker that
   ``robot.api.deco.keyword`` attaches).
5. The whole import surface round-trips through ``importlib`` so that any
   side-effect on import is exercised by the test, not by an end-user's
   ``Library AgentGuard.MCP`` line at suite-collection time.
"""

from __future__ import annotations

import importlib
import inspect
from typing import Any

import pytest

# 11 façade modules per PROPOSAL §3 mapping table. The order is arbitrary; the
# parametrize decorator gives each one its own pytest node so failures are
# attributed to the specific façade that broke.
FACADES: list[str] = [
    "AgentGuard.MCP",
    "AgentGuard.Skill",
    "AgentGuard.Tool",
    "AgentGuard.Stats",
    "AgentGuard.Judge",
    "AgentGuard.Security",
    "AgentGuard.Hook",
    "AgentGuard.SubAgent",
    "AgentGuard.Coding",
    "AgentGuard.Benchmark",
    "AgentGuard.Scenario",
]


def _instantiate(cls: type[Any]) -> Any:
    """Best-effort no-arg instantiation. Falls back to ``provider=None``.

    The keyword classes that compose an LLM provider (e.g. ``SkillsKeywords``,
    ``JudgeKeywords``) accept ``provider: Any | None = None`` so a constructor
    with no required positional args is the rule across all 11 sub-libraries.
    Any future class that breaks that rule fails this contract test loudly.
    """
    try:
        return cls()
    except TypeError:
        # Try the documented optional form. If it still fails we re-raise so
        # the test reports the underlying TypeError, not a swallowed one.
        return cls(provider=None)


def _has_keyword_method(cls: type[Any]) -> bool:
    """Return True if any attribute on the class carries Robot's ``robot_name``.

    ``robot.api.deco.keyword`` decorates the wrapped function with a
    ``robot_name`` attribute (and ``robot_tags`` / ``robot_types``). We only
    need ``robot_name`` to confirm the contract.
    """
    for name in dir(cls):
        if name.startswith("_"):
            continue
        attr = getattr(cls, name, None)
        if attr is None:
            continue
        if getattr(attr, "robot_name", None):
            return True
    return False


@pytest.mark.parametrize("dotted", FACADES)
def test_facade_module_imports(dotted: str) -> None:
    """The façade module imports without raising."""
    importlib.import_module(dotted)


@pytest.mark.parametrize("dotted", FACADES)
def test_facade_exposes_class_named_after_last_segment(dotted: str) -> None:
    """``getattr(module, last)`` returns the keyword class (PROPOSAL R4)."""
    module = importlib.import_module(dotted)
    last = dotted.rsplit(".", 1)[-1]
    assert hasattr(module, last), (
        f"{dotted} is missing top-level name {last!r}; Robot Framework's "
        f"`Library {dotted}` import would fail with 'contains no keywords'."
    )
    cls = getattr(module, last)
    assert inspect.isclass(cls), (
        f"{dotted}.{last} is {type(cls).__name__}, not a class. RF's library loader expects a class to instantiate."
    )


@pytest.mark.parametrize("dotted", FACADES)
def test_facade_class_is_instantiable(dotted: str) -> None:
    """The exposed class can be instantiated with no required args."""
    module = importlib.import_module(dotted)
    last = dotted.rsplit(".", 1)[-1]
    cls = getattr(module, last)
    instance = _instantiate(cls)
    assert instance is not None
    # Each instance must be of the resolved class — guards against a façade
    # whose attribute name happens to point at something else (e.g. a module).
    assert isinstance(instance, cls)


@pytest.mark.parametrize("dotted", FACADES)
def test_facade_class_has_at_least_one_keyword(dotted: str) -> None:
    """The exposed class carries at least one ``@keyword``-decorated method."""
    module = importlib.import_module(dotted)
    last = dotted.rsplit(".", 1)[-1]
    cls = getattr(module, last)
    assert _has_keyword_method(cls), (
        f"{dotted}.{last} has no `@keyword`-decorated methods; `Library {dotted}` would import 0 keywords."
    )


@pytest.mark.parametrize("dotted", FACADES)
def test_facade_module_is_listed_in_dunder_all(dotted: str) -> None:
    """The façade declares its alias in ``__all__`` (PROPOSAL §6 contract)."""
    module = importlib.import_module(dotted)
    last = dotted.rsplit(".", 1)[-1]
    declared = getattr(module, "__all__", None)
    assert declared is not None, f"{dotted} has no __all__"
    assert last in declared, f"{last!r} not in {dotted}.__all__ ({declared!r})"


# ---------------------------------------------------------------------------
# End-to-end: confirm the kitchen-sink ``from X.Y import Y`` form actually
# yields the keyword class, regardless of the upstream class's own __name__
# (the alias survives RF's `getattr(module, name)` lookup — see
# `tests/experiments/exp_13c/test_alias.robot`).
# ---------------------------------------------------------------------------


def test_mcp_facade_alias_survives_from_import() -> None:
    """``from AgentGuard.MCP import MCP`` returns the keyword class."""
    from AgentGuard.MCP import MCP  # noqa: PLC0415  — intentional in-test import

    assert inspect.isclass(MCP)
    # The internal class is `MCPKeywords`; the façade aliases it. Both names
    # point at the same class object.
    from AgentGuard.mcp.library import MCPKeywords  # noqa: PLC0415

    assert MCP is MCPKeywords


def test_skill_facade_alias_survives_from_import() -> None:
    from AgentGuard.Skill import Skill  # noqa: PLC0415
    from AgentGuard.skills.library import SkillsKeywords  # noqa: PLC0415

    assert Skill is SkillsKeywords


def test_security_facade_alias_survives_from_import() -> None:
    from AgentGuard.Security import Security  # noqa: PLC0415
    from AgentGuard.security.library import SecurityKeywords  # noqa: PLC0415

    assert Security is SecurityKeywords


# ---------------------------------------------------------------------------
# Coverage: confirm every façade's class is *the same object* as the deeply
# imported one. This rules out a regression where a future façade builds a
# wrapper class instead of aliasing — that would create two separate suite-
# scoped state holders if a user imports both forms (PROPOSAL R1).
# ---------------------------------------------------------------------------

# Each tuple: (façade_dotted_path, deep_import_path, deep_class_name)
ALIAS_PAIRS: list[tuple[str, str, str]] = [
    ("AgentGuard.MCP", "AgentGuard.mcp.library", "MCPKeywords"),
    ("AgentGuard.Skill", "AgentGuard.skills.library", "SkillsKeywords"),
    ("AgentGuard.Tool", "AgentGuard.tool_calls.library", "ToolCallKeywords"),
    ("AgentGuard.Stats", "AgentGuard.stats.library", "StatsKeywords"),
    ("AgentGuard.Judge", "AgentGuard.judge.library", "JudgeKeywords"),
    ("AgentGuard.Security", "AgentGuard.security.library", "SecurityKeywords"),
    ("AgentGuard.Hook", "AgentGuard.hooks.library", "HooksKeywords"),
    ("AgentGuard.SubAgent", "AgentGuard.subagents.library", "SubAgentsKeywords"),
    ("AgentGuard.Coding", "AgentGuard.coding_agent.library", "CodingAgentKeywords"),
    (
        "AgentGuard.Benchmark",
        "AgentGuard.coding_agent.benchmarks.library",
        "CodingBenchmarkKeywords",
    ),
    ("AgentGuard.Scenario", "AgentGuard.mcp_scenario.library", "MCPScenarioKeywords"),
]


@pytest.mark.parametrize(("facade", "deep", "internal"), ALIAS_PAIRS)
def test_facade_class_is_same_object_as_deep_import(facade: str, deep: str, internal: str) -> None:
    """``AgentGuard.MCP.MCP is AgentGuard.mcp.library.MCPKeywords`` holds for every façade."""
    facade_mod = importlib.import_module(facade)
    deep_mod = importlib.import_module(deep)
    facade_alias = facade.rsplit(".", 1)[-1]
    facade_cls = getattr(facade_mod, facade_alias)
    deep_cls = getattr(deep_mod, internal)
    assert facade_cls is deep_cls, (
        f"{facade}.{facade_alias} ({facade_cls!r}) is not the same object as "
        f"{deep}.{internal} ({deep_cls!r}). Façades must alias, not subclass."
    )
