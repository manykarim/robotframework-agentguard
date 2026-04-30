"""Coding-agent benchmark loaders + keywords (research §2.5).

Five benchmarks ship: SWE-bench Verified (primary, leakage-clean per Yang
et al. 2024), Aider (exercism-style first-run pass rate), HumanEval, MBPP,
LiveCodeBench. Each loader implements
:class:`AgentGuard.coding_agent.benchmarks.base.BenchmarkLoader` and degrades
to a bundled mini-fixture when the optional ``[benchmarks]`` extra
(``datasets`` + ``huggingface-hub``) is missing.

Aggregate scoring goes through
:func:`AgentGuard.coding_agent.benchmarks.scorer.pass_at_k_from_results`,
which delegates to the Phase-1 :func:`AgentGuard.stats.pass_at_k.pass_at_k`
calculator (Chen et al. product form, numerically stable).
"""

from AgentGuard.coding_agent.benchmarks.base import (
    BenchmarkLoader,
    RunResult,
    Task,
)
from AgentGuard.coding_agent.benchmarks.library import (
    CodingBenchmarkKeywords,
    CodingBenchmarkLibrary,
)
from AgentGuard.coding_agent.benchmarks.registry import (
    BENCHMARK_NAMES,
    available,
    get_loader,
)
from AgentGuard.coding_agent.benchmarks.scorer import (
    first_run_pass_rate,
    pass_at_k_from_results,
    pass_rate,
    per_problem_outcomes,
    resolved_rate,
)

__all__ = [
    "BENCHMARK_NAMES",
    "BenchmarkLoader",
    "CodingBenchmarkKeywords",
    "CodingBenchmarkLibrary",
    "RunResult",
    "Task",
    "available",
    "first_run_pass_rate",
    "get_loader",
    "pass_at_k_from_results",
    "pass_rate",
    "per_problem_outcomes",
    "resolved_rate",
]
