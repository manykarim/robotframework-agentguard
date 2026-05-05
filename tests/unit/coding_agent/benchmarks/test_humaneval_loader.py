"""Unit tests for ``benchmarks.humaneval.HumanEvalLoader``."""

from __future__ import annotations

import pytest

try:
    from AgentGuard.coding_agent.benchmarks.base import RunResult
    from AgentGuard.coding_agent.benchmarks.humaneval import (
        FIXTURE_PATH,
        HumanEvalLoader,
    )
except ImportError:  # pragma: no cover — Phase 3 race
    pytest.skip("phase3: benchmarks.humaneval not yet implemented", allow_module_level=True)


def test_loader_name() -> None:
    assert HumanEvalLoader.name == "humaneval"


def test_fixture_path_exists() -> None:
    assert FIXTURE_PATH.exists()


def test_load_returns_tasks_from_fixture() -> None:
    tasks = HumanEvalLoader.load(limit=5)
    assert len(tasks) == 5
    assert tasks[0].id  # non-empty
    assert tasks[0].prompt  # non-empty


def test_load_respects_limit() -> None:
    tasks = HumanEvalLoader.load(limit=2)
    assert len(tasks) == 2


def test_loaded_task_carries_metadata() -> None:
    tasks = HumanEvalLoader.load(limit=1)
    task = tasks[0]
    assert "entry_point" in task.metadata
    assert "test" in task.metadata


def test_score_empty_returns_zero() -> None:
    out = HumanEvalLoader.score([])
    assert out["n"] == 0.0
    assert out["pass_at_1"] == 0.0


def test_score_all_pass() -> None:
    results = [RunResult(task_id=f"t{i}", passed=True, duration_seconds=0.1) for i in range(3)]
    out = HumanEvalLoader.score(results)
    assert out["pass_at_1"] == pytest.approx(1.0)
    assert out["pass_rate"] == pytest.approx(1.0)
    assert out["n"] == 3.0


def test_score_partial_pass() -> None:
    results = [
        RunResult(task_id="t1", passed=True, duration_seconds=0.1),
        RunResult(task_id="t2", passed=False, duration_seconds=0.1),
    ]
    out = HumanEvalLoader.score(results)
    assert 0 < out["pass_rate"] < 1


def test_is_available_returns_bool() -> None:
    assert isinstance(HumanEvalLoader.is_available(), bool)
