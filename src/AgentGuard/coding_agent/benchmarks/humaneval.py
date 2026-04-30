"""HumanEval loader (research §2.5).

HumanEval (Chen et al., 2021, *Evaluating LLMs Trained on Code*) is the
canonical Python pass@1/pass@k benchmark. Each task ships a function-signature
prompt and a Python ``check(candidate)`` test that asserts behavioural
correctness.

Live dataset: ``openai_humaneval`` on HuggingFace. We lazy-import
:mod:`datasets` so users without the ``[benchmarks]`` extra still get the
bundled mini-fixture (5 tasks under
``tests/fixtures/coding_agent/benchmarks/humaneval_mini.json``).

Scoring delegates to :func:`AgentGuard.coding_agent.benchmarks.scorer.pass_at_k_from_results`,
which in turn delegates to the Phase-1
:func:`AgentGuard.stats.pass_at_k.pass_at_k` calculator (Chen et al. product
form).
"""

from __future__ import annotations

import json
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from .base import RunResult, Task
from .scorer import pass_at_k_from_results, pass_rate

__all__ = ["HumanEvalLoader", "FIXTURE_PATH"]

#: Bundled mini-fixture used when the HuggingFace dataset isn't reachable.
FIXTURE_PATH = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "coding_agent"
    / "benchmarks"
    / "humaneval_mini.json"
)


def _row_to_task(row: dict[str, Any]) -> Task:
    """Map a HuggingFace ``openai_humaneval`` row into a :class:`Task`."""
    task_id = str(row.get("task_id") or row.get("id") or "")
    return Task(
        id=task_id,
        prompt=str(row.get("prompt", "")),
        test_command=None,  # HumanEval validation is in-process via `check()`.
        repo_path=None,
        expected_files=[],
        metadata={
            "entry_point": row.get("entry_point", ""),
            "test": row.get("test", ""),
            "canonical_solution": row.get("canonical_solution", ""),
        },
    )


def _load_fixture(limit: int | None) -> list[Task]:
    if not FIXTURE_PATH.exists():  # pragma: no cover - shipped with the repo
        return []
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    tasks = [_row_to_task(row) for row in raw]
    return tasks if limit is None else tasks[: int(limit)]


class HumanEvalLoader:
    """:class:`~AgentGuard.coding_agent.benchmarks.base.BenchmarkLoader` for HumanEval."""

    name: str = "humaneval"

    @staticmethod
    def is_available() -> bool:
        return find_spec("datasets") is not None

    @staticmethod
    def load(split: str = "test", limit: int | None = None) -> list[Task]:
        if not HumanEvalLoader.is_available():
            return _load_fixture(limit)
        try:
            from datasets import load_dataset
        except Exception:  # noqa: BLE001 — fall back to the fixture
            return _load_fixture(limit)
        try:
            ds = load_dataset("openai_humaneval", split=split)
        except Exception:  # noqa: BLE001 — offline / 403 / dataset moved
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
