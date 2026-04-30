"""7-stage skill scanner — thin orchestrator.

The per-stage logic lives in :mod:`AgentGuard.security.stages`; this module
threads them together, derives the skill name and publisher, and applies
the decision matrix.

See ``docs/security/skill-scanner-spec.md`` §2 for the formal contract.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from AgentGuard.security import stages
from AgentGuard.security.types import (
    Decision,
    Finding,
    Severity,
    SkillSecurityReport,
)

logger = logging.getLogger("AgentGuard.security.scanner")

DEFAULT_FIRST_PARTY_PUBLISHERS: frozenset[str] = frozenset({"agentguard", "anthropic"})


def scan_skill(
    skill: object | Path | str,
    *,
    allow_unsigned: bool = False,
    allowed_tools: Sequence[str] | None = None,
    marketplace_allowlist: Sequence[str] | None = None,
    aidefence_threshold: float = 0.5,
) -> SkillSecurityReport:
    """Run the full 7-stage pipeline against ``skill`` and return a report."""
    skill_dir, skill_md = _resolve_skill(skill)
    skill_name = _derive_skill_name(skill_dir, skill_md)

    findings: list[Finding] = []

    frontmatter, body, fm_findings = stages.stage1_frontmatter(skill_md)
    findings.extend(fm_findings)
    findings.extend(stages.stage2_allowed_tools(frontmatter, allowed_tools))
    findings.extend(stages.stage3_scripts(skill_dir))
    findings.extend(stages.stage4_aidefence(body, skill_dir, aidefence_threshold))

    sig_status, sig_findings = stages.stage5_signature(skill_dir, frontmatter)
    findings.extend(sig_findings)
    findings.extend(stages.stage6_marketplace(skill_dir, skill_name, marketplace_allowlist))
    findings.extend(stages.stage7_pii(body))

    decision, reason = _decide(
        findings=findings,
        signature_status=sig_status,
        allow_unsigned=allow_unsigned,
        publisher=_publisher_of(frontmatter),
    )

    return SkillSecurityReport(
        skill_name=skill_name,
        skill_path=skill_dir,
        findings=tuple(findings),
        decision=decision,
        decision_reason=reason,
        signature_status=sig_status,
    )


def _decide(
    *,
    findings: Sequence[Finding],
    signature_status: str,
    allow_unsigned: bool,
    publisher: str | None,
) -> tuple[Decision, str]:
    """Default decision matrix (`docs/security/skill-scanner-spec.md` §4)."""
    if any(f.severity == Severity.CRITICAL for f in findings):
        return "deny", "At least one CRITICAL finding."

    is_first_party = (publisher or "").lower() in DEFAULT_FIRST_PARTY_PUBLISHERS
    if signature_status in {"missing", "invalid", "untrusted_root"} and not is_first_party:
        if not allow_unsigned:
            return "deny", (
                f"Unsigned third-party skill (signature_status={signature_status}) and allow_unsigned=False."
            )

    if any(f.severity == Severity.HIGH for f in findings):
        return "warn", "At least one HIGH finding."

    return "allow", "All findings at MEDIUM or below."


def _resolve_skill(skill: object | Path | str) -> tuple[Path, Path]:
    if hasattr(skill, "path"):
        skill = skill.path  # type: ignore[assignment]
    if not isinstance(skill, (str, Path)):
        raise TypeError(f"Cannot scan {type(skill).__name__}: provide a path or a Skill object with `.path`.")
    path = Path(skill).expanduser().resolve()
    if path.is_file() and path.name == "SKILL.md":
        return path.parent, path
    if path.is_dir():
        return path, path / "SKILL.md"
    if path.suffix == ".md":
        return path.parent, path
    raise FileNotFoundError(f"Skill path {path} is neither a SKILL.md file nor a directory.")


def _derive_skill_name(skill_dir: Path, skill_md: Path) -> str:
    if skill_md.exists():
        text = skill_md.read_text(encoding="utf-8", errors="replace")
        frontmatter, _ = stages.split_frontmatter(text)
        name = frontmatter.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return skill_dir.name


def _publisher_of(frontmatter: dict[str, Any]) -> str | None:
    publisher = frontmatter.get("publisher") or frontmatter.get("author")
    if isinstance(publisher, str):
        return publisher
    return None
