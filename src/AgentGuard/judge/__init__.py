"""Judge context — classification-based LLM-as-Judge with calibration gating.

ADR-011: every judge must be calibrated against a human-labeled set
(Cohen's κ ≥ 0.7) before it is allowed to score real CI runs. Bypass via
``--allow-uncalibrated-judge`` is explicit and noisy.

Public re-exports keep `from AgentGuard.judge import …` ergonomic for tests.
"""

from AgentGuard.judge.calibration import (
    CalibrationReport,
    JudgeNotCalibratedError,
    cohens_kappa,
    krippendorff_alpha,
    load_cached_calibration,
)
from AgentGuard.judge.library import JudgeKeywords
from AgentGuard.judge.rubric import (
    Criterion,
    Label,
    Rubric,
    format_judge_prompt,
    load_rubric,
)
from AgentGuard.judge.types import CalibrationSample, JudgmentResult

__all__ = [
    "CalibrationReport",
    "CalibrationSample",
    "Criterion",
    "JudgeKeywords",
    "JudgeNotCalibratedError",
    "JudgmentResult",
    "Label",
    "Rubric",
    "cohens_kappa",
    "format_judge_prompt",
    "krippendorff_alpha",
    "load_cached_calibration",
    "load_rubric",
]
