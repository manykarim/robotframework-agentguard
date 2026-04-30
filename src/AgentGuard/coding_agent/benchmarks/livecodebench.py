"""LiveCodeBench loader (research §2.5).

LiveCodeBench is a contamination-resistant code-generation benchmark whose
problems are sampled from coding-contest platforms (LeetCode, AtCoder,
Codeforces) within rolling time windows. The HuggingFace dataset
``livecodebench/code_generation_lite`` exposes the public/private test cases
and a stdin/stdout harness — we surface those in :class:`Task.metadata` so
the keyword-side runner can drive a sandboxed exec.

Score: pass@1 (per the LCB paper convention).
"""

from __future__ import annotations

import json
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from .base import RunResult, Task
from .scorer import pass_at_k_from_results, pass_rate

__all__ = ["LiveCodeBenchLoader", "FIXTURE_PATH"]

FIXTURE_PATH = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "coding_agent"
    / "benchmarks"
    / "livecodebench_mini.json"
)


def _row_to_task(row: dict[str, Any]) -> Task:
    qid = str(row.get("question_id") or row.get("id") or "")
    title = str(row.get("question_title") or "")
    content = str(row.get("question_content") or row.get("prompt", ""))
    return Task(
        id=f"lcb/{qid}",
        prompt=content,
        test_command=None,
        repo_path=None,
        expected_files=[],
        metadata={
            "question_title": title,
            "starter_code": row.get("starter_code", ""),
            "difficulty": row.get("difficulty", ""),
            "platform": row.get("platform", ""),
            "contest_date": row.get("contest_date", ""),
            "public_test_cases": row.get("public_test_cases", []),
            "private_test_cases": row.get("private_test_cases", []),
        },
    )


def _load_fixture(limit: int | None) -> list[Task]:
    if not FIXTURE_PATH.exists():  # pragma: no cover
        return []
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    tasks = [_row_to_task(row) for row in raw]
    return tasks if limit is None else tasks[: int(limit)]


class LiveCodeBenchLoader:
    """:class:`~AgentGuard.coding_agent.benchmarks.base.BenchmarkLoader` for LCB."""

    name: str = "livecodebench"

    @staticmethod
    def is_available() -> bool:
        return find_spec("datasets") is not None

    @staticmethod
    def load(split: str = "test", limit: int | None = None) -> list[Task]:
        if not LiveCodeBenchLoader.is_available():
            return _load_fixture(limit)
        try:
            from datasets import load_dataset
        except Exception:  # noqa: BLE001
            return _load_fixture(limit)
        try:
            ds = load_dataset("livecodebench/code_generation_lite", split=split)
        except Exception:  # noqa: BLE001
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
