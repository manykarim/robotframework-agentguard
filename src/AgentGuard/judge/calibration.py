"""Inter-rater agreement for judge calibration (ADR-011, research §2.7).

Implements Cohen's κ for a pair of raters and a defensive (k-rater) version
of Krippendorff's α for nominal data. Both are pure-Python; no sklearn
dependency is required.

Cohen's κ formula
-----------------

    κ = (p_o − p_e) / (1 − p_e)

where ``p_o`` is the observed agreement (fraction of items where the two
raters chose the same category) and ``p_e`` is the expected agreement under
chance, computed from the marginal frequencies of each rater::

    p_e = Σ_c  P_rater1(c) · P_rater2(c)

Manual worked example (`tests/unit/judge/test_calibration.py::test_cohens_kappa_known_value`):

    rater_a = ['good','good','bad','partial','bad','good']
    rater_b = ['good','partial','bad','partial','bad','good']

      n = 6
      agreements = 5  → p_o = 5/6 = 0.8333
      marginals A = good:3/6, partial:1/6, bad:2/6
      marginals B = good:2/6, partial:2/6, bad:2/6
      p_e = 3/6·2/6 + 1/6·2/6 + 2/6·2/6 = (6+2+4)/36 = 12/36 = 0.3333
      κ = (0.8333 − 0.3333) / (1 − 0.3333) = 0.5 / 0.6667 = 0.75

So `cohens_kappa(rater_a, rater_b) == 0.75` exactly.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_CACHE_PATH = Path(".agentguard/judge_calibration.json")
DEFAULT_EXPIRY_SECONDS = 30 * 24 * 3600  # 30 days
DEFAULT_KAPPA_THRESHOLD = 0.7


class JudgeNotCalibratedError(RuntimeError):
    """Raised when a judge is asked to score before passing calibration."""


@dataclass(slots=True)
class CalibrationReport:
    """Outcome of running a judge across a labeled set."""

    model: str
    rubric_fingerprint: str
    set_fingerprint: str
    n_items: int
    n_agree: int
    kappa: float
    per_criterion_kappa: dict[str, float] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    threshold: float = DEFAULT_KAPPA_THRESHOLD
    notes: str = ""

    @property
    def passed(self) -> bool:
        return self.kappa >= self.threshold


# ---------------------------------------------------------------------------
# Cohen's κ
# ---------------------------------------------------------------------------


def cohens_kappa(predicted: Sequence[str], human: Sequence[str]) -> float:
    """Cohen's κ for two raters over the same N items (categorical labels).

    Returns ``1.0`` when the two raters agree on every item, ``0.0`` when
    agreement equals chance, and negative values when worse than chance.

    Edge cases
    ----------
    * Empty inputs raise ``ValueError`` (κ is undefined).
    * If both raters give the same single label everywhere, ``p_e == 1`` and we
      return ``1.0`` by convention (perfect, trivial agreement).
    """
    if len(predicted) != len(human):
        raise ValueError(f"cohens_kappa requires equal-length inputs (got {len(predicted)} vs {len(human)}).")
    n = len(predicted)
    if n == 0:
        raise ValueError("cohens_kappa requires at least one item.")

    n_agree = sum(1 for a, b in zip(predicted, human, strict=True) if a == b)
    p_o = n_agree / n

    cnt_a = Counter(predicted)
    cnt_b = Counter(human)
    categories = set(cnt_a) | set(cnt_b)
    p_e = sum((cnt_a.get(c, 0) / n) * (cnt_b.get(c, 0) / n) for c in categories)

    if p_e >= 1.0:
        # Both raters used a single identical label — agreement is by definition.
        return 1.0 if p_o >= 1.0 else 0.0
    return (p_o - p_e) / (1.0 - p_e)


# ---------------------------------------------------------------------------
# Krippendorff's α (nominal)
# ---------------------------------------------------------------------------


def krippendorff_alpha(
    ratings: Sequence[Sequence[str | None]],
) -> float:
    """Krippendorff's α for nominal data, multi-rater.

    Parameters
    ----------
    ratings : Sequence[Sequence[str | None]]
        Matrix shape ``(n_raters, n_items)``. ``None`` marks a missing value
        (rater did not score that item).

    Returns
    -------
    float
        α in ``[-∞, 1.0]`` (nominally bounded, but rounding can push slightly
        outside ``[0, 1]`` for adversarial inputs).

    Notes
    -----
    Implements the coincidence-matrix formula (Krippendorff 2011 §3.2). Used
    for >2 raters; for 2-rater calibration prefer :func:`cohens_kappa`.
    """
    if not ratings or not ratings[0]:
        raise ValueError("krippendorff_alpha requires a non-empty ratings matrix.")

    n_items = len(ratings[0])
    if any(len(row) != n_items for row in ratings):
        raise ValueError("All raters must rate the same number of items.")

    # Per-item value counts (skipping None).
    coincidences: dict[tuple[str, str], float] = {}
    item_totals: list[int] = []
    for j in range(n_items):
        col_raw = [row[j] for row in ratings if row[j] is not None]
        col: list[str] = [v for v in col_raw if v is not None]
        m = len(col)
        item_totals.append(m)
        if m < 2:
            continue
        for i, a in enumerate(col):
            for b in col[:i] + col[i + 1 :]:
                key = (a, b)
                coincidences[key] = coincidences.get(key, 0.0) + 1.0 / (m - 1)

    n = sum(item_totals)
    if n < 2:
        raise ValueError("Need at least 2 valid ratings overall to compute α.")

    # Marginal value counts.
    value_totals: dict[str, float] = {}
    for (a, _b), c in coincidences.items():
        value_totals[a] = value_totals.get(a, 0.0) + c

    # Disagreement (nominal): D_o = Σ_{a≠b} o_ab; D_e = (Σ n_a · n_b for a≠b) / (n − 1)
    d_o = sum(c for (a, b), c in coincidences.items() if a != b)
    d_e_num = sum(value_totals[a] * value_totals[b] for a in value_totals for b in value_totals if a != b)
    d_e = d_e_num / (n - 1)

    if d_e == 0:
        return 1.0
    return 1.0 - (d_o / d_e)


# ---------------------------------------------------------------------------
# Calibration cache
# ---------------------------------------------------------------------------


def _cache_key(model: str, rubric_fp: str, set_fp: str) -> str:
    return f"{model}|{rubric_fp}|{set_fp}"


def load_cached_calibration(
    model: str,
    rubric_fingerprint: str,
    set_fingerprint: str,
    cache_path: Path = DEFAULT_CACHE_PATH,
    expiry_seconds: float = DEFAULT_EXPIRY_SECONDS,
) -> CalibrationReport | None:
    """Return a non-expired cached report, or ``None`` if absent/stale."""
    if not cache_path.exists():
        return None
    try:
        store: dict[str, Any] = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    entry = store.get(_cache_key(model, rubric_fingerprint, set_fingerprint))
    if not entry:
        return None
    if time.time() - float(entry.get("timestamp", 0)) > expiry_seconds:
        return None
    try:
        return CalibrationReport(**entry)
    except TypeError:
        return None


def save_calibration(
    report: CalibrationReport,
    cache_path: Path = DEFAULT_CACHE_PATH,
) -> None:
    """Persist `report` to the on-disk cache (creates parent dirs)."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    store: dict[str, Any] = {}
    if cache_path.exists():
        try:
            store = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            store = {}
    key = _cache_key(report.model, report.rubric_fingerprint, report.set_fingerprint)
    store[key] = asdict(report)
    cache_path.write_text(json.dumps(store, indent=2, sort_keys=True), encoding="utf-8")
