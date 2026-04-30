"""Unit tests for ``benchmarks.mbpp.MBPPLoader``."""

from __future__ import annotations

import pytest

try:
    from AgentGuard.coding_agent.benchmarks.base import RunResult
    from AgentGuard.coding_agent.benchmarks.mbpp import FIXTURE_PATH, MBPPLoader
except ImportError:  # pragma: no cover — Phase 3 race
    pytest.skip("phase3: benchmarks.mbpp not yet implemented", allow_module_level=True)


def test_loader_name() -> None:
    assert MBPPLoader.name == "mbpp"


def test_fixture_path_exists() -> None:
    assert FIXTURE_PATH.exists()


def test_load_returns_tasks_from_fixture() -> None:
    tasks = MBPPLoader.load(limit=3)
    assert len(tasks) == 3
    assert tasks[0].id.startswith("mbpp/")


def test_loaded_task_carries_tests_metadata() -> None:
    tasks = MBPPLoader.load(limit=1)
    assert "tests" in tasks[0].metadata
    assert isinstance(tasks[0].metadata["tests"], list)
    assert len(tasks[0].metadata["tests"]) >= 1


def test_load_no_limit_returns_all_fixture_rows() -> None:
    tasks = MBPPLoader.load()
    assert len(tasks) >= 3


def test_score_empty_returns_zero() -> None:
    out = MBPPLoader.score([])
    assert out["n"] == 0.0
    assert out["pass_at_1"] == 0.0


def test_score_all_pass() -> None:
    results = [RunResult(task_id=f"mbpp/{i}", passed=True, duration_seconds=0.1) for i in range(2)]
    out = MBPPLoader.score(results)
    assert out["pass_rate"] == pytest.approx(1.0)


def test_is_available_returns_bool() -> None:
    assert isinstance(MBPPLoader.is_available(), bool)
