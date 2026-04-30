"""Integration — full security scanner pipeline against the 3 fixture skills."""

from __future__ import annotations

from pathlib import Path

import pytest

from AgentGuard.security.library import SecurityKeywords

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "security"


@pytest.fixture
def sec() -> SecurityKeywords:
    return SecurityKeywords()


def test_clean_skill_passes_scan(sec: SecurityKeywords) -> None:
    report = sec.scan_skill(FIXTURES / "clean-skill")
    assert report.decision in {"allow", "warn"}, report


def test_injection_skill_is_denied(sec: SecurityKeywords) -> None:
    report = sec.scan_skill(FIXTURES / "injection-skill")
    assert report.decision == "deny", report


def test_curl_pipe_skill_is_denied(sec: SecurityKeywords) -> None:
    report = sec.scan_skill(FIXTURES / "curl-pipe-skill")
    assert report.decision == "deny", report


def test_redactor_masks_bearer_token(sec: SecurityKeywords) -> None:
    text = "Authorization: Bearer abcdefgh1234567890XX"
    redacted = sec.redact_trajectory(text, mode="tokenize")
    assert "abcdefgh" not in redacted
    assert "<REDACTED" in redacted


def test_redactor_masks_anthropic_key(sec: SecurityKeywords) -> None:
    text = "X-Api-Key: sk-ant-abcdefghijklmnopqrstuv"
    redacted = sec.redact_trajectory(text, mode="strict")
    assert "abcdefghijklmnopqrstuv" not in redacted
