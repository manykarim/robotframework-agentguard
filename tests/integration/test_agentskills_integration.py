"""Integration — exercise AgentGuard's Skills + Security keywords against the
``robotframework-agentskills`` skill catalogue.

Two paths:

1. **Bundled fixture mode (always runs)** — load + validate + scan the small
   subset committed under ``tests/fixtures/integrations/skills/``.
2. **Discovered mode (runs when an upstream clone is reachable)** — scan every
   skill under the ``manykarim/robotframework-agentskills`` working tree.
   Auto-detected at ``~/workspace/robotframework-agentskills/skills`` and at
   the standard ``.claude/skills`` install root.

PROPOSAL-library-import-structure §3 + §6: imports use the façade form
``from AgentGuard.Skill import Skill`` / ``from AgentGuard.Security import Security``
(Python equivalents of ``Library AgentGuard.Skill`` / ``Library AgentGuard.Security``).

ADR-022: ``Convention Violation Rate Should Be Below`` is collapsed to the
operator form ``Convention Violation Rate ${responses} <= 0.05`` (per
``docs/proposals/keyword-reduction-table.md``). The Skills suite uses the new
operator-driven keyword via the AssertionAdapter contract.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Façade imports — equivalent to `Library AgentGuard.Skill` / `Library AgentGuard.Security`.
from AgentGuard.Security import Security
from AgentGuard.Skill import Skill

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "integrations" / "skills"
LOCAL_CLONE = Path.home() / "workspace" / "robotframework-agentskills" / "skills"


# Force the local AIDefence regex fallback so security tests don't try to spawn
# the claude-flow MCP server during integration runs.
@pytest.fixture(autouse=True)
def _disable_aidefence_mcp() -> None:
    os.environ["AGENTGUARD_AIDEFENCE_DISABLE"] = "1"


@pytest.fixture
def skills() -> Skill:
    # Constructed via the façade alias — proves the production import path
    # works end-to-end. The alias is the same class object as the deep
    # ``SkillsKeywords`` (see tests/unit/test_library_facades.py).
    return Skill(default_model="mockllm/model", default_judge_model="mockllm/model")


@pytest.fixture
def security() -> Security:
    return Security()


# ---- bundled-fixture mode (always runs) -----------------------------------


@pytest.mark.parametrize(
    "skill_dir",
    [
        FIXTURE_ROOT / "rf-libdoc-search",
        FIXTURE_ROOT / "rf-browser-skill",
    ],
)
def test_bundled_skill_loads_and_validates(skills: Skill, skill_dir: Path) -> None:
    skill = skills.load_skill(skill_dir)
    skills.validate_skill_frontmatter(skill)
    assert skill.description
    assert skill.name


def test_bundled_skill_passes_security_scan(security: Security) -> None:
    """``Skill Should Pass Security Scan`` is a domain predicate kept per DDD §6
    (the named keyword reads cleaner than the equivalent inline ``validate``
    expression over the ``SkillSecurityReport`` shape)."""
    # ADR-006 default-deny means *every* unsigned third-party skill is denied;
    # `allow_unsigned=True` bypasses the signature gate so we can assert on the
    # remaining (real) security findings instead. A first-party reference
    # skill must have NO CRITICAL findings.
    report = security.skill_should_pass_security_scan(
        FIXTURE_ROOT / "rf-libdoc-search", allow_unsigned=True, max_severity="HIGH"
    )
    crits = [f for f in report.findings if f.severity.name == "CRITICAL"]
    assert not crits, f"unexpected CRITICAL findings: {crits}"


def test_bundled_skill_grades_offline_with_mockllm(skills: Skill) -> None:
    sc = skills.run_skill_eval(
        str(FIXTURE_ROOT / "rf-libdoc-search"),
        runs=1,
        model="mockllm/model",
        judge_model="mockllm/model",
        prompts=["Find a keyword that creates a temp file."],
    )
    assert sc.skill_name == "rf-libdoc-search"
    assert sc.runs >= 1


# ---- ADR-022 collapsed keyword: Convention Violation Rate (operator form) --


def test_convention_violation_rate_operator_form_offline(skills: Skill) -> None:
    """Operator-form proof: ``Convention Violation Rate ${responses} <= 0.05``.

    The Should-pair ``Convention Violation Rate Should Be Below`` was deleted
    in Phase 4-D per ``docs/proposals/keyword-reduction-table.md``; the Get
    keyword now accepts ``(assertion_operator, assertion_expected, message)``
    via the AssertionAdapter and asserts in-place.

    We run it on a tiny synthetic response set so the test stays default-offline.
    """
    # Clean responses — no convention violations expected; rate should be 0.0.
    rate = skills.convention_violation_rate(
        responses=["Hello, the response is concise and on-topic."],
        assertion_operator="<=",
        assertion_expected=0.05,
    )
    assert isinstance(rate, float)
    assert 0.0 <= rate <= 1.0


def test_convention_violation_rate_pass_through_returns_value(skills: Skill) -> None:
    """No operator -> the keyword returns the rate unchanged (no assertion)."""
    rate = skills.convention_violation_rate(responses=["Hello, the response is concise and on-topic."])
    assert isinstance(rate, float)


# ---- discovered mode (runs only when upstream clone is reachable) ----------


_HAVE_LOCAL_CLONE = LOCAL_CLONE.exists() and any(LOCAL_CLONE.iterdir())


@pytest.mark.skipif(
    not _HAVE_LOCAL_CLONE,
    reason="no local manykarim/robotframework-agentskills checkout under ~/workspace",
)
def test_discovered_skills_validate(skills: Skill) -> None:
    seen = 0
    for child in LOCAL_CLONE.iterdir():
        skill_md = child / "SKILL.md"
        if not skill_md.exists():
            continue
        skill = skills.load_skill(child)
        skills.validate_skill_frontmatter(skill)
        seen += 1
    # The upstream repo ships 11 skills as of 2026-04; fall back to >=3 to be
    # robust against ongoing churn.
    assert seen >= 3, f"only validated {seen} skills under {LOCAL_CLONE}"


@pytest.mark.skipif(not _HAVE_LOCAL_CLONE, reason="no local agentskills checkout")
def test_discovered_skills_have_no_critical_findings(security: Security) -> None:
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


@pytest.mark.skipif(not _HAVE_LOCAL_CLONE, reason="no local agentskills checkout")
def test_discover_skills_via_keyword(skills: Skill) -> None:
    # discover() iterates each root's immediate subdirs looking for SKILL.md,
    # so we point it at the `skills/` directory itself (not its parent).
    out = skills.discover_skills(roots=[LOCAL_CLONE], enforce_allowlist=False)
    assert isinstance(out, dict)
    flat = [s for bucket in out.values() for s in bucket]
    assert len(flat) >= 3, f"only discovered {len(flat)} skills under {LOCAL_CLONE}"
