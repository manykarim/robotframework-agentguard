"""Unit tests for ``benchmarks.registry`` — name → loader resolution."""

from __future__ import annotations

import pytest

try:
    from AgentGuard.coding_agent.benchmarks import registry
except ImportError:  # pragma: no cover — Phase 3 race
    pytest.skip("phase3: benchmarks.registry not yet implemented", allow_module_level=True)


def test_canonical_names_match_research() -> None:
    expected = {"humaneval", "mbpp", "livecodebench", "swe_bench", "aider"}
    assert set(registry.available()) == expected


def test_get_loader_humaneval() -> None:
    loader = registry.get_loader("humaneval")
    assert loader.name == "humaneval"


def test_get_loader_aliases() -> None:
    assert registry.get_loader("human-eval").name == "humaneval"
    assert registry.get_loader("human_eval").name == "humaneval"
    assert registry.get_loader("HumanEval").name == "humaneval"


def test_get_loader_swe_aliases() -> None:
    assert registry.get_loader("swe-bench").name == "swe_bench"
    assert registry.get_loader("swe-bench-verified").name == "swe_bench"
    assert registry.get_loader("swebench").name == "swe_bench"


def test_get_loader_lcb_alias() -> None:
    assert registry.get_loader("lcb").name == "livecodebench"


def test_get_loader_aider_alias() -> None:
    assert registry.get_loader("aider-bench").name == "aider"
    assert registry.get_loader("aider_bench").name == "aider"


def test_get_loader_mbpp() -> None:
    assert registry.get_loader("mbpp").name == "mbpp"


def test_get_loader_unknown_raises() -> None:
    with pytest.raises(KeyError):
        registry.get_loader("not-a-benchmark")


def test_loader_classes_satisfy_protocol() -> None:
    """Every registered loader has the canonical static-method surface."""
    for name in registry.available():
        cls = registry.get_loader(name)
        assert hasattr(cls, "name")
        assert hasattr(cls, "is_available")
        assert hasattr(cls, "load")
        assert hasattr(cls, "score")
