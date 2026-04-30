"""Skill scorecard — JSON-serialisable result of one ``Run Skill Eval`` call.

Mirrors the format used by ``manykarim/robotframework-agentskills``'s
``rf-skill-eval`` so existing dashboards and baselines remain comparable.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    """Return current UTC time in ISO-8601 (timezone-aware)."""
    return datetime.now(tz=UTC).isoformat()


@dataclass(slots=True)
class SkillResponse:
    """Single (prompt, run) output produced by ``Skill Output For Prompts``."""

    prompt: str
    output: str
    run_index: int = 0
    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class JudgeScore:
    """Per-sample classification verdict (Inspect AI ``Score`` view)."""

    sample_id: str
    value: float
    rationale: str = ""
    raw: str = ""


@dataclass(slots=True)
class SkillScorecard:
    """Aggregate evaluation outcome for a single skill against a model."""

    skill_name: str
    runs: int
    pass_rate: float
    judge_scores: list[JudgeScore] = field(default_factory=list)
    raw_responses: list[SkillResponse] = field(default_factory=list)
    started_at: str = field(default_factory=_utc_now_iso)
    ended_at: str = field(default_factory=_utc_now_iso)
    model: str = ""
    judge_model: str = ""
    rubric_hash: str = ""
    notes: str = ""

    # ---- (de)serialisation -------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str, sort_keys=True)

    def save(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(self.to_json(), encoding="utf-8")
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillScorecard:
        judge_scores = [JudgeScore(**js) for js in data.get("judge_scores", [])]
        raw_responses = [SkillResponse(**rr) for rr in data.get("raw_responses", [])]
        kwargs = {k: v for k, v in data.items() if k not in {"judge_scores", "raw_responses"}}
        return cls(judge_scores=judge_scores, raw_responses=raw_responses, **kwargs)

    @classmethod
    def from_json(cls, text: str) -> SkillScorecard:
        return cls.from_dict(json.loads(text))

    @classmethod
    def load(cls, path: str | Path) -> SkillScorecard:
        return cls.from_json(Path(path).read_text(encoding="utf-8"))

    # ---- caching key -------------------------------------------------------
    def cache_key(self) -> str:
        """Stable digest of (skill_name, model, rubric_hash, runs) for caching."""
        material = f"{self.skill_name}|{self.model}|{self.rubric_hash}|{self.runs}".encode()
        return hashlib.sha256(material).hexdigest()


def hash_rubric(text: str | None) -> str:
    """SHA-256 of a rubric (empty string when absent) — used for cache keys."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()
