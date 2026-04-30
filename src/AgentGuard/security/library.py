"""Robot Framework keyword surface for the security module.

Composed into the top-level ``AgentGuard`` library via ``DynamicCore``
(see ``AgentGuard.library._SUB_LIBRARIES``). Each keyword wraps a
deterministic helper from ``scanner`` / ``redactor`` / ``aidefence`` /
``sandbox`` so unit tests can call those helpers directly without going
through Robot Framework.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from robot.api.deco import keyword

from AgentGuard.security import aidefence, redactor, sandbox, scanner
from AgentGuard.security.types import (
    AIDefenceResult,
    PIIResult,
    SandboxUnavailable,
    Severity,
    SkillSecurityError,
    SkillSecurityReport,
)

__all__ = ["SecurityKeywords"]


class SecurityKeywords:
    """Robot keywords for skill scanning, trajectory redaction, sandbox probing."""

    ROBOT_LIBRARY_SCOPE = "SUITE"

    def __init__(self, provider: Any | None = None) -> None:
        # ``provider`` is unused today (security keywords are deterministic)
        # but accepted to satisfy the DynamicCore composition contract.
        self._provider = provider

    # ------------------------------------------------------------------
    # Skill scanning
    # ------------------------------------------------------------------

    @keyword(name="Skill Should Pass Security Scan")
    def skill_should_pass_security_scan(
        self,
        skill: object | Path | str,
        allow_unsigned: bool = False,
        max_severity: str = "MEDIUM",
    ) -> SkillSecurityReport:
        """Run the full pipeline; raise ``SkillSecurityError`` if findings exceed
        ``max_severity`` or the decision is ``deny``.
        """
        report = scanner.scan_skill(skill, allow_unsigned=allow_unsigned)
        threshold = Severity.parse(max_severity)
        worst = report.max_severity
        if report.decision == "deny":
            raise SkillSecurityError(report)
        if worst is not None and worst.rank > threshold.rank:
            raise SkillSecurityError(report)
        return report

    @keyword(name="Scan Skill")
    def scan_skill(self, skill: object | Path | str) -> SkillSecurityReport:
        """Run the pipeline; return the report without asserting."""
        return scanner.scan_skill(skill)

    # ------------------------------------------------------------------
    # Trajectory secret / PII handling
    # ------------------------------------------------------------------

    @keyword(name="Trajectory Should Not Leak Secrets")
    def trajectory_should_not_leak_secrets(
        self,
        trajectory: list[dict[str, Any]] | str,
        redact: bool = True,
    ) -> str:
        """Scan a serialized trajectory for credentials / PII.

        Raises ``AssertionError`` when secrets are found. When ``redact`` is
        ``True`` the redacted form is returned; otherwise the original text.
        """
        text = redactor.serialize_trajectory(trajectory)
        secrets = redactor.find_secrets(text)
        if secrets:
            kinds = sorted({k for k, _ in secrets})
            raise AssertionError(
                f"Trajectory leaks {len(secrets)} secret(s) of kind(s): {', '.join(kinds)}"
            )
        return redactor.redact(text) if redact else text

    @keyword(name="Redact Trajectory")
    def redact_trajectory(
        self,
        trajectory: list[dict[str, Any]] | str,
        mode: str = "balanced",
    ) -> str:
        """Return a redacted version of ``trajectory``.

        ``mode`` is ``strict`` | ``balanced`` | ``tokenize`` per the spec.
        """
        if mode not in ("strict", "balanced", "tokenize"):
            raise ValueError(
                f"Unknown redact mode {mode!r}; expected strict | balanced | tokenize."
            )
        text = redactor.serialize_trajectory(trajectory)
        return redactor.redact(text, mode=mode)  # type: ignore[arg-type]

    @keyword(name="AIDefence Should Find No Injection")
    def aidefence_should_find_no_injection(
        self,
        text: str,
        threshold: float = 0.5,
    ) -> AIDefenceResult:
        """Call AIDefence over MCP; raise if the injection score >= ``threshold``."""
        result = aidefence.scan(text)
        if result.injection_score >= threshold:
            raise AssertionError(
                f"AIDefence flagged prompt-injection: score={result.injection_score:.2f}, "
                f"labels={', '.join(result.findings) or 'unspecified'}, source={result.source}"
            )
        return result

    @keyword(name="Trajectory Should Not Contain PII")
    def trajectory_should_not_contain_pii(
        self,
        trajectory: list[dict[str, Any]] | str,
        types: list[str] | None = None,
    ) -> PIIResult:
        """Call AIDefence ``has_pii`` on a trajectory; raise if PII is found."""
        text = redactor.serialize_trajectory(trajectory)
        result = aidefence.has_pii(text)
        if result.detected:
            if types is None or any(t in result.types for t in types):
                raise AssertionError(
                    f"Trajectory contains PII (types={', '.join(result.types) or 'unspecified'}, "
                    f"source={result.source})."
                )
        return result

    # ------------------------------------------------------------------
    # Sandbox probing
    # ------------------------------------------------------------------

    @keyword(name="Sandbox Should Be Available")
    def sandbox_should_be_available(self, backend: str = "docker") -> dict[str, str]:
        """Probe ``backend``; return version/capabilities or raise
        ``SandboxUnavailable``."""
        if backend not in ("docker", "k8s", "proxmox", "process"):
            raise SandboxUnavailable(f"Unknown sandbox backend {backend!r}.")
        return sandbox.probe_backend(backend)  # type: ignore[arg-type]

    @keyword(name="Run In Sandbox")
    def run_in_sandbox(
        self,
        command: list[str] | str,
        image: str | None = None,
        backend: str | None = None,
        timeout_seconds: int | None = None,
        allow_code_execution: bool = True,
        network_allowed: bool = False,
    ) -> Any:
        """Execute ``command`` inside the configured sandbox; return ``SandboxResult``.

        Defaults to a docker backend with ``network=none``, read-only fs, dropped caps.
        ``allow_code_execution`` defaults to True at the keyword level (the suite
        author has explicitly opted in by calling this keyword) but the underlying
        SandboxPolicy still validates every other invariant.
        """
        from dataclasses import replace

        policy = sandbox.policy_from_env()
        overrides: dict[str, Any] = {}
        if backend is not None:
            overrides["backend"] = backend
        if allow_code_execution and not policy.allow_code_execution:
            overrides["allow_code_execution"] = True
        if network_allowed and not policy.network_allowed:
            overrides["network_allowed"] = True
        if overrides:
            policy = replace(policy, **overrides)
        kwargs: dict[str, Any] = {}
        if image is not None:
            kwargs["image"] = image
        if timeout_seconds is not None:
            kwargs["timeout_seconds"] = timeout_seconds
        return sandbox.run_in_sandbox(policy, command, **kwargs)

    @keyword(name="Sandbox Output Should Contain")
    def sandbox_output_should_contain(self, result: Any, expected: str) -> None:
        """Assert ``expected`` substring is present in ``result.stdout`` (or stderr)."""
        stdout = getattr(result, "stdout", "") or ""
        stderr = getattr(result, "stderr", "") or ""
        if expected not in stdout and expected not in stderr:
            raise AssertionError(
                f"Sandbox output does not contain {expected!r}. "
                f"stdout[:200]={stdout[:200]!r}, stderr[:200]={stderr[:200]!r}"
            )

    @keyword(name="Sandbox Exit Code Should Be")
    def sandbox_exit_code_should_be(self, result: Any, expected: int) -> None:
        """Assert ``result.exit_code == expected``."""
        actual = getattr(result, "exit_code", None)
        if actual != expected:
            raise AssertionError(
                f"Sandbox exit code mismatch: expected {expected}, got {actual!r}"
            )
