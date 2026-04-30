"""Shared benchmark loader contracts (research §2.5).

Every concrete benchmark module (``humaneval``, ``mbpp``, ``livecodebench``,
``swe_bench``, ``aider_bench``) implements :class:`BenchmarkLoader` so the
keyword surface in :mod:`AgentGuard.coding_agent.benchmarks.library` and the
generic ``Run Benchmark Suite`` runner can iterate them uniformly.

The ``Task`` shape is intentionally narrow: a prompt, an optional
``test_command`` to validate the agent's edits, and a free-form
``metadata`` dict for benchmark-specific extras (``FAIL_TO_PASS`` /
``PASS_TO_PASS`` lists for SWE-bench, the ``entry_point`` for HumanEval,
etc.). Everything else lives in :class:`RunResult`.

All dataclasses are mypy ``--strict`` clean; loaders raise plain ``RuntimeError``
on dataset-availability problems so the keyword layer can catch them and
either skip the suite or fall back to the bundled mini-fixtures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "Task",
    "RunResult",
    "BenchmarkLoader",
]


@dataclass
class Task:
    """One benchmark task fed to a coding-agent driver.

    ``test_command`` is the canonical way the benchmark validates a successful
    edit (e.g. ``pytest -q test_foo.py`` for HumanEval, the SWE-bench
    ``test_cmd`` for SWE-bench Verified). ``None`` means the loader has no
    automatic validator (Aider's exercism-style check sometimes lives inside
    ``metadata``).

    ``repo_path`` is set when the benchmark ships a self-contained repo at a
    specific commit (SWE-bench Verified) — otherwise ``None``.

    ``expected_files`` is a hint for first-run-test-pass-rate analytics: the
    files the agent is *expected* to modify.

    ``metadata`` carries benchmark-specific extras; documented per-benchmark
    in each loader module.
    """

    id: str
    prompt: str
    test_command: str | None = None
    repo_path: str | None = None
    expected_files: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunResult:
    """Outcome of dispatching a single :class:`Task` to a driver.

    ``passed`` is the benchmark-specific verdict — for HumanEval/MBPP that's
    the bundled unit-test result, for SWE-bench it's the ``FAIL_TO_PASS`` /
    ``PASS_TO_PASS`` outcome, for Aider it's the first-run test pass.

    ``diff`` is the unified diff the agent produced (when available); the
    keyword layer logs it with Robot's ``logger.info`` so failures land in
    ``log.html`` in a humanly readable form.

    ``cost_usd`` and ``session_jsonl_path`` are forwarded straight from the
    underlying ``DriverResult`` so downstream metric calculators (e.g. the
    #42796 pack) can re-open the JSONL.
    """

    task_id: str
    passed: bool
    duration_seconds: float
    diff: str | None = None
    test_output: str | None = None
    cost_usd: float | None = None
    session_jsonl_path: str | None = None


@runtime_checkable
class BenchmarkLoader(Protocol):
    """Stable benchmark surface (research §2.5).

    Implementations MUST be importable with the optional ``[benchmarks]``
    extra missing — ``is_available()`` reports the dataset reachability
    without raising, and ``load()`` falls back to the bundled
    ``tests/fixtures/coding_agent/benchmarks/<name>_mini.json`` fixture when
    the HuggingFace ``datasets`` package isn't installed.
    """

    name: str

    @staticmethod
    def is_available() -> bool:
        """``True`` when the upstream dataset (HuggingFace) is reachable.

        Returning ``False`` is not an error — the loader still works against
        the bundled mini-fixture.
        """
        ...

    @staticmethod
    def load(split: str = "test", limit: int | None = None) -> list[Task]:
        """Return the (sliced) task list for the requested split.

        ``split`` mirrors HuggingFace dataset splits (``"test"``, ``"train"``,
        sometimes ``"validation"``); benchmarks without splits ignore it.
        ``limit`` truncates the returned list (useful for cost-capped CI runs).
        """
        ...

    @staticmethod
    def score(results: list[RunResult]) -> dict[str, float]:
        """Aggregate ``results`` into the canonical metric for this benchmark.

        Returned dict always contains at least ``"n"`` (number of attempts);
        per-benchmark keys include ``"pass_at_1"``, ``"resolved_rate"``,
        ``"first_run_pass_rate"`` etc.
        """
        ...
