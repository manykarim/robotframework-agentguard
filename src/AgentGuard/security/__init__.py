"""AgentGuard.security — default-deny skill scanner, redactor, sandbox policy.

Public surface:

- :class:`SecurityKeywords` — Robot Framework keyword class composed into
  the top-level ``AgentGuard`` library via ``DynamicCore``.
- :func:`scanner.scan_skill` — pure-Python entry point used by tests.
- :func:`redactor.redact` / :func:`redactor.redact_dict` — secret + PII
  redaction for trajectories.
- :func:`aidefence.scan` / :func:`aidefence.has_pii` — MCP-backed wrappers
  with conservative local fallbacks.
- :class:`sandbox.SandboxPolicy` + :func:`sandbox.probe_backend` — Phase-1
  sandbox declaration and host-capability probe.

See ``docs/adr/ADR-006``, ``ADR-013``, ``ADR-020`` and
``docs/security/`` for the design contract.
"""

from AgentGuard.security.library import SecurityKeywords
from AgentGuard.security.types import (
    AIDefenceResult,
    Decision,
    Finding,
    PIIResult,
    SandboxUnavailable,
    ScannerStage,
    SecurityError,
    Severity,
    SkillSecurityError,
    SkillSecurityReport,
)

__all__ = [
    "SecurityKeywords",
    "Severity",
    "ScannerStage",
    "Finding",
    "Decision",
    "SkillSecurityReport",
    "AIDefenceResult",
    "PIIResult",
    "SecurityError",
    "SkillSecurityError",
    "SandboxUnavailable",
]
