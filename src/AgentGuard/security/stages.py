"""Per-stage helpers for the 7-stage scanner pipeline.

Split out of ``scanner.py`` so the orchestrator stays readable and so each
file remains under the 300-line module budget. Every function here is
pure: it takes a parsed skill description and returns a list of findings.
"""

from __future__ import annotations

import importlib
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

from AgentGuard.security import aidefence, static_analysis
from AgentGuard.security.types import Finding, ScannerStage, Severity

logger = logging.getLogger("AgentGuard.security.stages")

DEFAULT_TOOL_ALLOWLIST: frozenset[str] = frozenset(
    {"Read", "Write", "Edit", "Bash", "Grep", "Glob"}
)


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Return ``(frontmatter_dict, body)`` for a SKILL.md text blob."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        loaded = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}, parts[2].lstrip("\n")
    if not isinstance(loaded, dict):
        return {}, parts[2].lstrip("\n")
    return loaded, parts[2].lstrip("\n")


def _f(stage: ScannerStage, sev: Severity, msg: str, rem: str, loc: str, rule: str) -> Finding:
    return Finding(stage=stage, severity=sev, message=msg, remediation=rem, location=loc, rule_id=rule)


def stage1_frontmatter(skill_md: Path) -> tuple[dict[str, Any], str, list[Finding]]:
    findings: list[Finding] = []
    if not skill_md.exists():
        findings.append(_f(
            ScannerStage.FRONTMATTER, Severity.CRITICAL,
            f"SKILL.md not found at {skill_md}",
            "Create SKILL.md with at least `name` and `description`.",
            str(skill_md), "AGRD-S-001"))
        return {}, "", findings

    text = skill_md.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = split_frontmatter(text)

    try:
        parser_mod = importlib.import_module("AgentGuard.skills.parser")
        validator = getattr(parser_mod, "validate_frontmatter", None)
        if callable(validator):
            try:
                validator(frontmatter)
            except Exception as exc:  # noqa: BLE001
                findings.append(_f(
                    ScannerStage.FRONTMATTER, Severity.HIGH,
                    f"Frontmatter rejected by skills parser: {exc}",
                    "Fix the frontmatter to match the Agent Skills spec.",
                    f"{skill_md}:frontmatter", "AGRD-S-002"))
            return frontmatter, body, findings
    except ImportError:
        pass

    for key in ("name", "description"):
        if not frontmatter.get(key):
            findings.append(_f(
                ScannerStage.FRONTMATTER, Severity.HIGH,
                f"Frontmatter missing required field {key!r}.",
                f"Add `{key}: ...` to the YAML frontmatter.",
                f"{skill_md}:frontmatter", "AGRD-S-003"))
    return frontmatter, body, findings


def stage2_allowed_tools(
    frontmatter: dict[str, Any], override: Sequence[str] | None
) -> list[Finding]:
    declared = frontmatter.get("allowed-tools")
    if declared is None:
        return []
    if not isinstance(declared, list):
        return [_f(
            ScannerStage.ALLOWED_TOOLS, Severity.HIGH,
            "`allowed-tools` must be a YAML list.",
            "Use `allowed-tools: [Read, Write, ...]` syntax.",
            "frontmatter:allowed-tools", "AGRD-S-200")]

    allowlist: frozenset[str] = (
        frozenset(override) if override is not None else DEFAULT_TOOL_ALLOWLIST
    )
    findings: list[Finding] = []
    for idx, tool in enumerate(declared):
        if not isinstance(tool, str):
            findings.append(_f(
                ScannerStage.ALLOWED_TOOLS, Severity.HIGH,
                f"`allowed-tools[{idx}]` is not a string.",
                "Each entry must be a tool name string.",
                f"frontmatter:allowed-tools[{idx}]", "AGRD-S-201"))
            continue
        if tool not in allowlist:
            findings.append(_f(
                ScannerStage.ALLOWED_TOOLS, Severity.HIGH,
                f"Tool {tool!r} is not in the configured allowlist.",
                "Either remove the tool or widen the scanner's allowlist.",
                f"frontmatter:allowed-tools[{idx}]", "AGRD-S-202"))
    return findings


def stage3_scripts(skill_dir: Path) -> list[Finding]:
    return static_analysis.scan_directory(skill_dir / "scripts")


def stage4_aidefence(body: str, skill_dir: Path, threshold: float) -> list[Finding]:
    findings: list[Finding] = []
    _scan_block(findings, body, "SKILL.md:body", threshold)
    references = skill_dir / "references"
    if references.exists() and references.is_dir():
        for ref in sorted(references.rglob("*.md")):
            try:
                _scan_block(findings, ref.read_text(encoding="utf-8", errors="replace"),
                            str(ref), threshold)
            except OSError as exc:
                findings.append(_f(
                    ScannerStage.AIDEFENCE_INJECTION, Severity.MEDIUM,
                    f"Could not read reference {ref.name}: {exc}",
                    "Ensure the reference is readable.", str(ref), "AGRD-S-401"))
    return findings


def _scan_block(sink: list[Finding], text: str, location: str, threshold: float) -> None:
    if not text.strip():
        return
    result = aidefence.scan(text)
    if result.injection_score < threshold:
        return
    sev = Severity.CRITICAL if result.injection_score >= 0.85 else Severity.HIGH
    labels = ", ".join(result.findings) if result.findings else "unspecified"
    sink.append(_f(
        ScannerStage.AIDEFENCE_INJECTION, sev,
        f"AIDefence flagged prompt-injection (score={result.injection_score:.2f}, "
        f"labels={labels}, source={result.source}).",
        "Remove or rephrase the flagged passage; if legitimate, review with "
        "`--allow-suspicious-skill`.",
        location, "AGRD-S-400"))


def stage5_signature(
    skill_dir: Path, frontmatter: dict[str, Any]
) -> tuple[str, list[Finding]]:
    sig_file = skill_dir / "SKILL.md.sig"
    skillsig = skill_dir / ".skillsig"
    declared = bool(frontmatter.get("signed"))
    if sig_file.exists() or skillsig.exists() or declared:
        loc = str(sig_file if sig_file.exists() else (skillsig if skillsig.exists() else skill_dir))
        return "stub", [_f(
            ScannerStage.SIGNATURE, Severity.INFO,
            "Signature artifact present — full cosign verification ships in Phase 2.",
            "No action; Phase 2 performs cryptographic verification.",
            loc, "AGRD-S-500")]
    return "missing", [_f(
        ScannerStage.SIGNATURE, Severity.INFO,
        "Skill is unsigned (no SKILL.md.sig / .skillsig / `signed: true`).",
        "Pass `allow_unsigned=True` to accept, or sign via cosign before distribution.",
        str(skill_dir), "AGRD-S-501")]


def stage6_marketplace(
    skill_dir: Path, skill_name: str, override: Sequence[str] | None
) -> list[Finding]:
    allowlist: list[str] = list(override) if override is not None else []
    repo_allow = _find_allowlist_file(skill_dir)
    if repo_allow is not None:
        allowlist.extend(repo_allow)
    if not allowlist:
        return [_f(
            ScannerStage.MARKETPLACE, Severity.INFO,
            "No marketplace allowlist configured — skipping reputation check.",
            "Provide `.agentguard-allow.txt` or pass `marketplace_allowlist=`.",
            str(skill_dir), "AGRD-S-600")]
    if skill_name in allowlist:
        return []
    return [_f(
        ScannerStage.MARKETPLACE, Severity.HIGH,
        f"Skill {skill_name!r} not present in configured allowlist.",
        f"Add `{skill_name}` to .agentguard-allow.txt after manual review.",
        str(skill_dir), "AGRD-S-601")]


def stage7_pii(body: str) -> list[Finding]:
    if not body.strip():
        return []
    result = aidefence.has_pii(body)
    if not result.detected:
        return []
    return [_f(
        ScannerStage.PII_SCAN, Severity.HIGH,
        f"PII detected in SKILL.md body (types={', '.join(result.types) or 'unspecified'}, "
        f"source={result.source}).",
        "Remove personal data; use placeholders such as `<EMAIL>`.",
        "SKILL.md:body", "AGRD-S-700")]


def _find_allowlist_file(skill_dir: Path) -> list[str] | None:
    for parent in [skill_dir, *skill_dir.parents]:
        candidate = parent / ".agentguard-allow.txt"
        if candidate.exists() and candidate.is_file():
            try:
                return [
                    ln.strip()
                    for ln in candidate.read_text(encoding="utf-8").splitlines()
                    if ln.strip() and not ln.lstrip().startswith("#")
                ]
            except OSError:
                return None
    return None
