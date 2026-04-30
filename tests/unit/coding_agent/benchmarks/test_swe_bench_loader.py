"""Unit tests for ``benchmarks.swe_bench.SWEBenchLoader``."""

from __future__ import annotations

import pytest

try:
    from AgentGuard.coding_agent.benchmarks.base import RunResult
    from AgentGuard.coding_agent.benchmarks.swe_bench import (
        DATASET_FULL,
        DATASET_VERIFIED,
        FIXTURE_PATH,
        SWEBenchLoader,
    )
except ImportError:  # pragma: no cover — Phase 3 race
    pytest.skip("phase3: benchmarks.swe_bench not yet implemented", allow_module_level=True)


def test_loader_name() -> None:
    assert SWEBenchLoader.name == "swe_bench"


def test_dataset_constants() -> None:
    assert "Verified" in DATASET_VERIFIED
    assert "SWE-bench" in DATASET_FULL


def test_fixture_path_exists() -> None:
    assert FIXTURE_PATH.exists()


def test_load_returns_tasks_from_fixture() -> None:
    tasks = SWEBenchLoader.load(limit=2)
    assert len(tasks) == 2
    assert tasks[0].id  # instance_id
    assert tasks[0].metadata.get("FAIL_TO_PASS")  # canonical SWE-bench shape


def test_loaded_task_carries_repo_metadata() -> None:
    tasks = SWEBenchLoader.load(limit=1)
    md = tasks[0].metadata
    assert "repo" in md
    assert "base_commit" in md


def test_fixture_tasks_have_test_command() -> None:
    """The bundled fixture tasks (when datasets isn't reachable) carry test_cmd.
    Some live HF rows omit ``test_cmd``; we only assert this for fixture mode.
    """
    import json
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert any(row.get("test_cmd") for row in raw)


def test_score_resolved_rate_alias_for_pass_rate() -> None:
    results = [
        RunResult(task_id="i1", passed=True, duration_seconds=1.0),
        RunResult(task_id="i2", passed=False, duration_seconds=1.0),
    ]
    out = SWEBenchLoader.score(results)
    assert out["resolved_rate"] == pytest.approx(0.5)
    assert out["pass_rate"] == pytest.approx(0.5)
    assert out["n"] == 2.0


def test_score_empty_returns_zero() -> None:
    out = SWEBenchLoader.score([])
    assert out["n"] == 0.0
    assert out["resolved_rate"] == 0.0


def test_is_available_returns_bool() -> None:
    assert isinstance(SWEBenchLoader.is_available(), bool)


def test_verified_only_default() -> None:
    assert SWEBenchLoader.verified_only is True
