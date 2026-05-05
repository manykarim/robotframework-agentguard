"""``CodingBenchmarkKeywords`` — Robot Framework surface for benchmark suites.

Composed alongside the rest of the CodingAgent context (see
:mod:`AgentGuard.coding_agent.library`); also addressable directly via
``Library AgentGuard.CodingAgent.Benchmarks`` for suites that only need
benchmark keywords.

All keywords accept ``driver="local"`` by default — the LocalDriver produces
a synthetic ReAct loop against OpenRouter (research §7.2) which is the only
driver guaranteed to be runnable in CI without an external CLI. Live tests
on HumanEval/MBPP set ``driver="local"`` and gate themselves with the
``OPENROUTER_API_KEY`` env var.

Per the SWE-Bench+ leakage finding (Yang et al., 2024) the SWE-bench loader
defaults to the **Verified** split. ``Run SWE Bench Task`` currently returns
a *plausibility* signal (Phase 4 will land the real apply-patch + test loop
under Docker) — the keyword's docstring spells this out.
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

from robot.api.deco import keyword

from AgentGuard._assertions import AssertionOperator, assert_value

from .base import RunResult, Task
from .registry import BENCHMARK_NAMES, get_loader
from .runner import (
    aider_validate,
    coerce_task,
    driver_config,
    extract_code,
    humaneval_validate,
    lcb_validate,
    make_run_result,
    mbpp_validate,
    resolve_driver,
    swe_bench_plausibility,
)
from .scorer import (
    first_run_pass_rate,
    pass_at_k_from_results,
    pass_rate,
    resolved_rate,
)

if TYPE_CHECKING:  # pragma: no cover
    from AgentGuard.providers.base import LLMProviderAdapter

logger = logging.getLogger("AgentGuard.coding_agent.benchmarks")


def _coerce_numeric(expected: Any) -> Any:
    """Coerce string ``assertion_expected`` to ``float`` for pass@k assertions.

    Robot Framework passes positional arguments as strings; AssertionEngine's
    ``verify_assertion`` does not auto-coerce. Pass@k / pass-rate keywords all
    return floats so we coerce string thresholds to floats. Non-numeric strings
    pass through unchanged (e.g. ``validate`` Python expressions).
    """
    if isinstance(expected, str):
        try:
            return float(expected)
        except ValueError:
            return expected
    return expected


class CodingBenchmarkKeywords:
    """Robot keywords for SWE-bench, Aider, HumanEval, MBPP, LiveCodeBench."""

    def __init__(
        self,
        provider: LLMProviderAdapter | None = None,
        *,
        default_model: str | None = None,
    ) -> None:
        self._provider = provider
        self._default_model = default_model

    @keyword(name="Load SWE Bench Dataset")
    def load_swe_bench_dataset(
        self, split: str = "test", limit: int | None = None, verified_only: bool = True
    ) -> list[Task]:
        """Load SWE-bench (Verified by default; ``verified_only=False`` for the full set).

        Per Yang et al. 2024 (*SWE-Bench+*) the original SWE-bench leaks ~33%
        of solutions; the Verified subset is the leakage-clean default. Falls
        back to the bundled mini-fixture when the ``[benchmarks]`` extra is
        not installed.
        """
        from . import swe_bench

        return swe_bench.SWEBenchLoader.load(split=split, limit=limit, verified_only=verified_only)

    @keyword(name="Run SWE Bench Task")
    def run_swe_bench_task(
        self,
        task: Task | dict[str, Any],
        driver: str = "local",
        model: str | None = None,
        cwd: str | None = None,
    ) -> RunResult:
        """Dispatch a SWE-bench task to ``driver`` and score plausibility.

        **Phase-3 caveat**: a real SWE-bench eval runs the instance's
        ``test_cmd`` after applying the agent's patch inside the upstream
        Docker image — that loop lands in Phase 4. The current implementation
        invokes the LocalDriver and treats "agent emitted a unified diff" as
        the success signal. Use this keyword for harness wiring + cost /
        token / behavioural-metric collection; do NOT publish "% Resolved"
        numbers off it.
        """
        coerced = coerce_task(task)
        drv = resolve_driver(driver, self._provider)
        cfg = driver_config(model or self._default_model, cwd)
        start = time.perf_counter()
        dr = drv.run(coerced.prompt, cfg)
        passed, output = swe_bench_plausibility(dr.stdout or "")
        return make_run_result(
            coerced,
            passed=passed,
            duration_s=time.perf_counter() - start,
            diff=dr.stdout or None,
            test_output=output,
            driver_result=dr,
        )

    @keyword(name="SWE Bench Pass At K")
    def swe_bench_pass_at_k(
        self,
        results: list[RunResult],
        k: int = 1,
        assertion_operator: AssertionOperator | None = None,
        assertion_expected: Any = None,
        message: str | None = None,
    ) -> float:
        """Compute SWE-bench pass@k. With ``assertion_operator`` also asserts.

        ``k == 1`` (the leaderboard convention) collapses to the resolved-rate;
        ``k > 1`` delegates to HumanEval-style pass@k.

        Typical assertion: ``SWE Bench Pass At K ${results} 1 >= 0.4``.
        """
        value = resolved_rate(results) if int(k) <= 1 else pass_at_k_from_results(results, int(k))
        logger.info("SWE-bench pass@%d = %.4f", int(k), value)
        return float(assert_value(value, assertion_operator, _coerce_numeric(assertion_expected), message=message))

    @keyword(name="Load Aider Benchmark Dataset")
    def load_aider_benchmark_dataset(self, limit: int | None = None) -> list[Task]:
        """Load the Aider exercism-style benchmark (mini-fixture in Phase 3)."""
        from . import aider_bench

        return aider_bench.AiderBenchLoader.load(limit=limit)

    @keyword(name="Run Aider Benchmark Task")
    def run_aider_benchmark_task(
        self, task: Task | dict[str, Any], driver: str = "local", model: str | None = None
    ) -> RunResult:
        """Dispatch an Aider exercise; score with the upstream check()."""
        return self._run_with_validator(task, driver, model, aider_validate)

    @keyword(name="Aider Benchmark Pass Rate")
    def aider_benchmark_pass_rate(
        self,
        results: list[RunResult],
        assertion_operator: AssertionOperator | None = None,
        assertion_expected: Any = None,
        message: str | None = None,
    ) -> float:
        """Compute Aider's first-run pass rate. With ``assertion_operator`` also asserts.

        Typical assertion: ``Aider Benchmark Pass Rate ${results} >= 0.5``.
        """
        value = first_run_pass_rate(results)
        logger.info("Aider first-run pass rate = %.4f", value)
        return float(assert_value(value, assertion_operator, _coerce_numeric(assertion_expected), message=message))

    @keyword(name="Load HumanEval Dataset")
    def load_humaneval_dataset(self, limit: int | None = None) -> list[Task]:
        """Load HumanEval (``openai_humaneval`` HF dataset; mini-fixture fallback)."""
        from . import humaneval

        return humaneval.HumanEvalLoader.load(limit=limit)

    @keyword(name="Run HumanEval Task")
    def run_humaneval_task(
        self, task: Task | dict[str, Any], driver: str = "local", model: str | None = None
    ) -> RunResult:
        """Dispatch a HumanEval task and score with the bundled ``check()``."""
        return self._run_with_validator(task, driver, model, humaneval_validate)

    @keyword(name="HumanEval Pass At K")
    def humaneval_pass_at_k(
        self,
        results: list[RunResult],
        k: int = 1,
        assertion_operator: AssertionOperator | None = None,
        assertion_expected: Any = None,
        message: str | None = None,
    ) -> float:
        """Compute HumanEval pass@k. With ``assertion_operator`` also asserts.

        Typical assertion: ``HumanEval Pass At K ${results} 1 >= 0.6``.
        """
        value = pass_at_k_from_results(results, int(k))
        logger.info("HumanEval pass@%d = %.4f", int(k), value)
        return float(assert_value(value, assertion_operator, _coerce_numeric(assertion_expected), message=message))

    @keyword(name="Load MBPP Dataset")
    def load_mbpp_dataset(self, limit: int | None = None) -> list[Task]:
        """Load MBPP (HF ``mbpp`` dataset; mini-fixture fallback)."""
        from . import mbpp

        return mbpp.MBPPLoader.load(limit=limit)

    @keyword(name="Run MBPP Task")
    def run_mbpp_task(self, task: Task | dict[str, Any], driver: str = "local", model: str | None = None) -> RunResult:
        """Dispatch an MBPP task and exec the bundled ``test_list`` asserts."""
        return self._run_with_validator(task, driver, model, mbpp_validate)

    @keyword(name="MBPP Pass At K")
    def mbpp_pass_at_k(
        self,
        results: list[RunResult],
        k: int = 1,
        assertion_operator: AssertionOperator | None = None,
        assertion_expected: Any = None,
        message: str | None = None,
    ) -> float:
        """Compute MBPP pass@k. With ``assertion_operator`` also asserts.

        Typical assertion: ``MBPP Pass At K ${results} 1 >= 0.6``.
        """
        value = pass_at_k_from_results(results, int(k))
        logger.info("MBPP pass@%d = %.4f", int(k), value)
        return float(assert_value(value, assertion_operator, _coerce_numeric(assertion_expected), message=message))

    @keyword(name="Load LiveCodeBench Dataset")
    def load_livecodebench_dataset(self, limit: int | None = None) -> list[Task]:
        """Load LiveCodeBench (``livecodebench/code_generation_lite``; mini-fixture fallback)."""
        from . import livecodebench

        return livecodebench.LiveCodeBenchLoader.load(limit=limit)

    @keyword(name="Run LiveCodeBench Task")
    def run_livecodebench_task(
        self, task: Task | dict[str, Any], driver: str = "local", model: str | None = None
    ) -> RunResult:
        """Dispatch an LCB task; exec public+private cases against stdin/stdout."""
        return self._run_with_validator(task, driver, model, lcb_validate)

    @keyword(name="Run Benchmark Suite")
    def run_benchmark_suite(
        self,
        name: str,
        limit: int | None = None,
        driver: str = "local",
        model: str | None = None,
    ) -> dict[str, Any]:
        """Load → iterate → score in one keyword.

        Returns ``{"name", "tasks", "results", "score"}`` so suite authors can
        drop the dict directly into a baseline-diff keyword. Unknown ``name``
        raises ``KeyError`` with the list of accepted names.
        """
        loader_cls = get_loader(name)
        tasks = loader_cls.load(limit=limit)
        runner = self._runner_for(loader_cls.name)
        results: list[RunResult] = [runner(t, driver=driver, model=model) for t in tasks]
        score = loader_cls.score(results)
        logger.info(
            "Run Benchmark Suite %r: n=%d  pass_rate=%.4f  score=%s",
            name,
            len(results),
            pass_rate(results),
            json.dumps(score),
        )
        return {"name": loader_cls.name, "tasks": tasks, "results": results, "score": score}

    def _run_with_validator(
        self,
        task: Task | dict[str, Any],
        driver: str,
        model: str | None,
        validator: Any,
    ) -> RunResult:
        coerced = coerce_task(task)
        drv = resolve_driver(driver, self._provider)
        cfg = driver_config(model or self._default_model, None)
        start = time.perf_counter()
        dr = drv.run(coerced.prompt, cfg)
        candidate = extract_code(dr.stdout or "")
        passed, output = validator(candidate, coerced)
        return make_run_result(
            coerced,
            passed=passed,
            duration_s=time.perf_counter() - start,
            diff=candidate or None,
            test_output=output,
            driver_result=dr,
        )

    def _runner_for(self, canonical_name: str) -> Any:
        runners = {
            "humaneval": self.run_humaneval_task,
            "mbpp": self.run_mbpp_task,
            "livecodebench": self.run_livecodebench_task,
            "swe_bench": self.run_swe_bench_task,
            "aider": self.run_aider_benchmark_task,
        }
        try:
            return runners[canonical_name]
        except KeyError as exc:  # pragma: no cover - registry guards this
            raise KeyError(f"No runner for {canonical_name!r}; expected one of {BENCHMARK_NAMES}") from exc


# Backwards-compat alias used by ``DynamicCore`` registration patterns.
CodingBenchmarkLibrary = CodingBenchmarkKeywords
