"""Plain-data types shared across the judge submodule.

Kept import-free of any heavy dependency so they can be used in tests and
docstrings without forcing scipy/litellm to load.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, frozen=True)
class JudgmentResult:
    """One judge call's outcome.

    Attributes
    ----------
    labels : dict[str, str]
        ``{criterion_name: chosen_label_value}``.
    score : float
        Aggregate score in ``[0.0, 1.0]`` — mean of the per-criterion label
        scores defined in the rubric.
    raw : str
        The model's raw response text (chain of thought + JSON).
    model : str
        Identifier of the model that produced this judgment.
    rationale : str
        Free-form rationale extracted from the response (best-effort).
    """

    labels: dict[str, str]
    score: float
    raw: str = ""
    model: str = ""
    rationale: str = ""


@dataclass(slots=True, frozen=True)
class CalibrationSample:
    """One human-labeled item used to calibrate a judge."""

    input: str
    response: str
    human_label: dict[str, str]
    metadata: dict[str, Any] = field(default_factory=dict)
