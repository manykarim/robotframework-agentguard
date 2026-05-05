"""SWE-bench Verified loader (research §2.5).

SWE-bench (Jimenez et al., 2024) measures end-to-end issue-resolution on real
GitHub repos: each instance ships a problem statement, the failing repo at a
specific ``base_commit``, and a ``FAIL_TO_PASS`` / ``PASS_TO_PASS`` test list
that defines "resolved". The headline metric is **% Resolved** (== pass-rate).

**Why Verified is the default split.** Yang et al. (*SWE-Bench+*, 2024) showed
that ~33% of the original SWE-bench's "successful" patches contained solution
leakage — SWE-Agent + GPT-4 fell from 12.47% → 3.97% when leakage was
stripped. The ``princeton-nlp/SWE-bench_Verified`` 500-problem subset is the
human-validated, leakage-clean re-curation that has since become the
defensible default; we expose ``verified_only=True`` to the keyword layer to
make this explicit.

**Phase 3 scope.** Live SWE-bench evaluation requires the upstream Docker
images (one per instance) plus an apply-patch + run-tests harness — that
landed as Phase-4 work. The current ``Run SWE Bench Task`` keyword still
dispatches to the LocalDriver to give us cost / token / behavioral-metric
signal, but the resulting ``RunResult.passed`` reflects the LLM's
diff-format plausibility rather than a real test outcome. The docstring on
the keyword spells this out so downstream baselines aren't misread.
"""

from __future__ import annotations

import json
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from .base import RunResult, Task
from .scorer import pass_rate, resolved_rate

__all__ = ["SWEBenchLoader", "FIXTURE_PATH", "DATASET_VERIFIED", "DATASET_FULL"]

FIXTURE_PATH = (
    Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "coding_agent" / "benchmarks" / "swe_bench_mini.json"
)

DATASET_VERIFIED = "princeton-nlp/SWE-bench_Verified"
DATASET_FULL = "princeton-nlp/SWE-bench"

_CACHE_DIR = Path.home() / ".cache" / "agentguard" / "swe_bench"


def _row_to_task(row: dict[str, Any]) -> Task:
    instance_id = str(row.get("instance_id") or row.get("id") or "")
    return Task(
        id=instance_id,
        prompt=str(row.get("problem_statement", "")),
        test_command=row.get("test_cmd"),
        repo_path=None,
        expected_files=[],
        metadata={
            "repo": row.get("repo", ""),
            "base_commit": row.get("base_commit", ""),
            "FAIL_TO_PASS": row.get("FAIL_TO_PASS", []),
            "PASS_TO_PASS": row.get("PASS_TO_PASS", []),
            "patch": row.get("patch", ""),
            "version": row.get("version", ""),
            "environment_setup_commit": row.get("environment_setup_commit", ""),
            "hints_text": row.get("hints_text", ""),
        },
    )


def _load_fixture(limit: int | None) -> list[Task]:
    if not FIXTURE_PATH.exists():  # pragma: no cover
        return []
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    tasks = [_row_to_task(row) for row in raw]
    return tasks if limit is None else tasks[: int(limit)]


def _cache_dir() -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR


class SWEBenchLoader:
    """:class:`~AgentGuard.coding_agent.benchmarks.base.BenchmarkLoader` for SWE-bench Verified."""

    name: str = "swe_bench"

    #: Default to the Verified subset per research §2.5 (leakage-clean).
    verified_only: bool = True

    @staticmethod
    def is_available() -> bool:
        return find_spec("datasets") is not None

    @staticmethod
    def load(
        split: str = "test",
        limit: int | None = None,
        *,
        verified_only: bool = True,
    ) -> list[Task]:
        """Load SWE-bench tasks.

        ``verified_only=True`` (the default) loads
        ``princeton-nlp/SWE-bench_Verified`` — the 500-problem human-validated
        subset that mitigates the leakage finding from Yang et al.
        """
        if not SWEBenchLoader.is_available():
            return _load_fixture(limit)
        try:
            from datasets import load_dataset
        except Exception:  # noqa: BLE001
            return _load_fixture(limit)
        target = DATASET_VERIFIED if verified_only else DATASET_FULL
        try:
            ds = load_dataset(target, split=split, cache_dir=str(_cache_dir()))
        except Exception:  # noqa: BLE001
            return _load_fixture(limit)
        rows = list(ds) if limit is None else list(ds.select(range(min(int(limit), len(ds)))))
        return [_row_to_task(row) for row in rows]

    @staticmethod
    def score(results: list[RunResult]) -> dict[str, float]:
        """Aggregate to ``{resolved_rate, n}``.

        ``resolved_rate`` is the canonical SWE-bench leaderboard metric — the
        fraction of instances whose ``FAIL_TO_PASS`` tests now pass without
        regressing the ``PASS_TO_PASS`` tests. We delegate to
        :func:`AgentGuard.coding_agent.benchmarks.scorer.resolved_rate` (an
        alias for ``pass_rate``) so the terminology stays consistent.
        """
        return {
            "n": float(len(results)),
            "resolved_rate": resolved_rate(results),
            "pass_rate": pass_rate(results),
        }
