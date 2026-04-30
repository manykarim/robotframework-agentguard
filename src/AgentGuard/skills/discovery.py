"""Cross-vendor skill discovery (research §2.2, ADR-006).

The Agent Skills spec was adopted within ~90 days by 32 tools, each installing
under different paths. This module scans the four canonical roots, classifies
each discovered skill by its source tool, and enforces the default-deny
allowlist (``.agentguard-allow.txt``) for non-project skills.

Discovery itself is pure enumeration; the actual aidefence-backed security scan
is performed by ``AgentGuard.security`` (ADR-020).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from AgentGuard.skills.parser import Skill, SkillParseError, parse_skill

logger = logging.getLogger("AgentGuard.skills.discovery")

#: Canonical install roots — keep ordering stable so report output is reproducible.
DEFAULT_ROOTS: dict[str, Path] = {
    "claude": Path(".claude/skills"),
    "agents": Path(".agents/skills"),
    "gemini": Path.home() / ".gemini" / "antigravity" / "skills",
    "codex": Path.home() / ".codex" / "skills",
}

#: File listing trusted skill directory names, one per line. ADR-006.
ALLOWLIST_FILENAME = ".agentguard-allow.txt"


@dataclass(slots=True)
class DiscoveryResult:
    """Aggregate outcome of one ``discover()`` call."""

    by_tool: dict[str, list[Skill]]
    errors: list[tuple[Path, str]]
    warnings: list[str]

    def all_skills(self) -> list[Skill]:
        return [s for skills in self.by_tool.values() for s in skills]


def _load_allowlist(root: Path) -> set[str]:
    """Read ``.agentguard-allow.txt`` from ``root``; return set of allowed names.

    Lines starting with ``#`` and blank lines are ignored. A missing file means
    'no allowlist' (ADR-006: warning, no hard block — security agent enforces).
    """
    allow_file = root / ALLOWLIST_FILENAME
    if not allow_file.is_file():
        return set()
    entries: set[str] = set()
    for line in allow_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            entries.add(stripped)
    return entries


def _is_project_local(root: Path) -> bool:
    """Project-local roots (``.claude/skills``, ``.agents/skills`` under cwd) are trusted."""
    try:
        resolved = root.resolve()
        cwd = Path.cwd().resolve()
        return cwd in resolved.parents or resolved == cwd
    except OSError:
        return False


def _iter_skill_dirs(root: Path) -> Iterable[Path]:
    """Yield each immediate subdirectory of ``root`` that contains a ``SKILL.md``."""
    if not root.is_dir():
        return
    for child in sorted(root.iterdir()):
        if child.is_dir() and (child / "SKILL.md").is_file():
            yield child


def _resolve_roots(
    roots: list[str | Path] | None,
) -> dict[str, Path]:
    """Normalise the ``roots`` argument to a tool→Path map."""
    if roots is None:
        return dict(DEFAULT_ROOTS)
    resolved: dict[str, Path] = {}
    for entry in roots:
        p = Path(entry)
        # Heuristic tag: prefer the parent directory name to keep classification stable.
        tag = p.parent.name or p.name or "custom"
        # Avoid clobbering identical tags by appending an index.
        original = tag
        i = 1
        while tag in resolved:
            i += 1
            tag = f"{original}-{i}"
        resolved[tag] = p
    return resolved


def discover(
    roots: list[str | Path] | None = None,
    *,
    enforce_allowlist: bool = True,
) -> DiscoveryResult:
    """Discover skills across the four standard roots (or a custom set).

    Returns a :class:`DiscoveryResult` carrying:

    - ``by_tool``: tool-name → list[Skill] (may be empty if a root is absent),
    - ``errors``: skills whose SKILL.md failed to parse,
    - ``warnings``: ADR-006 allowlist warnings for non-project skills.
    """
    by_tool: dict[str, list[Skill]] = {}
    errors: list[tuple[Path, str]] = []
    warning_lines: list[str] = []

    for tool, root in _resolve_roots(roots).items():
        skills: list[Skill] = []
        if not root.is_dir():
            by_tool[tool] = []
            continue
        allowlist = _load_allowlist(root)
        trusted = _is_project_local(root)
        for skill_dir in _iter_skill_dirs(root):
            try:
                skill = parse_skill(skill_dir, source_tool=tool)
            except (SkillParseError, FileNotFoundError, OSError) as exc:
                errors.append((skill_dir, str(exc)))
                continue
            if (
                enforce_allowlist
                and not trusted
                and allowlist
                and skill_dir.name not in allowlist
                and skill.name not in allowlist
            ):
                warning_lines.append(
                    f"third-party skill '{skill.name}' at {skill_dir} not in "
                    f"{ALLOWLIST_FILENAME} (ADR-006 default-deny — load suppressed)"
                )
                logger.warning(warning_lines[-1])
                continue
            if enforce_allowlist and not trusted and not allowlist:
                warning_lines.append(
                    f"third-party skill '{skill.name}' at {skill_dir} loaded without "
                    f"{ALLOWLIST_FILENAME} (ADR-006 — security agent will scan)"
                )
                logger.warning(warning_lines[-1])
            skills.append(skill)
        by_tool[tool] = skills

    return DiscoveryResult(by_tool=by_tool, errors=errors, warnings=warning_lines)
