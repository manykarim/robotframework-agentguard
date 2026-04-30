"""Tests for the 7-stage skill scanner pipeline (ADR-006, ADR-020).

`AgentGuard.security.scanner.scan_skill` returns a `SkillSecurityReport`
with `decision in {"allow", "warn", "deny"}` and a list of `Finding`s.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from AgentGuard.security import scanner
from AgentGuard.security.types import (
    Decision,
    Finding,
    ScannerStage,
    Severity,
    SkillSecurityReport,
)


FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "security"


@pytest.fixture(autouse=True)
def _force_local_aidefence(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the regex local fallback so unit tests don't depend on the MCP server."""
    monkeypatch.setenv("AGENTGUARD_AIDEFENCE_DISABLE", "1")
    from AgentGuard.security import aidefence

    aidefence._MCPSession._instance = None


class TestSeverity:
    def test_rank_order(self) -> None:
        assert Severity.CRITICAL.rank > Severity.HIGH.rank > Severity.MEDIUM.rank > Severity.INFO.rank

    def test_parse_uppercases(self) -> None:
        assert Severity.parse("high") == Severity.HIGH
        assert Severity.parse(Severity.CRITICAL) == Severity.CRITICAL


class TestSkillSecurityReportProperties:
    def test_max_severity_none_when_no_findings(self, tmp_path: Path) -> None:
        report = SkillSecurityReport(skill_name="x", skill_path=tmp_path)
        assert report.max_severity is None

    def test_counts_zero_baseline(self, tmp_path: Path) -> None:
        report = SkillSecurityReport(skill_name="x", skill_path=tmp_path)
        assert all(v == 0 for v in report.counts.values())

    def test_max_severity_with_mix(self, tmp_path: Path) -> None:
        f1 = Finding(
            stage=ScannerStage.FRONTMATTER, severity=Severity.MEDIUM,
            message="m", remediation="r",
        )
        f2 = Finding(
            stage=ScannerStage.PII_SCAN, severity=Severity.HIGH,
            message="m", remediation="r",
        )
        report = SkillSecurityReport(
            skill_name="x", skill_path=tmp_path, findings=(f1, f2)
        )
        assert report.max_severity == Severity.HIGH


class TestScanSkillFixtures:
    def test_clean_skill_allows(self) -> None:
        report = scanner.scan_skill(FIXTURES / "clean-skill", allow_unsigned=True)
        assert report.decision in ("allow", "warn")
        # No CRITICAL findings.
        assert all(f.severity != Severity.CRITICAL for f in report.findings)

    def test_curl_pipe_denies_or_warns(self) -> None:
        report = scanner.scan_skill(
            FIXTURES / "curl-pipe-skill", allow_unsigned=True
        )
        # The static analyser must flag a curl|sh pattern as HIGH or CRITICAL.
        assert report.decision in ("warn", "deny")
        assert any(
            f.stage == ScannerStage.SCRIPTS_STATIC for f in report.findings
        )

    def test_injection_skill_findings(self) -> None:
        # Locally fall back to regex (no MCP) — should still flag the injection.
        report = scanner.scan_skill(
            FIXTURES / "injection-skill", allow_unsigned=True
        )
        # AIDefence stage emits at least one finding (HIGH or CRITICAL).
        injection_findings = [
            f for f in report.findings if f.stage == ScannerStage.AIDEFENCE_INJECTION
        ]
        assert injection_findings, "expected AIDefence to flag the injection skill"


class TestScanSkillResolution:
    def test_directory_input(self, tmp_path: Path) -> None:
        d = tmp_path / "s"
        d.mkdir()
        (d / "SKILL.md").write_text("---\nname: x\ndescription: y\n---\nbody\n")
        report = scanner.scan_skill(d, allow_unsigned=True)
        assert report.skill_path == d.resolve()

    def test_md_file_input(self, tmp_path: Path) -> None:
        d = tmp_path / "s"
        d.mkdir()
        f = d / "SKILL.md"
        f.write_text("---\nname: x\ndescription: y\n---\nbody\n")
        report = scanner.scan_skill(f, allow_unsigned=True)
        assert report.skill_path == d.resolve()

    def test_invalid_path_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            scanner.scan_skill(tmp_path / "nope.txt", allow_unsigned=True)

    def test_non_path_object_raises(self) -> None:
        with pytest.raises(TypeError):
            scanner.scan_skill(12345, allow_unsigned=True)


class TestDecisionMatrix:
    def test_critical_finding_denies(self) -> None:
        critical = Finding(
            stage=ScannerStage.AIDEFENCE_INJECTION, severity=Severity.CRITICAL,
            message="m", remediation="r",
        )
        decision, reason = scanner._decide(
            findings=[critical],
            signature_status="valid",
            allow_unsigned=True,
            publisher="anthropic",
        )
        assert decision == "deny"

    def test_high_finding_warns(self) -> None:
        high = Finding(
            stage=ScannerStage.PII_SCAN, severity=Severity.HIGH,
            message="m", remediation="r",
        )
        decision, _ = scanner._decide(
            findings=[high],
            signature_status="valid",
            allow_unsigned=True,
            publisher="anthropic",
        )
        assert decision == "warn"

    def test_unsigned_third_party_denied_by_default(self) -> None:
        decision, _ = scanner._decide(
            findings=[],
            signature_status="missing",
            allow_unsigned=False,
            publisher="randomvendor",
        )
        assert decision == "deny"

    def test_unsigned_third_party_allowed_when_flag_set(self) -> None:
        decision, _ = scanner._decide(
            findings=[],
            signature_status="missing",
            allow_unsigned=True,
            publisher="randomvendor",
        )
        assert decision == "allow"

    def test_first_party_unsigned_allowed(self) -> None:
        decision, _ = scanner._decide(
            findings=[],
            signature_status="missing",
            allow_unsigned=False,
            publisher="anthropic",
        )
        assert decision == "allow"


class TestSecurityKeywords:
    def test_skill_should_pass_security_scan_clean(self) -> None:
        from AgentGuard.security.library import SecurityKeywords

        kw = SecurityKeywords()
        report = kw.skill_should_pass_security_scan(
            FIXTURES / "clean-skill", allow_unsigned=True, max_severity="HIGH"
        )
        assert isinstance(report, SkillSecurityReport)

    def test_skill_should_pass_security_scan_critical_raises(self, tmp_path: Path) -> None:
        from AgentGuard.security.library import SecurityKeywords
        from AgentGuard.security.types import SkillSecurityError

        # Build a skill that triggers a CRITICAL via missing SKILL.md.
        bogus = tmp_path / "ghost"
        bogus.mkdir()
        # SKILL.md absent → stage1 emits CRITICAL.
        kw = SecurityKeywords()
        with pytest.raises(SkillSecurityError):
            kw.skill_should_pass_security_scan(bogus, allow_unsigned=True)

    def test_sandbox_should_be_available_unknown_backend(self) -> None:
        from AgentGuard.security.library import SecurityKeywords
        from AgentGuard.security.types import SandboxUnavailable

        kw = SecurityKeywords()
        with pytest.raises(SandboxUnavailable):
            kw.sandbox_should_be_available(backend="carrier-pigeon")
