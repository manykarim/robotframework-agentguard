"""Internal helpers for ``judge.library`` — keeps the public surface < 300 lines.

Nothing here is part of the public API; do not import from outside the
``judge`` subpackage.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import time
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from robot.api import logger

from AgentGuard.judge.calibration import CalibrationReport, cohens_kappa
from AgentGuard.judge.rubric import Criterion, Label, Rubric
from AgentGuard.judge.types import CalibrationSample, JudgmentResult

if TYPE_CHECKING:  # pragma: no cover
    from AgentGuard.providers.base import LLMProviderAdapter


def load_calibration_set(
    source: str | Path | Sequence[CalibrationSample],
) -> list[CalibrationSample]:
    """JSONL file loader (one record per line) or pass-through for in-memory lists."""
    if isinstance(source, (str, Path)):
        path = Path(source)
        rows: list[CalibrationSample] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            obj = json.loads(stripped)
            rows.append(
                CalibrationSample(
                    input=str(obj.get("input", "")),
                    response=str(obj.get("response", "")),
                    human_label={
                        k: str(v) for k, v in (obj.get("human_label") or {}).items()
                    },
                    metadata=obj.get("metadata") or {},
                )
            )
        return rows
    return list(source)


def fingerprint_samples(samples: Sequence[CalibrationSample]) -> str:
    """Stable SHA-256 of the calibration set (for cache keys)."""
    payload = json.dumps(
        [
            {"input": s.input, "response": s.response, "human_label": s.human_label}
            for s in samples
        ],
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def infer_rubric_from_samples(samples: Sequence[CalibrationSample]) -> Rubric:
    """Fallback: build a rubric whose criteria/labels mirror what humans labeled."""
    if not samples:
        raise ValueError("Cannot infer rubric from empty calibration set.")
    seed = samples[0].human_label
    if not seed:
        raise ValueError(
            "First calibration sample has no human_label; pass `rubric=` explicitly."
        )
    label_values: dict[str, set[str]] = {k: set() for k in seed}
    for s in samples:
        for k, v in s.human_label.items():
            label_values.setdefault(k, set()).add(v)
    criteria = tuple(
        Criterion(
            name=cname,
            description="(inferred from calibration set)",
            labels=tuple(
                Label(value=v, description=v, score=label_score_heuristic(v))
                for v in sorted(values)
            ),
        )
        for cname, values in label_values.items()
    )
    return Rubric(name="(inferred)", criteria=criteria)


def label_score_heuristic(value: str) -> float:
    v = value.strip().lower()
    if v in {"good", "correct", "equivalent", "pass", "yes", "true"}:
        return 1.0
    if v in {"partial", "mixed", "borderline"}:
        return 0.5
    return 0.0


def aggregate_calibration(
    judgments: Sequence[JudgmentResult],
    samples: Sequence[CalibrationSample],
    rubric: Rubric,
) -> tuple[float, dict[str, float], int]:
    """Compute (overall κ, per-criterion κ, total agreement count)."""
    predicted: dict[str, list[str]] = {c.name: [] for c in rubric.criteria}
    human: dict[str, list[str]] = {c.name: [] for c in rubric.criteria}
    n_agree = 0
    for sample, judgment in zip(samples, judgments, strict=True):
        for cname in predicted:
            pred = judgment.labels.get(cname, "")
            ref = sample.human_label.get(cname, "")
            predicted[cname].append(pred)
            human[cname].append(ref)
            if pred and ref and pred == ref:
                n_agree += 1
    per_criterion = {
        cname: cohens_kappa(pred_vals, human[cname])
        for cname, pred_vals in predicted.items()
        if any(human[cname])
    }
    overall = (
        statistics.fmean(per_criterion.values()) if per_criterion else 0.0
    )
    return overall, per_criterion, n_agree


def build_calibration_report(
    model: str,
    samples: Sequence[CalibrationSample],
    judgments: Sequence[JudgmentResult],
    rubric: Rubric,
    threshold: float,
    record_only: bool,
) -> CalibrationReport:
    """Aggregate judge predictions into a persistable :class:`CalibrationReport`."""
    overall_kappa, per_criterion_kappa, n_agree = aggregate_calibration(
        judgments, samples, rubric
    )
    return CalibrationReport(
        model=model,
        rubric_fingerprint=rubric.fingerprint(),
        set_fingerprint=fingerprint_samples(samples),
        n_items=len(samples),
        n_agree=n_agree,
        kappa=overall_kappa,
        per_criterion_kappa=per_criterion_kappa,
        timestamp=time.time(),
        threshold=float(threshold),
        notes="record_only" if record_only else "",
    )


def call_provider_with_retry(
    provider: LLMProviderAdapter | None,
    prompt: str,
    model: str | None,
    mock_response: str | None,
    max_retries: int,
) -> str:
    """Single-prompt call against ``provider`` with rate-limit backoff."""
    if provider is None:
        if mock_response is None:
            raise RuntimeError(
                "JudgeKeywords has no provider; pass `mock_response=` for offline tests."
            )
        return mock_response
    from AgentGuard.providers.base import RateLimitError  # lazy import

    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            kwargs: dict[str, Any] = {}
            if mock_response is not None:
                kwargs["mock_response"] = mock_response
            resp = provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                **kwargs,
            )
            return resp.text or ""
        except RateLimitError as exc:
            last_exc = exc
            backoff = 2**attempt
            logger.warn(
                f"Judge call hit rate limit (attempt {attempt + 1}); "
                f"backing off {backoff}s."
            )
            time.sleep(backoff)
    assert last_exc is not None  # for mypy
    raise last_exc


def find_any_fresh_for_model(
    model: str,
    cache_path: Path,
    expiry_seconds: float,
    min_kappa: float,
) -> CalibrationReport | None:
    """Cache scan — most recent non-expired report for ``model`` with κ ≥ min_kappa."""
    if not cache_path.exists():
        return None
    try:
        store: dict[str, Any] = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    now = time.time()
    best: CalibrationReport | None = None
    for entry in store.values():
        if entry.get("model") != model:
            continue
        if now - float(entry.get("timestamp", 0)) > expiry_seconds:
            continue
        try:
            report = CalibrationReport(**entry)
        except TypeError:
            continue
        if report.kappa < min_kappa:
            continue
        if best is None or report.timestamp > best.timestamp:
            best = report
    return best
