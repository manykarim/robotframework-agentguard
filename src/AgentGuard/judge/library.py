"""Robot Framework keyword surface for the judge context (ADR-011).

Implements classification-based LLM-as-Judge with calibration gating. All
judge calls flow through an injected provider (default: LiteLLM); offline
unit tests use ``MockProvider`` and rely on ``parse_judge_response`` to
extract the labels from a hand-crafted JSON-tail response.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from robot.api import logger
from robot.api.deco import keyword

from AgentGuard.judge._helpers import (
    build_calibration_report,
    call_provider_with_retry,
    find_any_fresh_for_model,
    infer_rubric_from_samples,
    load_calibration_set,
)
from AgentGuard.judge._prompts import (
    build_pairwise_prompt,
    default_equivalence_rubric,
    extract_pairwise_winner,
    score_from_labels,
)
from AgentGuard.judge.calibration import (
    DEFAULT_CACHE_PATH,
    DEFAULT_EXPIRY_SECONDS,
    DEFAULT_KAPPA_THRESHOLD,
    CalibrationReport,
    JudgeNotCalibratedError,
    load_cached_calibration,
    save_calibration,
)
from AgentGuard.judge.rubric import (
    Rubric,
    format_judge_prompt,
    load_rubric,
    parse_judge_response,
)
from AgentGuard.judge.types import CalibrationSample, JudgmentResult

if TYPE_CHECKING:  # pragma: no cover
    from AgentGuard.providers.base import LLMProviderAdapter


class JudgeKeywords:
    """Classification LLM-as-Judge keywords (Tier-2/3)."""

    def __init__(
        self,
        provider: LLMProviderAdapter | None = None,
        default_model: str | None = None,
        cache_path: Path | str = DEFAULT_CACHE_PATH,
        kappa_threshold: float = DEFAULT_KAPPA_THRESHOLD,
        max_retries: int = 3,
    ) -> None:
        self._provider = provider
        self._default_model = default_model
        self._cache_path = Path(cache_path)
        self._kappa_threshold = float(kappa_threshold)
        self._max_retries = int(max_retries)

    @keyword(name="Load Rubric")
    def load_rubric(self, source: str | Path | dict[str, Any] | Rubric) -> Rubric:
        """Load a rubric from a path (.md / .yaml), a dict, or pass-through."""
        return load_rubric(source)


    @keyword(name="LLM Judge Should Score At Least")
    def llm_judge_should_score_at_least(
        self,
        responses: list[Any] | str,
        rubric: str | Path | Rubric,
        threshold: float,
        model: str | None = None,
        runs: int = 1,
        mock_response: str | None = None,
    ) -> float:
        """Run the classification judge ``runs`` times per response; assert mean ≥ threshold."""
        rubric_obj = load_rubric(rubric)
        items = [responses] if isinstance(responses, str) else list(responses)
        if not items:
            raise ValueError("LLM Judge Should Score At Least: no responses provided.")
        per_response_scores: list[float] = []
        for resp in items:
            run_scores = [
                self._judge_one(
                    response=str(resp), rubric=rubric_obj, model=model,
                    mock_response=mock_response,
                ).score
                for _ in range(int(runs))
            ]
            per_response_scores.append(statistics.fmean(run_scores))
        mean_score = statistics.fmean(per_response_scores)
        logger.info(
            f"LLM Judge mean score = {mean_score:.4f} over "
            f"{len(items)} response(s) × {runs} run(s)  (threshold {threshold:g})"
        )
        if mean_score < float(threshold):
            raise AssertionError(
                f"Mean judge score {mean_score:.4f} is below threshold {threshold:g}."
            )
        return mean_score

    @keyword(name="Tool Output Should Be Semantically Equal")
    def tool_output_should_be_semantically_equal(
        self,
        actual: str,
        expected: str,
        rubric: Rubric | None = None,
        model: str | None = None,
        mock_response: str | None = None,
    ) -> JudgmentResult:
        """Classify ``actual`` against ``expected`` (equivalent / partial / not)."""
        rubric_obj = rubric or default_equivalence_rubric()
        judgment = self._judge_one(
            response=actual,
            rubric=rubric_obj,
            model=model,
            reference=expected,
            mock_response=mock_response,
        )
        if judgment.score < 1.0:
            label = ", ".join(f"{k}={v}" for k, v in judgment.labels.items())
            raise AssertionError(
                f"Output not semantically equivalent (score={judgment.score:.2f}, {label})."
            )
        return judgment

    @keyword(name="LLM Judge Pairwise")
    def llm_judge_pairwise(
        self,
        a: str,
        b: str,
        rubric: str | Path | Rubric,
        model: str | None = None,
        mock_response: str | None = None,
    ) -> str:
        """Return ``"A" | "B" | "TIE"`` for the pairwise winner."""
        prompt = build_pairwise_prompt(a, b, load_rubric(rubric))
        raw = self._call_provider(prompt, model=model, mock_response=mock_response)
        winner = extract_pairwise_winner(raw)
        logger.info(f"Pairwise judge: winner={winner}")
        return winner

    @keyword(name="LLM Judge Reference Based")
    def llm_judge_reference_based(
        self,
        responses: list[str] | str,
        references: list[str] | str,
        rubric: str | Path | Rubric,
        model: str | None = None,
        mock_response: str | None = None,
    ) -> list[JudgmentResult]:
        """Classify each response against its corresponding reference."""
        rubric_obj = load_rubric(rubric)
        resps = [responses] if isinstance(responses, str) else list(responses)
        refs = [references] if isinstance(references, str) else list(references)
        if len(resps) != len(refs):
            raise ValueError(
                f"responses ({len(resps)}) and references ({len(refs)}) must align 1:1."
            )
        return [
            self._judge_one(
                response=r,
                rubric=rubric_obj,
                model=model,
                reference=ref,
                mock_response=mock_response,
            )
            for r, ref in zip(resps, refs, strict=True)
        ]

    @keyword(name="Calibrate Judge")
    def calibrate_judge(
        self,
        model: str,
        calibration_set: str | Path | Sequence[CalibrationSample],
        rubric: str | Path | Rubric | None = None,
        min_kappa: float = DEFAULT_KAPPA_THRESHOLD,
        record_only: bool = False,
        mock_responses: Sequence[str] | None = None,
    ) -> CalibrationReport:
        """Run ``model`` over a labeled set and compute Cohen's κ vs human labels.

        Asserts ``κ >= min_kappa`` unless ``record_only=True``. Persists the
        report to the on-disk cache so future runs can short-circuit via
        :py:meth:`judge_should_be_calibrated`.
        """
        samples = load_calibration_set(calibration_set)
        if not samples:
            raise ValueError("Calibration set is empty.")
        rubric_obj = (
            load_rubric(rubric) if rubric is not None
            else infer_rubric_from_samples(samples)
        )
        judgments = [
            self._judge_one(
                response=s.response, rubric=rubric_obj, model=model,
                reference=s.input or None,
                mock_response=mock_responses[i] if mock_responses else None,
            )
            for i, s in enumerate(samples)
        ]
        report = build_calibration_report(
            model, samples, judgments, rubric_obj, min_kappa, record_only
        )
        save_calibration(report, cache_path=self._cache_path)
        logger.info(
            f"Calibrate Judge: model={model} κ={report.kappa:.4f} "
            f"(n={len(samples)}, threshold={min_kappa:g}) → "
            f"{'PASS' if report.passed else 'FAIL'}"
        )
        if not record_only and not report.passed:
            raise AssertionError(
                f"Judge {model!r} κ={report.kappa:.4f} is below required {min_kappa:g}."
            )
        return report

    @keyword(name="Judge Should Be Calibrated")
    def judge_should_be_calibrated(
        self,
        model: str,
        rubric_fingerprint: str | None = None,
        set_fingerprint: str | None = None,
        expiry_seconds: float = DEFAULT_EXPIRY_SECONDS,
    ) -> CalibrationReport:
        """Look up cached calibration; assert κ ≥ ``self._kappa_threshold`` within expiry."""
        if rubric_fingerprint and set_fingerprint:
            cached = load_cached_calibration(
                model=model,
                rubric_fingerprint=rubric_fingerprint,
                set_fingerprint=set_fingerprint,
                cache_path=self._cache_path,
                expiry_seconds=expiry_seconds,
            )
            if cached is None:
                raise JudgeNotCalibratedError(
                    f"No fresh calibration cached for model={model!r}; "
                    f"run `Calibrate Judge` first."
                )
            if cached.kappa < self._kappa_threshold:
                raise JudgeNotCalibratedError(
                    f"Cached κ={cached.kappa:.4f} for {model!r} is below "
                    f"{self._kappa_threshold:g}."
                )
            return cached

        cached = find_any_fresh_for_model(
            model, self._cache_path, expiry_seconds, self._kappa_threshold
        )
        if cached is None:
            raise JudgeNotCalibratedError(
                f"No fresh calibration with κ ≥ {self._kappa_threshold:g} "
                f"found for model={model!r}."
            )
        return cached


    def _judge_one(
        self,
        response: str,
        rubric: Rubric,
        model: str | None,
        reference: str | None = None,
        mock_response: str | None = None,
    ) -> JudgmentResult:
        prompt = format_judge_prompt(response, rubric, reference=reference)
        raw = self._call_provider(prompt, model=model, mock_response=mock_response)
        labels = parse_judge_response(raw, rubric)
        score = score_from_labels(labels, rubric)
        chosen_model = model or self._default_model or ""
        return JudgmentResult(
            labels=labels,
            score=score,
            raw=raw,
            model=chosen_model,
            rationale=raw.rsplit("\n", 1)[0] if "\n" in raw else "",
        )

    def _call_provider(
        self,
        prompt: str,
        model: str | None = None,
        mock_response: str | None = None,
    ) -> str:
        return call_provider_with_retry(
            self._provider,
            prompt,
            model or self._default_model,
            mock_response,
            self._max_retries,
        )
