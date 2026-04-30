"""Aider benchmark loader (research §2.5).

Aider's benchmark is exercism-style: a curated set of small Python (and
multi-language) exercises with starter files, an instruction prompt, and a
unit-test suite. The headline metric is **first-run pass rate** — Aider's
"plausible solution" criterion that research §2.5 flags as the most
defensible signal in a post-leakage-finding world.

**Phase 3 scope.** Full integration with the upstream
``aider-AI/aider/benchmark`` driver (clone exercism, prepare scaffolds,
diff-apply, run pytest) lands in Phase 4. This loader provides the stable
:class:`~AgentGuard.coding_agent.benchmarks.base.BenchmarkLoader` shape and
serves the bundled mini-fixture (3 exercises) so the keyword surface,
scoring, and Robot examples are testable end-to-end today.
"""

from __future__ import annotations

import json
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from .base import RunResult, Task
from .scorer import first_run_pass_rate, pass_rate

__all__ = ["AiderBenchLoader", "FIXTURE_PATH"]

FIXTURE_PATH = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "coding_agent"
    / "benchmarks"
    / "aider_mini.json"
)


def _row_to_task(row: dict[str, Any]) -> Task:
    exercise = str(row.get("exercise") or row.get("id") or "")
    files_to_edit = row.get("files_to_edit") or []
    if not isinstance(files_to_edit, list):
        files_to_edit = [str(files_to_edit)]
    return Task(
        id=f"aider/{exercise}",
        prompt=str(row.get("instructions", "")),
        test_command=None,
        repo_path=None,
        expected_files=[str(p) for p in files_to_edit],
        metadata={
            "exercise": exercise,
            "language": row.get("language", "python"),
            "starter_code": row.get("starter_code", ""),
            "test": row.get("test", ""),
            "entry_point": row.get("entry_point", ""),
        },
    )


def _load_fixture(limit: int | None) -> list[Task]:
    if not FIXTURE_PATH.exists():  # pragma: no cover
        return []
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    tasks = [_row_to_task(row) for row in raw]
    return tasks if limit is None else tasks[: int(limit)]


class AiderBenchLoader:
    """:class:`~AgentGuard.coding_agent.benchmarks.base.BenchmarkLoader` for Aider exercises."""

    name: str = "aider"

    @staticmethod
    def is_available() -> bool:
        # Real upstream loader will require the ``aider`` package + a clone of
        # ``exercism/python`` — both Phase-4. Today we only need the optional
        # ``datasets`` extra to be present to *attempt* a HuggingFace mirror.
        return find_spec("datasets") is not None

    @staticmethod
    def load(split: str = "test", limit: int | None = None) -> list[Task]:
        # Phase-3: always fall back to the bundled fixture. Phase-4 will swap
        # in the real exercism walker.
        return _load_fixture(limit)

    @staticmethod
    def score(results: list[RunResult]) -> dict[str, float]:
        return {
            "n": float(len(results)),
            "first_run_pass_rate": first_run_pass_rate(results),
            "pass_rate": pass_rate(results),
        }
