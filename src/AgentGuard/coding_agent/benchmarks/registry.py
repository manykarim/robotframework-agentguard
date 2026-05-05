"""Benchmark name → loader factory.

Used by :class:`AgentGuard.coding_agent.benchmarks.library.CodingBenchmarkKeywords`
to resolve a free-form ``name`` argument to one of the bundled
:class:`~AgentGuard.coding_agent.benchmarks.base.BenchmarkLoader`
implementations.

We intentionally use string keys (not Enum) so suite authors can write
``Run Benchmark Suite    humaneval`` without an import dance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .base import BenchmarkLoader

__all__ = ["available", "get_loader", "BENCHMARK_NAMES"]

#: Canonical benchmark names accepted by ``Run Benchmark Suite`` and
#: :func:`get_loader`. Aliases are normalised inside :func:`get_loader`.
BENCHMARK_NAMES: tuple[str, ...] = (
    "humaneval",
    "mbpp",
    "livecodebench",
    "swe_bench",
    "aider",
)


_ALIASES: dict[str, str] = {
    "human-eval": "humaneval",
    "human_eval": "humaneval",
    "live-code-bench": "livecodebench",
    "live_code_bench": "livecodebench",
    "lcb": "livecodebench",
    "swe-bench": "swe_bench",
    "swe-bench-verified": "swe_bench",
    "swebench": "swe_bench",
    "aider-bench": "aider",
    "aider_bench": "aider",
}


def _canonical(name: str) -> str:
    key = name.strip().lower().replace(" ", "")
    return _ALIASES.get(key, key)


def available() -> tuple[str, ...]:
    """Return the tuple of canonical benchmark names known to the registry."""
    return BENCHMARK_NAMES


def get_loader(name: str) -> type[BenchmarkLoader]:
    """Resolve ``name`` (or alias) to a loader *class*.

    Imports happen lazily so the unused benchmarks never pull their fixture
    paths / ``datasets`` probes into memory.
    """
    canonical = _canonical(name)
    if canonical == "humaneval":
        from . import humaneval

        return humaneval.HumanEvalLoader
    if canonical == "mbpp":
        from . import mbpp

        return mbpp.MBPPLoader
    if canonical == "livecodebench":
        from . import livecodebench

        return livecodebench.LiveCodeBenchLoader
    if canonical == "swe_bench":
        from . import swe_bench

        return swe_bench.SWEBenchLoader
    if canonical == "aider":
        from . import aider_bench

        return aider_bench.AiderBenchLoader
    raise KeyError(f"Unknown benchmark {name!r}; expected one of {BENCHMARK_NAMES} (or an alias).")
