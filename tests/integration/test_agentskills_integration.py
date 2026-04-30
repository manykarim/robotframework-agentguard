"""Integration — exercise AgentGuard's Skills + Security keywords against the
``robotframework-agentskills`` skill catalogue.

Two paths:

1. **Bundled fixture mode (always runs)** — load + validate + scan the small
   subset committed under ``tests/fixtures/integrations/skills/``.
2. **Discovered mode (runs when an upstream clone is reachable)** — scan every
   skill under the ``manykarim/robotframework-agentskills`` working tree.
   Auto-detected at ``~/workspace/robotframework-agentskills/skills`` and at
   the standard ``.claude/skills`` install root.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from AgentGuard.security.library import SecurityKeywords
from AgentGuard.skills.library import SkillsKeywords

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "integrations" / "skills"
LOCAL_CLONE = Path.home() / "workspace" / "robotframework-agentskills" / "skills"


# Force the local AIDefence regex fallback so security tests don't try to spawn
# the claude-flow MCP server during integration runs.
@pytest.fixture(autouse=True)
def _disable_aidefence_mcp() -> None:
    os.environ["AGENTGUARD_AIDEFENCE_DISABLE"] = "1"


@pytest.fixture
def skills() -> SkillsKeywords:
    return SkillsKeywords(
        default_model="mockllm/model", default_judge_model="mockllm/model"
    )


@pytest.fixture
def security() -> SecurityKeywords:
    return SecurityKeywords()


# ---- bundled-fixture mode (always runs) -----------------------------------


@pytest.mark.parametrize(
    "skill_dir",
    [
        FIXTURE_ROOT / "rf-libdoc-search",
        FIXTURE_ROOT / "rf-browser-skill",
    ],
)
def test_bundled_skill_loads_and_validates(
    skills: SkillsKeywords, skill_dir: Path
) -> None:
    skill = skills.load_skill(skill_dir)
    skills.validate_skill_frontmatter(skill)
    assert skill.description
    assert skill.name


def test_bundled_skill_passes_security_scan(
    security: SecurityKeywords,
) -> None:
    # ADR-006 default-deny means *every* unsigned third-party skill is denied;
    # `allow_unsigned=True` bypasses the signature gate so we can assert on the
    # remaining (real) security findings instead. A first-party reference
    # skill must have NO CRITICAL findings.
    report = security.skill_should_pass_security_scan(
        FIXTURE_ROOT / "rf-libdoc-search", allow_unsigned=True, max_severity="HIGH"
    )
    crits = [f for f in report.findings if f.severity.name == "CRITICAL"]
    assert not crits, f"unexpected CRITICAL findings: {crits}"


def test_bundled_skill_grades_offline_with_mockllm(
    skills: SkillsKeywords,
) -> None:
    sc = skills.run_skill_eval(
        str(FIXTURE_ROOT / "rf-libdoc-search"),
        runs=1,
        model="mockllm/model",
        judge_model="mockllm/model",
        prompts=["Find a keyword that creates a temp file."],
    )
    assert sc.skill_name == "rf-libdoc-search"
    assert sc.runs >= 1


# ---- discovered mode (runs only when upstream clone is reachable) ----------


_HAVE_LOCAL_CLONE = LOCAL_CLONE.exists() and any(LOCAL_CLONE.iterdir())


@pytest.mark.skipif(
    not _HAVE_LOCAL_CLONE,
    reason="no local manykarim/robotframework-agentskills checkout under ~/workspace",
)
def test_discovered_skills_validate(skills: SkillsKeywords) -> None:
    seen = 0
    for child in LOCAL_CLONE.iterdir():
        skill_md = child / "SKILL.md"
        if not skill_md.exists():
            continue
        skill = skills.load_skill(child)
        skills.validate_skill_frontmatter(skill)
        seen += 1
    # The upstream repo ships 11 skills as of 2026-04; fall back to ≥3 to be
    # robust against ongoing churn.
    assert seen >= 3, f"only validated {seen} skills under {LOCAL_CLONE}"


@pytest.mark.skipif(
    not _HAVE_LOCAL_CLONE, reason="no local agentskills checkout"
)
def test_discovered_skills_have_no_critical_findings(
    security: SecurityKeywords,
) -> None:
    # ADR-006 default-deny applies to every unsigned skill. We bypass with
    # allow_unsigned=True (these ARE first-party skills the user owns) and
    # assert the scanner finds no actual CRITICAL issues.
    flagged = []
    for child in LOCAL_CLONE.iterdir():
        if not (child / "SKILL.md").exists():
            continue
        report = security.scan_skill(child)
        crits = [f for f in report.findings if f.severity.name == "CRITICAL"]
        if crits:
            flagged.append((child.name, [f.message for f in crits]))
    assert not flagged, f"upstream skills with CRITICAL findings: {flagged}"


@pytest.mark.skipif(
    not _HAVE_LOCAL_CLONE, reason="no local agentskills checkout"
)
def test_discover_skills_via_keyword(skills: SkillsKeywords) -> None:
    # discover() iterates each root's immediate subdirs looking for SKILL.md,
    # so we point it at the `skills/` directory itself (not its parent).
    out = skills.discover_skills(roots=[LOCAL_CLONE], enforce_allowlist=False)
    assert isinstance(out, dict)
    flat = [s for bucket in out.values() for s in bucket]
    assert len(flat) >= 3, f"only discovered {len(flat)} skills under {LOCAL_CLONE}"
