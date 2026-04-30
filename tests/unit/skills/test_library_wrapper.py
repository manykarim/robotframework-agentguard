"""Direct unit tests for ``SkillsKeywords`` — the Robot keyword wrapper layer."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from AgentGuard.skills.library import SkillsKeywords
from AgentGuard.skills.parser import Skill
from AgentGuard.skills.scorecard import SkillResponse, SkillScorecard

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "skills"


@pytest.fixture
def kw() -> SkillsKeywords:
    return SkillsKeywords(default_model="mockllm/model", default_judge_model="mockllm/model")


# ---------------- discovery & parsing ----------------


def test_load_skill_from_directory(kw: SkillsKeywords) -> None:
    skill = kw.load_skill(FIXTURES / "good-skill")
    assert skill.name == "good-example"


def test_load_skill_from_file_path(kw: SkillsKeywords) -> None:
    skill = kw.load_skill(FIXTURES / "good-skill" / "SKILL.md")
    assert skill.name == "good-example"


def test_load_skill_bad_raises(kw: SkillsKeywords) -> None:
    with pytest.raises(Exception):
        kw.load_skill(FIXTURES / "bad-skill")


def test_validate_skill_frontmatter_passes(kw: SkillsKeywords) -> None:
    skill = kw.load_skill(FIXTURES / "good-skill")
    kw.validate_skill_frontmatter(skill)


def test_discover_skills_with_explicit_root(kw: SkillsKeywords) -> None:
    out = kw.discover_skills(roots=[FIXTURES], enforce_allowlist=False)
    assert isinstance(out, dict)


def test_discover_skills_full_returns_result_object(kw: SkillsKeywords) -> None:
    result = kw.discover_skills_full(roots=[FIXTURES], enforce_allowlist=False)
    assert hasattr(result, "by_tool")
    assert hasattr(result, "errors")


# ---------------- model interaction ----------------


def test_skill_output_for_prompts_empty_returns_empty(kw: SkillsKeywords) -> None:
    skill = kw.load_skill(FIXTURES / "good-skill")
    assert kw.skill_output_for_prompts(skill, prompts=[]) == []


def test_skill_output_for_prompts_no_provider_uses_mock(kw: SkillsKeywords) -> None:
    skill = kw.load_skill(FIXTURES / "good-skill")
    out = kw.skill_output_for_prompts(skill, prompts=["hi", "bye"], runs=2)
    assert len(out) == 4
    assert all(isinstance(r, SkillResponse) for r in out)
    assert all(r.model == "mockllm/model" for r in out)


@dataclass
class _Usage:
    prompt_tokens: int = 5
    completion_tokens: int = 7


@dataclass
class _Resp:
    text: str = "ok"
    usage: _Usage = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.usage is None:
            self.usage = _Usage()


def test_skill_output_for_prompts_with_provider() -> None:
    provider = type("P", (), {"chat": lambda self, **kw: _Resp(text="hi-back")})()
    kw = SkillsKeywords(provider=provider, default_model="m")
    skill = Skill(
        name="x-skill",
        description="d",
        allowed_tools=[],
        body="body",
        scripts=[],
        references=[],
        assets=[],
        source_path=Path("/tmp/x"),
        source_tool="claude",
    )
    out = kw.skill_output_for_prompts(skill, prompts=["a"], runs=1)
    assert out[0].output == "hi-back"


# ---------------- evaluation ----------------


def test_run_skill_eval_offline_with_mockllm(kw: SkillsKeywords) -> None:
    sc = kw.run_skill_eval(
        str(FIXTURES / "good-skill"),
        runs=2,
        model="mockllm/model",
        judge_model="mockllm/model",
        prompts=["one", "two"],
    )
    assert isinstance(sc, SkillScorecard)
    assert sc.skill_name == "good-example"


def test_run_skill_eval_with_inline_rubric(kw: SkillsKeywords) -> None:
    sc = kw.run_skill_eval(
        str(FIXTURES / "good-skill"),
        runs=1,
        rubric="Be helpful.",
        prompts=["help"],
    )
    assert sc.runs >= 1


def test_run_skill_eval_with_rubric_path(tmp_path: Path, kw: SkillsKeywords) -> None:
    rub = tmp_path / "r.md"
    rub.write_text("# Correctness\n- Good [1.0]\n", encoding="utf-8")
    sc = kw.run_skill_eval(str(FIXTURES / "good-skill"), runs=1, rubric=str(rub), prompts=["x"])
    assert sc is not None


# ---------------- conventions ----------------


def test_convention_violation_rate_passes_when_clean(kw: SkillsKeywords) -> None:
    responses = ["The weather is sunny.", "Done."]
    report = kw.convention_violation_rate_should_be_below(responses, threshold=0.99)
    assert report.rate < 0.99


def test_convention_violation_rate_raises_when_high(tmp_path: Path, kw: SkillsKeywords) -> None:
    rules = tmp_path / "CLAUDE.md"
    rules.write_text("# Banned phrases\n- simply\n- obviously\n", encoding="utf-8")
    responses = ["This is simply great.", "Obviously correct.", "simply fine"]
    with pytest.raises(AssertionError, match="convention violation rate"):
        kw.convention_violation_rate_should_be_below(responses, rules=str(rules), threshold=0.05)


def test_convention_violation_accepts_skill_response_objects(kw: SkillsKeywords) -> None:
    responses = [
        SkillResponse(prompt="p", output="output text", run_index=0, model="m"),
    ]
    report = kw.convention_violation_rate_should_be_below(responses, threshold=0.99)
    assert report is not None


# ---------------- baseline IO ----------------


def test_save_and_load_baseline_roundtrip(tmp_path: Path, kw: SkillsKeywords) -> None:
    sc = kw.run_skill_eval(str(FIXTURES / "good-skill"), runs=1, model="mockllm/model", prompts=["x"])
    out_path = tmp_path / "baseline.json"
    kw.save_baseline(sc, out_path)
    assert out_path.exists()
    parsed = json.loads(out_path.read_text(encoding="utf-8"))
    assert parsed["skill_name"] == "good-example"
    loaded = kw.load_baseline(out_path)
    assert loaded.skill_name == "good-example"


def test_read_rubric_returns_none_for_none(kw: SkillsKeywords) -> None:
    assert kw._read_rubric(None) is None


def test_read_rubric_returns_inline_string(kw: SkillsKeywords) -> None:
    assert kw._read_rubric("inline rubric text") == "inline rubric text"


def test_system_prompt_for_skill_with_allowed_tools() -> None:
    skill = Skill(
        name="s",
        description="d",
        allowed_tools=["Read", "Write"],
        body="hello",
        scripts=[],
        references=[],
        assets=[],
        source_path=Path("/tmp/s"),
        source_tool="claude",
    )
    text = SkillsKeywords._system_prompt_for(skill)
    assert "Read" in text and "Write" in text and "hello" in text
