"""MBPP loader (research §2.5).

MBPP (Mostly Basic Python Programs) ships ~1,000 entry-level Python tasks
with three asserts each. We follow the HumanEval pass@k convention because
issue #42796 / research §2.5 treat MBPP as the "lighter" sibling benchmark
that uses the identical scoring rule.

Live dataset: ``mbpp`` on HuggingFace (``sanitized`` config preferred when
present). Lazy-imported via the optional ``[benchmarks]`` extra.
"""

from __future__ import annotations

import json
import logging
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from .base import RunResult, Task
from .scorer import pass_at_k_from_results, pass_rate

logger = logging.getLogger("AgentGuard.coding_agent.benchmarks.mbpp")

__all__ = ["MBPPLoader", "FIXTURE_PATH"]

FIXTURE_PATH = (
    Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "coding_agent" / "benchmarks" / "mbpp_mini.json"
)


def _row_to_task(row: dict[str, Any]) -> Task:
    task_id = str(row.get("task_id") or row.get("id") or "")
    text = str(row.get("text", row.get("prompt", "")))
    test_list = row.get("test_list") or row.get("tests") or []
    if not isinstance(test_list, list):  # pragma: no cover - defensive
        test_list = [str(test_list)]
    return Task(
        id=f"mbpp/{task_id}",
        prompt=text,
        test_command=None,
        repo_path=None,
        expected_files=[],
        metadata={
            "tests": list(test_list),
            "test_setup_code": row.get("test_setup_code", ""),
            "canonical_solution": row.get("code", ""),
        },
    )


def _load_fixture(limit: int | None) -> list[Task]:
    if not FIXTURE_PATH.exists():  # pragma: no cover
        return []
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    tasks = [_row_to_task(row) for row in raw]
    return tasks if limit is None else tasks[: int(limit)]


def _try_load_dataset(split: str) -> Any | None:
    try:
        from datasets import load_dataset
    except Exception:  # noqa: BLE001
        return None
    # Prefer the sanitised split when reachable; fall back to the raw config.
    for config in ("sanitized", None):
        try:
            if config:
                return load_dataset("mbpp", config, split=split)
            return load_dataset("mbpp", split=split)
        except Exception as exc:  # noqa: BLE001
            logger.debug("mbpp config=%s split=%s failed: %s", config, split, exc)
    return None


class MBPPLoader:
    """:class:`~AgentGuard.coding_agent.benchmarks.base.BenchmarkLoader` for MBPP."""

    name: str = "mbpp"

    @staticmethod
    def is_available() -> bool:
        return find_spec("datasets") is not None

    @staticmethod
    def load(split: str = "test", limit: int | None = None) -> list[Task]:
        if not MBPPLoader.is_available():
            return _load_fixture(limit)
        ds = _try_load_dataset(split)
        if ds is None:
            return _load_fixture(limit)
        rows = list(ds) if limit is None else list(ds.select(range(min(int(limit), len(ds)))))
        return [_row_to_task(row) for row in rows]

    @staticmethod
    def score(results: list[RunResult]) -> dict[str, float]:
        return {
            "n": float(len(results)),
            "pass_at_1": pass_at_k_from_results(results, 1),
            "pass_rate": pass_rate(results),
        }
