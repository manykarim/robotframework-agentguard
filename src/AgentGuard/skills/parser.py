"""SKILL.md parser — YAML frontmatter + body + scripts/references/assets enumeration.

Implements the Agent Skills file format (research §2.2). Frontmatter is delimited
by `---` lines. Required keys: `name`, `description`. Optional: `allowed-tools`.
Unknown keys are kept (forwards-compat) but a warning is emitted.

The Skill name MUST match `^[a-z][a-z0-9-]{2,63}$` per the published spec.
"""

from __future__ import annotations

import logging
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("AgentGuard.skills.parser")

#: Compiled regex used by both parser and validator.
SKILL_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{2,63}$")

#: Required and optional frontmatter keys (per Agent Skills spec, 2025-12-18).
_REQUIRED_KEYS: tuple[str, ...] = ("name", "description")
_OPTIONAL_KEYS: tuple[str, ...] = ("allowed-tools",)
_KNOWN_KEYS: frozenset[str] = frozenset(_REQUIRED_KEYS + _OPTIONAL_KEYS)


class SkillParseError(ValueError):
    """Raised when a SKILL.md file cannot be parsed or fails validation."""


@dataclass(slots=True)
class Skill:
    """Parsed Agent Skill — frontmatter + body + ancillary asset paths.

    Attributes mirror the published Agent Skills spec; ``source_tool`` records
    which discovery root surfaced the skill (``claude``/``agents``/``gemini``/
    ``codex``/``project``) and is used by ADR-006 (default-deny allowlist).
    """

    name: str
    description: str
    body: str
    allowed_tools: list[str] = field(default_factory=list)
    scripts: list[Path] = field(default_factory=list)
    references: list[Path] = field(default_factory=list)
    assets: list[Path] = field(default_factory=list)
    source_path: Path | None = None
    source_tool: str = "unknown"
    extra_frontmatter: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """JSON-serialisable view (Path → str)."""
        return {
            "name": self.name,
            "description": self.description,
            "allowed_tools": list(self.allowed_tools),
            "scripts": [str(p) for p in self.scripts],
            "references": [str(p) for p in self.references],
            "assets": [str(p) for p in self.assets],
            "source_path": str(self.source_path) if self.source_path else None,
            "source_tool": self.source_tool,
            "extra_frontmatter": dict(self.extra_frontmatter),
        }


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter_yaml, body) from a SKILL.md text blob.

    Accepts the canonical ``---\\n…\\n---\\n`` envelope. Tolerates a leading
    BOM and CRLF line endings. Raises ``SkillParseError`` if no frontmatter
    block is present.
    """
    cleaned = text.lstrip("﻿").replace("\r\n", "\n")
    if not cleaned.startswith("---"):
        raise SkillParseError("SKILL.md must start with '---' frontmatter delimiter")
    # Drop opening fence (and trailing newline).
    rest = cleaned[3:].lstrip("\n")
    end = rest.find("\n---")
    if end == -1:
        raise SkillParseError("SKILL.md frontmatter is not closed by '---'")
    fm = rest[:end]
    body = rest[end + 4 :]
    if body.startswith("\n"):
        body = body[1:]
    return fm, body


def _enumerate_dir(root: Path, name: str) -> list[Path]:
    sub = root / name
    if not sub.is_dir():
        return []
    return sorted(p for p in sub.rglob("*") if p.is_file())


def parse_skill_text(
    text: str, *, source_path: Path | None = None, source_tool: str = "unknown"
) -> Skill:
    """Parse a SKILL.md ``text`` blob into a :class:`Skill`. No filesystem reads."""
    fm_text, body = _split_frontmatter(text)
    try:
        loaded = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError as exc:
        raise SkillParseError(f"frontmatter is not valid YAML: {exc}") from exc
    if not isinstance(loaded, dict):
        raise SkillParseError("frontmatter must be a YAML mapping")

    missing = [k for k in _REQUIRED_KEYS if k not in loaded or loaded[k] in (None, "")]
    if missing:
        raise SkillParseError(
            f"SKILL.md missing required frontmatter keys: {', '.join(missing)}"
        )

    name = str(loaded["name"]).strip()
    description = str(loaded["description"]).strip()
    allowed_tools_raw: Any = loaded.get("allowed-tools", [])
    allowed_tools = _coerce_allowed_tools(allowed_tools_raw)

    extras = {k: v for k, v in loaded.items() if k not in _KNOWN_KEYS}
    for k in extras:
        warnings.warn(
            f"Unknown SKILL.md frontmatter key '{k}' (forwards-compat: kept in extras)",
            stacklevel=2,
        )

    return Skill(
        name=name,
        description=description,
        body=body,
        allowed_tools=allowed_tools,
        source_path=source_path,
        source_tool=source_tool,
        extra_frontmatter=extras,
    )


def _coerce_allowed_tools(raw: Any) -> list[str]:
    if raw in (None, "", []):
        return []
    if isinstance(raw, str):
        # Comma-separated single-line form is tolerated by some vendors.
        return [item.strip() for item in raw.split(",") if item.strip()]
    if isinstance(raw, list) and all(isinstance(item, str) for item in raw):
        return [item.strip() for item in raw if item.strip()]
    raise SkillParseError(
        "frontmatter 'allowed-tools' must be a list of strings or a comma-separated string"
    )


def parse_skill(path: str | Path, *, source_tool: str = "unknown") -> Skill:
    """Read ``SKILL.md`` from ``path`` (file or directory), parse, enumerate assets.

    If ``path`` is a directory, ``SKILL.md`` inside it is loaded. The returned
    :class:`Skill` carries ``source_path`` set to the SKILL.md file and
    ``scripts`` / ``references`` / ``assets`` populated from sibling directories.
    """
    p = Path(path)
    if p.is_dir():
        skill_md = p / "SKILL.md"
    elif p.is_file():
        skill_md = p
    else:
        raise FileNotFoundError(f"No SKILL.md or skill directory at {p}")
    if not skill_md.is_file():
        raise FileNotFoundError(f"SKILL.md not found at {skill_md}")

    text = skill_md.read_text(encoding="utf-8")
    skill = parse_skill_text(text, source_path=skill_md, source_tool=source_tool)
    root = skill_md.parent
    skill.scripts = _enumerate_dir(root, "scripts")
    skill.references = _enumerate_dir(root, "references")
    skill.assets = _enumerate_dir(root, "assets")
    return skill


def validate_skill(skill: Skill) -> None:
    """Assert the Skill satisfies the published spec. Raises ``SkillParseError``."""
    if not skill.name:
        raise SkillParseError("skill 'name' is empty")
    if not SKILL_NAME_RE.match(skill.name):
        raise SkillParseError(
            f"skill name '{skill.name}' violates regex {SKILL_NAME_RE.pattern}"
        )
    if not skill.description.strip():
        raise SkillParseError("skill 'description' is empty")
    for tool in skill.allowed_tools:
        if not isinstance(tool, str) or not tool.strip():
            raise SkillParseError(
                f"allowed-tools entries must be non-empty strings; got {tool!r}"
            )
