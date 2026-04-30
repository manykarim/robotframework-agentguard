"""Value objects for the security module.

These types are deliberately small and frozen so they can be safely shared
across the synchronous keyword facades and the async AIDefence MCP client.

Schema mirrors the formal contract in ``docs/security/skill-scanner-spec.md``
§3 (`SkillSecurityReport`) — the additional fields from the spec
(``rule_id``, ``cwe``, ``policy_sha256``) are optional in Phase 1; the
required minimum is ``stage / severity / message / remediation``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal


class Severity(StrEnum):
    """Finding severity — ordered ``CRITICAL > HIGH > MEDIUM > INFO``."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    INFO = "INFO"

    @property
    def rank(self) -> int:
        return _SEVERITY_RANK[self]

    @classmethod
    def parse(cls, value: str | Severity) -> Severity:
        if isinstance(value, cls):
            return value
        return cls(str(value).upper().strip())


_SEVERITY_RANK: dict[Severity, int] = {
    Severity.INFO: 0,
    Severity.MEDIUM: 1,
    Severity.HIGH: 2,
    Severity.CRITICAL: 3,
}


class ScannerStage(StrEnum):
    """The seven stages of the skill scanner pipeline (per spec §2)."""

    FRONTMATTER = "frontmatter"
    ALLOWED_TOOLS = "allowed_tools"
    SCRIPTS_STATIC = "scripts_static"
    AIDEFENCE_INJECTION = "aidefence_injection"
    SIGNATURE = "signature"
    MARKETPLACE = "marketplace"
    PII_SCAN = "pii_scan"


Decision = Literal["allow", "warn", "deny"]


@dataclass(frozen=True, slots=True)
class Finding:
    """A single scanner finding."""

    stage: ScannerStage
    severity: Severity
    message: str
    remediation: str
    location: str = ""
    rule_id: str = ""


@dataclass(frozen=True, slots=True)
class SkillSecurityReport:
    """Aggregate result of a skill scan."""

    skill_name: str
    skill_path: Path
    findings: tuple[Finding, ...] = field(default_factory=tuple)
    decision: Decision = "allow"
    decision_reason: str = ""
    scanned_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    scanner_version: str = "phase1"
    signature_status: Literal["valid", "invalid", "missing", "expired", "untrusted_root", "stub"] = "stub"

    @property
    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {s.value: 0 for s in Severity}
        for f in self.findings:
            out[f.severity.value] += 1
        return out

    @property
    def max_severity(self) -> Severity | None:
        if not self.findings:
            return None
        return max((f.severity for f in self.findings), key=lambda s: s.rank)


@dataclass(frozen=True, slots=True)
class AIDefenceResult:
    """Outcome of an ``aidefence_scan`` call."""

    injection_score: float
    findings: tuple[str, ...]
    source: Literal["mcp", "local_fallback"] = "mcp"
    raw: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class PIIResult:
    """Outcome of an ``aidefence_has_pii`` call."""

    detected: bool
    types: tuple[str, ...]
    source: Literal["mcp", "local_fallback"] = "mcp"
    raw: dict[str, object] | None = None


class SecurityError(Exception):
    """Base class for every security keyword failure."""


class SkillSecurityError(SecurityError):
    """Raised when a skill scan's decision is ``deny``."""

    def __init__(self, report: SkillSecurityReport) -> None:
        self.report = report
        super().__init__(f"Skill {report.skill_name!r} failed security scan: {report.decision_reason}")


class SandboxUnavailable(SecurityError):
    """Raised when the requested sandbox backend is not available on this host."""
