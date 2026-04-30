"""Robot Framework keyword surface for the statistics context (ADR-005).

Composed by the top-level ``AgentGuard`` library via ``DynamicCore``. The
class accepts an optional ``provider=`` (an ``LLMProviderAdapter``) so it
matches the constructor contract used by the other sub-libraries — Stats
keywords themselves are deterministic Tier-1 and never call the model.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from robot.api import logger
from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn

from AgentGuard.stats._helpers import coerce_outcomes, variance_banner
from AgentGuard.stats.bootstrap import bootstrap_ci
from AgentGuard.stats.cliffs_delta import cliffs_delta as _cliffs_delta
from AgentGuard.stats.cliffs_delta import magnitude as _delta_magnitude
from AgentGuard.stats.mannwhitney import mann_whitney_u
from AgentGuard.stats.pass_at_k import pass_at_k as _pass_at_k
from AgentGuard.stats.tar import tar_a as _tar_a
from AgentGuard.stats.tar import tar_r as _tar_r
from AgentGuard.stats.vargha_delaney import vargha_delaney_a12 as _vd_a12

if TYPE_CHECKING:  # pragma: no cover
    from AgentGuard.providers.base import LLMProviderAdapter

DEFAULT_RUNS_WARN_THRESHOLD = 10  # ADR-005: warn below N=10


class StatsKeywords:
    """Statistics + non-determinism assertion keywords (Tier-1)."""

    def __init__(self, provider: LLMProviderAdapter | None = None) -> None:
        # Provider is accepted for API symmetry; stats keywords are deterministic.
        self._provider = provider

    # ------------------------------------------------------------------
    # Iteration helper
    # ------------------------------------------------------------------

    @keyword(name="Run N Times")
    def run_n_times(
        self,
        runs: int,
        keyword_name: str,
        *args: Any,
        store: str | None = None,
    ) -> list[Any]:
        """Run ``keyword_name`` ``runs`` times and collect the return values.

        ``store`` (optional) — name of a Robot suite variable to set with the
        list of results (e.g. ``store=${samples}``). The variable is set as
        ``@{...}`` so subsequent keywords can iterate it directly.

        ADR-005 mandates ``runs >= 10`` for any LLM-mediated assertion; we
        log a WARN when below that threshold but never fail (local iteration
        with smaller N is supported).
        """
        runs_int = int(runs)
        if runs_int < 1:
            raise ValueError(f"runs must be >= 1; got {runs!r}.")
        if runs_int < DEFAULT_RUNS_WARN_THRESHOLD:
            logger.warn(
                f"Run N Times: runs={runs_int} is below the ADR-005 "
                f"recommended minimum of {DEFAULT_RUNS_WARN_THRESHOLD}. "
                "Statistical assertions will have low power."
            )

        results: list[Any] = []
        builtin = BuiltIn()
        for i in range(runs_int):
            try:
                result = builtin.run_keyword(keyword_name, *args)
            except Exception:  # noqa: BLE001 — surface to RF reporter as-is
                logger.error(f"Run N Times: iteration {i + 1}/{runs_int} failed.")
                raise
            results.append(result)

        if store:
            store_name = store.lstrip("$@&{").rstrip("}")
            builtin.set_suite_variable(f"@{{{store_name}}}", results)
        return results

    # ------------------------------------------------------------------
    # pass@k / TAR
    # ------------------------------------------------------------------

    @keyword(name="Pass At K Should Be Above")
    def pass_at_k_should_be_above(
        self,
        outcomes: list[Any],
        k: int,
        threshold: float,
        metric: str | None = None,
    ) -> float:
        """Assert ``pass@k(outcomes) > threshold`` (HumanEval convention)."""
        coerced = coerce_outcomes(outcomes)
        value = _pass_at_k(coerced, int(k))
        label = metric or "pass@k"
        logger.info(f"{label}@{k} = {value:.4f}  (threshold {threshold:g})")
        if value <= float(threshold):
            raise AssertionError(f"{label}@{k} = {value:.4f} is not above threshold {threshold:g}.")
        return value

    @keyword(name="Total Agreement Rate Should Be Above")
    def total_agreement_rate_should_be_above(
        self,
        outputs: list[Any],
        threshold: float,
        mode: str = "raw",
        parser: Callable[[Any], Any] | None = None,
    ) -> float:
        """Assert ``TARr@N`` (mode=raw) or ``TARa@N`` (mode=answer) > threshold.

        For ``mode='answer'`` callers may supply a ``parser`` callable; if
        omitted we fall back to ``str(out).strip().lower()`` which is enough
        for many short-answer benchmarks.
        """
        mode_norm = mode.lower().strip()
        if mode_norm == "raw":
            value = _tar_r(outputs)
        elif mode_norm in {"answer", "parsed", "tara"}:
            parse_fn = parser or (lambda o: str(o).strip().lower())
            value = _tar_a(outputs, parse_fn)
        else:
            raise ValueError(f"mode must be 'raw' or 'answer'; got {mode!r}.")
        logger.info(f"TAR{'r' if mode_norm == 'raw' else 'a'}@{len(outputs)} = {value:.4f}  (threshold {threshold:g})")
        if value <= float(threshold):
            raise AssertionError(f"Total agreement rate {value:.4f} is not above threshold {threshold:g}.")
        return value

    # ------------------------------------------------------------------
    # Two-sample comparisons
    # ------------------------------------------------------------------

    @keyword(name="Mann Whitney U Should Show Improvement")
    def mann_whitney_u_should_show_improvement(
        self,
        current: list[float],
        baseline: list[float],
        alpha: float = 0.05,
        alternative: str = "greater",
    ) -> float:
        """Assert Mann-Whitney U p-value < ``alpha`` for ``current`` vs ``baseline``."""
        cur = [float(v) for v in current]
        base = [float(v) for v in baseline]
        result = mann_whitney_u(cur, base, alternative=alternative)  # type: ignore[arg-type]
        logger.info(
            f"Mann-Whitney U: stat={result.statistic:.2f}  p={result.pvalue:.4g}  "
            f"alternative={result.alternative}  alpha={alpha:g}"
        )
        if result.pvalue >= float(alpha):
            raise AssertionError(
                f"Mann-Whitney U p={result.pvalue:.4g} is not below alpha={alpha:g} "
                f"(alternative={result.alternative}); cannot conclude improvement."
            )
        return result.pvalue

    @keyword(name="Cliffs Delta Should Be At Least")
    def cliffs_delta_should_be_at_least(
        self,
        current: list[float],
        baseline: list[float],
        delta: float = 0.2,
    ) -> float:
        """Assert Cliff's δ(current, baseline) ≥ ``delta``."""
        cur = [float(v) for v in current]
        base = [float(v) for v in baseline]
        value = _cliffs_delta(cur, base)
        logger.info(f"Cliff's delta = {value:+.4f} ({_delta_magnitude(value)})  required ≥ {delta:g}")
        if value < float(delta):
            raise AssertionError(f"Cliff's delta {value:+.4f} is below required threshold {delta:g}.")
        return value

    @keyword(name="Vargha Delaney A Should Be At Least")
    def vargha_delaney_a_should_be_at_least(
        self,
        current: list[float],
        baseline: list[float],
        threshold: float = 0.6,
    ) -> float:
        """Assert Vargha-Delaney A12(current, baseline) ≥ ``threshold``."""
        cur = [float(v) for v in current]
        base = [float(v) for v in baseline]
        value = _vd_a12(cur, base)
        logger.info(f"Vargha-Delaney A12 = {value:.4f}  required ≥ {threshold:g}")
        if value < float(threshold):
            raise AssertionError(f"Vargha-Delaney A12 {value:.4f} is below required threshold {threshold:g}.")
        return value

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    @keyword(name="Bootstrap Confidence Interval")
    def bootstrap_confidence_interval(
        self,
        samples: list[float],
        statistic: str = "mean",
        confidence: float = 0.95,
        n_resamples: int = 9999,
    ) -> tuple[float, float]:
        """Return ``(low, high)`` bootstrap CI for ``samples``."""
        nums = [float(v) for v in samples]
        ci = bootstrap_ci(
            nums,
            statistic=statistic,
            confidence=float(confidence),
            n_resamples=int(n_resamples),
        )
        logger.info(
            f"Bootstrap {ci.statistic} {confidence:g} CI = [{ci.low:.4f}, {ci.high:.4f}] (n_resamples={ci.n_resamples})"
        )
        return ci.low, ci.high

    @keyword(name="Bootstrap Confidence Interval Should Contain")
    def bootstrap_confidence_interval_should_contain(
        self,
        samples: list[float],
        expected_value: float,
        statistic: str = "mean",
        confidence: float = 0.95,
        n_resamples: int = 9999,
    ) -> tuple[float, float]:
        """Assert ``expected_value`` lies inside the bootstrap CI of ``samples``."""
        low, high = self.bootstrap_confidence_interval(
            samples,
            statistic=statistic,
            confidence=confidence,
            n_resamples=n_resamples,
        )
        if not (low <= float(expected_value) <= high):
            raise AssertionError(f"Expected value {expected_value:g} not in {confidence:g} CI [{low:.4f}, {high:.4f}].")
        return low, high

    # ------------------------------------------------------------------
    # Variance banner (ADR-005 mandate)
    # ------------------------------------------------------------------

    @keyword(name="Compute Variance Banner")
    def compute_variance_banner(self, runs: list[Any]) -> dict[str, Any]:
        """Summarise the observed run-to-run variance for the log.html header.

        Returns a dict with ``n``, ``mean``, ``std``, and ``cv`` (coefficient
        of variation = std/|mean|). Non-numeric runs are skipped with a WARN;
        an all-non-numeric input returns ``cv=None``.
        """
        return variance_banner(runs)
