"""Tests for `AgentGuard.skills.grader` — Inspect AI Task wrapper.

Default-offline path uses Inspect AI's `mockllm/model` (research exp_04). Live
grading lives in `tests/integration/test_skill_grading_live.py`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from AgentGuard.skills.grader import (
    GraderConfig,
    _coerce_skill,
    _compute_pass_rate,
    _resolve_judge_model,
    _resolve_model,
    _score_to_float,
    _skill_system_prompt,
    run_skill_eval,
)
from AgentGuard.skills.parser import Skill
from AgentGuard.skills.scorecard import JudgeScore

FIXTURE_GOOD = Path(__file__).parent.parent.parent / "fixtures" / "skills" / "good-skill"


class TestGraderConfigDefaults:
    def test_default_runs(self) -> None:
        c = GraderConfig()
        assert c.runs == 10
        assert c.rubric is None
        assert c.judge_model is None


class TestCoerceSkill:
    def test_coerce_path(self) -> None:
        s = _coerce_skill(str(FIXTURE_GOOD))
        assert isinstance(s, Skill)
        assert s.name == "good-example"

    def test_coerce_skill_passthrough(self) -> None:
        s = Skill(name="x", description="y", body="b")
        assert _coerce_skill(s) is s


class TestSystemPrompt:
    def test_includes_name_description_body(self) -> None:
        s = Skill(name="my-skill", description="desc", body="DO X")
        out = _skill_system_prompt(s)
        assert "my-skill" in out
        assert "desc" in out
        assert "DO X" in out

    def test_includes_allowed_tools_when_present(self) -> None:
        s = Skill(name="x", description="y", body="b", allowed_tools=["Read", "Write"])
        out = _skill_system_prompt(s)
        assert "Read" in out and "Write" in out


class TestModelResolution:
    def test_resolve_model_prefers_explicit(self) -> None:
        assert _resolve_model("openrouter/foo") == "openrouter/foo"

    def test_resolve_model_falls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AGENTGUARD_DEFAULT_MODEL", raising=False)
        out = _resolve_model(None)
        # Either a configured fallback or "mockllm/model"; both acceptable.
        assert isinstance(out, str) and out

    def test_resolve_judge_model_explicit(self) -> None:
        assert _resolve_judge_model("oai/judge", model="m") == "oai/judge"

    def test_resolve_judge_model_falls_back_to_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AGENTGUARD_JUDGE_MODEL", raising=False)
        out = _resolve_judge_model(None, model="m")
        assert isinstance(out, str) and out


class TestScoreToFloat:
    @pytest.mark.parametrize(
        "raw,expected",
        [(1, 1.0), (0.5, 0.5), (True, 1.0), (False, 0.0)],
    )
    def test_numeric_and_bool(self, raw: Any, expected: float) -> None:
        class _S:
            value = raw

        assert _score_to_float(_S()) == expected

    @pytest.mark.parametrize(
        "raw,expected",
        [("C", 1.0), ("I", 0.0), ("P", 0.5), ("PASS", 1.0), ("FAIL", 0.0), ("?", 0.0)],
    )
    def test_string_codes(self, raw: str, expected: float) -> None:
        class _S:
            value = raw

        assert _score_to_float(_S()) == expected


class TestComputePassRate:
    def test_empty_returns_zero(self) -> None:
        assert _compute_pass_rate([]) == 0.0

    def test_three_of_four(self) -> None:
        scores = [
            JudgeScore(sample_id="a", value=1.0),
            JudgeScore(sample_id="b", value=0.9),
            JudgeScore(sample_id="c", value=0.5),
            JudgeScore(sample_id="d", value=0.0),
        ]
        assert _compute_pass_rate(scores) == pytest.approx(0.75)


class TestRunSkillEval:
    @pytest.fixture(autouse=True)
    def _force_mock(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Default-offline contract — never let a real OPENROUTER_API_KEY leak in.
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.setenv("AGENTGUARD_DEFAULT_MODEL", "mockllm/model")
        monkeypatch.setenv("INSPECT_EVAL_MODEL", "mockllm/model")

    def test_uses_default_prompt_when_none_supplied(self, tmp_path: Path) -> None:
        # `prompts=None` → grader emits a default per-skill prompt.
        cfg = GraderConfig(
            runs=1,
            prompts=None,
            model="mockllm/model",
            log_dir=str(tmp_path / "_inspect"),
        )
        scorecard = run_skill_eval(FIXTURE_GOOD, cfg)
        assert scorecard.skill_name == "good-example"

    def test_runs_against_mockllm(self, tmp_path: Path) -> None:
        # End-to-end: tiny one-prompt eval through the mock provider.
        cfg = GraderConfig(
            runs=1,
            prompts=["Say OK."],
            model="mockllm/model",
            log_dir=str(tmp_path / "_inspect"),
        )
        scorecard = run_skill_eval(FIXTURE_GOOD, cfg)
        assert scorecard.skill_name == "good-example"
        assert scorecard.runs == 1
        # The mock model returns deterministic stub completions.
        assert isinstance(scorecard.pass_rate, float)
