"""Integration — grade a fixture skill end-to-end with mockllm/model (no API key)."""

from __future__ import annotations

from pathlib import Path

import pytest

from AgentGuard.skills.library import SkillsKeywords

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "skills"


def test_load_and_validate_good_skill() -> None:
    sk = SkillsKeywords()
    skill = sk.load_skill(FIXTURES / "good-skill")
    assert skill.name == "good-example"
    sk.validate_skill_frontmatter(skill)


def test_load_bad_skill_raises_at_load_time() -> None:
    sk = SkillsKeywords()
    with pytest.raises(Exception):
        sk.load_skill(FIXTURES / "bad-skill")


def test_run_skill_eval_offline_with_mockllm() -> None:
    sk = SkillsKeywords()
    scorecard = sk.run_skill_eval(
        skill=str(FIXTURES / "good-skill"),
        runs=2,
        model="mockllm/model",
        judge_model="mockllm/model",
        prompts=["Echo hello", "Return 42"],
    )
    assert scorecard.skill_name == "good-example"
    assert scorecard.runs >= 1
