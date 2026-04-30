"""Skills bounded context — Agent Skill discovery, parsing, grading.

Public surface (also re-exported by the top-level ``AgentGuard`` library):

- :class:`SkillsKeywords` — the Robot Framework keyword class
- :class:`Skill` — parsed skill data model
- :class:`SkillScorecard` / :class:`SkillResponse` — eval result types
- :func:`discover` — programmatic discovery (non-RF callers)
- :func:`parse_skill` / :func:`validate_skill` — parser API

ADR references: ADR-006 (default-deny allowlist), ADR-014 (spec pinning),
ADR-020 (AIDefence skill scanner integration).
"""

from AgentGuard.skills.conventions import (
    ConventionReport,
    Violation,
    check_responses,
    check_text,
)
from AgentGuard.skills.discovery import (
    ALLOWLIST_FILENAME,
    DEFAULT_ROOTS,
    DiscoveryResult,
    discover,
)
from AgentGuard.skills.grader import GraderConfig, run_skill_eval
from AgentGuard.skills.library import SkillsKeywords, SkillsLibrary
from AgentGuard.skills.parser import (
    SKILL_NAME_RE,
    Skill,
    SkillParseError,
    parse_skill,
    parse_skill_text,
    validate_skill,
)
from AgentGuard.skills.scorecard import (
    JudgeScore,
    SkillResponse,
    SkillScorecard,
    hash_rubric,
)

__all__ = [
    "ALLOWLIST_FILENAME",
    "ConventionReport",
    "DEFAULT_ROOTS",
    "DiscoveryResult",
    "GraderConfig",
    "JudgeScore",
    "SKILL_NAME_RE",
    "Skill",
    "SkillParseError",
    "SkillResponse",
    "SkillScorecard",
    "SkillsKeywords",
    "SkillsLibrary",
    "Violation",
    "check_responses",
    "check_text",
    "discover",
    "hash_rubric",
    "parse_skill",
    "parse_skill_text",
    "run_skill_eval",
    "validate_skill",
]
