"""Skill ``scripts/`` static analysis (regex heuristics, no AST in Phase 1).

The detector is intentionally conservative: it returns ``Finding`` objects
with severity HIGH or CRITICAL only on patterns that have direct supply-chain
parallels in the threat model (CWE-78 shell injection, CWE-94 code injection,
CWE-502 unsafe deserialisation).
"""

from __future__ import annotations

import base64
import re
from collections.abc import Iterable, Iterator
from pathlib import Path

from AgentGuard.security.types import Finding, ScannerStage, Severity

_DEFAULT_HOST_ALLOWLIST: frozenset[str] = frozenset(
    {
        "127.0.0.1",
        "localhost",
        "::1",
        "github.com",
        "api.github.com",
        "raw.githubusercontent.com",
        "pypi.org",
        "files.pythonhosted.org",
        "registry.npmjs.org",
    }
)

_PIPE_TO_SHELL = re.compile(r"\b(curl|wget|fetch)\b[^\n|]{0,400}\|\s*(sh|bash|zsh|ksh)\b")
_EVAL_CALL = re.compile(r"\beval\s*\(")
_EXEC_CALL = re.compile(r"\bexec\s*\(")
_OS_SYSTEM = re.compile(r"\bos\.system\s*\(")
_PICKLE_LOADS = re.compile(r"\bpickle\.loads\s*\(")
_DUNDER_IMPORT = re.compile(r"\b__import__\s*\(\s*['\"]?[^'\")]*\+")
_SHELL_TRUE = re.compile(r"\bsubprocess\.[A-Za-z_]+\s*\([^)]*shell\s*=\s*True", re.S)
_URL_PATTERN = re.compile(r"\bhttps?://([A-Za-z0-9._\-]+)(?::\d+)?(?:/[^\s'\"]*)?")
_BASE64_BLOB = re.compile(r"['\"]([A-Za-z0-9+/=]{120,})['\"]")


def scan_file(path: Path, host_allowlist: Iterable[str] | None = None) -> list[Finding]:
    """Scan a single script file. Returns an empty list when nothing matched."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [
            Finding(
                stage=ScannerStage.SCRIPTS_STATIC,
                severity=Severity.MEDIUM,
                message=f"Could not read script {path.name}: {exc}",
                remediation="Ensure the file is readable by the test runner.",
                location=str(path),
                rule_id="AGRD-S-300",
            )
        ]

    allowlist = frozenset(host_allowlist) if host_allowlist else _DEFAULT_HOST_ALLOWLIST
    findings: list[Finding] = list(_iter_findings(text, path, allowlist))
    return findings


def _iter_findings(text: str, path: Path, allowlist: frozenset[str]) -> Iterator[Finding]:
    location_for_line = lambda lineno: f"{path}:L{lineno}"  # noqa: E731

    for match in _PIPE_TO_SHELL.finditer(text):
        yield Finding(
            stage=ScannerStage.SCRIPTS_STATIC,
            severity=Severity.CRITICAL,
            message=f"Pipe-to-shell installer pattern detected ({match.group(0)[:60]}...).",
            remediation=("Replace `curl ... | sh` with a checksum-pinned download verified before execution."),
            location=location_for_line(_lineno(text, match.start())),
            rule_id="AGRD-S-101",
        )

    for match in _EVAL_CALL.finditer(text):
        yield Finding(
            stage=ScannerStage.SCRIPTS_STATIC,
            severity=Severity.HIGH,
            message="Use of `eval(` detected.",
            remediation="Replace `eval` with `ast.literal_eval` or explicit parsing.",
            location=location_for_line(_lineno(text, match.start())),
            rule_id="AGRD-S-110",
        )

    for match in _EXEC_CALL.finditer(text):
        yield Finding(
            stage=ScannerStage.SCRIPTS_STATIC,
            severity=Severity.HIGH,
            message="Use of `exec(` detected.",
            remediation="Replace `exec` with explicit code paths.",
            location=location_for_line(_lineno(text, match.start())),
            rule_id="AGRD-S-111",
        )

    for match in _OS_SYSTEM.finditer(text):
        yield Finding(
            stage=ScannerStage.SCRIPTS_STATIC,
            severity=Severity.HIGH,
            message="Use of `os.system(` detected.",
            remediation="Use `subprocess.run([...], shell=False)` with an arg list.",
            location=location_for_line(_lineno(text, match.start())),
            rule_id="AGRD-S-112",
        )

    for match in _PICKLE_LOADS.finditer(text):
        yield Finding(
            stage=ScannerStage.SCRIPTS_STATIC,
            severity=Severity.CRITICAL,
            message="`pickle.loads(` detected — arbitrary-code-execution risk (CWE-502).",
            remediation="Use a safe format such as JSON or msgpack with a schema.",
            location=location_for_line(_lineno(text, match.start())),
            rule_id="AGRD-S-120",
        )

    for match in _DUNDER_IMPORT.finditer(text):
        yield Finding(
            stage=ScannerStage.SCRIPTS_STATIC,
            severity=Severity.HIGH,
            message="Dynamic `__import__` with string concatenation detected.",
            remediation="Use static imports; avoid runtime module-name construction.",
            location=location_for_line(_lineno(text, match.start())),
            rule_id="AGRD-S-130",
        )

    for match in _SHELL_TRUE.finditer(text):
        yield Finding(
            stage=ScannerStage.SCRIPTS_STATIC,
            severity=Severity.HIGH,
            message="`subprocess(..., shell=True)` detected.",
            remediation="Pass an argument list and `shell=False` (the default).",
            location=location_for_line(_lineno(text, match.start())),
            rule_id="AGRD-S-140",
        )

    for match in _URL_PATTERN.finditer(text):
        host = match.group(1).lower()
        if host in allowlist:
            continue
        yield Finding(
            stage=ScannerStage.SCRIPTS_STATIC,
            severity=Severity.MEDIUM,
            message=f"Hard-coded URL to non-allowlisted host: {host}",
            remediation=(
                "Move the host to a configurable setting and add it to the "
                "scanner's host allowlist if it is genuinely required."
            ),
            location=location_for_line(_lineno(text, match.start())),
            rule_id="AGRD-S-150",
        )

    for match in _BASE64_BLOB.finditer(text):
        blob = match.group(1)
        if _looks_like_base64(blob):
            yield Finding(
                stage=ScannerStage.SCRIPTS_STATIC,
                severity=Severity.HIGH,
                message=(f"Embedded base64 blob ({len(blob)} chars) — possible obfuscated payload."),
                remediation="Replace with plain text or load from a verified file.",
                location=location_for_line(_lineno(text, match.start())),
                rule_id="AGRD-S-160",
            )


def _lineno(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _looks_like_base64(value: str) -> bool:
    if len(value) < 100:
        return False
    try:
        base64.b64decode(value, validate=True)
    except (ValueError, TypeError):
        return False
    return True


def scan_directory(root: Path, host_allowlist: Iterable[str] | None = None) -> list[Finding]:
    """Walk every file under ``root`` (treated as a ``scripts/`` dir) and scan it."""
    findings: list[Finding] = []
    if not root.exists() or not root.is_dir():
        return findings
    for entry in sorted(root.rglob("*")):
        if entry.is_file():
            findings.extend(scan_file(entry, host_allowlist))
    return findings
