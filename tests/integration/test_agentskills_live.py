"""Live end-to-end — real OpenRouter LLM grading a robotframework-agentskills SKILL.

Runs only when ``OPENROUTER_API_KEY`` is set (``@pytest.mark.live``). Exercises
the full grading stack against a real model:

    SKILL.md  →  AgentGuard SkillsKeywords.run_skill_eval
              →  Inspect AI Task with the skill body as system message
              →  OpenRouter LLM (gpt-4o-mini)
              →  judge run on the responses
              →  SkillScorecard.

Cost ceiling per run: <$0.01 (gpt-4o-mini, N=2, judge=mockllm/model).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from AgentGuard.config import load_env
from AgentGuard.skills.library import SkillsKeywords

# Load .env before the OPENROUTER_API_KEY skip-check so local runs work the
# same way as CI (where the secret is injected via the workflow's env block).
load_env()

if not os.getenv("OPENROUTER_API_KEY"):
    pytest.skip("OPENROUTER_API_KEY not set", allow_module_level=True)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "integrations" / "skills"
LOCAL_CLONE = Path.home() / "workspace" / "robotframework-agentskills" / "skills"


@pytest.fixture
def skills() -> SkillsKeywords:
    return SkillsKeywords(
        default_model="openrouter/openai/gpt-4o-mini",
        default_judge_model="mockllm/model",  # judge stays mocked to keep cost flat
    )


@pytest.mark.live
def test_grade_bundled_skill_with_real_openrouter_llm(skills: SkillsKeywords) -> None:
    """Grade the bundled ``rf-libdoc-search`` SKILL.md against gpt-4o-mini, N=2."""
    sc = skills.run_skill_eval(
        str(FIXTURE_ROOT / "rf-libdoc-search"),
        runs=2,
        model="openrouter/openai/gpt-4o-mini",
        judge_model="mockllm/model",
        prompts=[
            "Search for keywords related to logging.",
            "Find keywords that create a temp file.",
        ],
    )
    assert sc.skill_name == "rf-libdoc-search"
    assert sc.runs >= 1
    # We don't assert pass_rate — the mockllm judge always passes; the value here
    # is the wiring proof, not the model's quality.


@pytest.mark.live
def test_grade_bundled_browser_skill_with_real_openrouter_llm(
    skills: SkillsKeywords,
) -> None:
    sc = skills.run_skill_eval(
        str(FIXTURE_ROOT / "rf-browser-skill"),
        runs=1,
        model="openrouter/openai/gpt-4o-mini",
        judge_model="mockllm/model",
        prompts=["List two Browser library keywords for filling a text input."],
    )
    assert sc.skill_name == "rf-browser-skill"


@pytest.mark.live
@pytest.mark.skipif(
    not (LOCAL_CLONE.exists() and any(LOCAL_CLONE.iterdir())),
    reason="no local manykarim/robotframework-agentskills checkout under ~/workspace",
)
def test_grade_one_upstream_skill_with_real_openrouter_llm(
    skills: SkillsKeywords,
) -> None:
    """If the full upstream catalogue is on disk, grade the smallest skill live.

    Uses ``robotframework-libdoc-search`` (matches the bundled fixture's intent)
    so the cost stays bounded.
    """
    target = LOCAL_CLONE / "robotframework-libdoc-search"
    if not (target / "SKILL.md").exists():
        pytest.skip("robotframework-libdoc-search not in local clone")
    sc = skills.run_skill_eval(
        str(target),
        runs=1,
        model="openrouter/openai/gpt-4o-mini",
        judge_model="mockllm/model",
        prompts=["Show how to invoke the libdoc search command."],
    )
    assert sc.runs >= 1
