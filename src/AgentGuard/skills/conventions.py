"""Convention-violation checker — regex/AST scan against a project CLAUDE.md.

Implements the ``Convention violation rate`` metric from the #42796 catalog
(research §3.3). The intent is the same as Stella Laurenzo's
``stop-phrase-guard.sh``: catch ownership-dodging language, banned phrasing,
and mutations that violate documented project rules.

The default ruleset is hand-derived from the CLAUDE.md shipped with this repo
(banned filler phrases, root-folder writes, premature test-pass claims). Project
authors override by passing their own CLAUDE.md (or any markdown) and the
checker will mine ``NEVER``/``ALWAYS``/``MUST NOT``/``Don't`` lines from it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

#: Default banned phrases (case-insensitive) — extend via project CLAUDE.md mining.
DEFAULT_BANNED_PHRASES: tuple[str, ...] = (
    r"\bsimply\b",
    r"\bjust\b",
    r"\bobviously\b",
    r"\bclearly\b",
    r"\beasily\b",
    r"\bsimplest\b",
    r"\btrivial\b",
)

#: Default test-pass-without-evidence triggers (lifted from #42796 stop-phrase-guard).
DEFAULT_PREMATURE_PASS_PHRASES: tuple[str, ...] = (
    r"all tests pass",
    r"tests should pass",
    r"this should work",
    r"the tests pass now",
)

#: Default forbidden file-write paths (root-level dumping, per CLAUDE.md).
ROOT_WRITE_RE = re.compile(r"(?:^|[/\s])(?:Write|Edit)\s*\([^)]*['\"]\./[^/'\"]+\.[a-zA-Z]+['\"]")


@dataclass(slots=True)
class Violation:
    """One detected convention breach."""

    response_index: int
    rule: str
    snippet: str


@dataclass(slots=True)
class ConventionReport:
    """Aggregate ``Violation`` set for a batch of responses."""

    total_responses: int
    violations: list[Violation] = field(default_factory=list)

    @property
    def rate(self) -> float:
        if self.total_responses <= 0:
            return 0.0
        bad = {v.response_index for v in self.violations}
        return len(bad) / float(self.total_responses)


def _mine_extra_phrases(rules_text: str) -> list[str]:
    """Pull literal banned phrases out of NEVER/MUST NOT/Don't lines in CLAUDE.md.

    Heuristic: the first quoted string on a NEVER/Don't/MUST NOT line is treated
    as a banned phrase. Misses are tolerated — this is best-effort augmentation
    on top of ``DEFAULT_BANNED_PHRASES``.
    """
    extras: list[str] = []
    pattern = re.compile(
        r"^\s*[-*]?\s*(?:NEVER|MUST NOT|Don'?t|DO NOT)\b[^\n]*?['\"]([^'\"]{2,80})['\"]",
        re.IGNORECASE | re.MULTILINE,
    )
    for match in pattern.finditer(rules_text):
        phrase = match.group(1).strip()
        if phrase:
            extras.append(re.escape(phrase))
    return extras


def _compile_banned(rules_text: str | None) -> list[re.Pattern[str]]:
    phrases = list(DEFAULT_BANNED_PHRASES)
    if rules_text:
        phrases.extend(_mine_extra_phrases(rules_text))
    return [re.compile(p, re.IGNORECASE) for p in phrases]


def _compile_premature() -> list[re.Pattern[str]]:
    return [re.compile(p, re.IGNORECASE) for p in DEFAULT_PREMATURE_PASS_PHRASES]


def _load_rules(rules: str | Path | None) -> str | None:
    if rules is None:
        return None
    p = Path(rules)
    if p.exists() and p.is_file():
        try:
            return p.read_text(encoding="utf-8")
        except OSError:
            return None
    if isinstance(rules, str):
        return rules
    return None


def check_text(
    text: str,
    *,
    response_index: int = 0,
    rules: str | Path | None = None,
) -> list[Violation]:
    """Return all violations found in a single ``text`` blob."""
    rules_text = _load_rules(rules)
    banned = _compile_banned(rules_text)
    premature = _compile_premature()

    violations: list[Violation] = []
    for pat in banned:
        for hit in pat.finditer(text):
            violations.append(
                Violation(
                    response_index=response_index,
                    rule=f"banned-phrase:{pat.pattern}",
                    snippet=text[max(0, hit.start() - 20) : hit.end() + 20],
                )
            )
    for pat in premature:
        for hit in pat.finditer(text):
            violations.append(
                Violation(
                    response_index=response_index,
                    rule=f"premature-pass:{pat.pattern}",
                    snippet=text[max(0, hit.start() - 20) : hit.end() + 20],
                )
            )
    for hit in ROOT_WRITE_RE.finditer(text):
        violations.append(
            Violation(
                response_index=response_index,
                rule="root-folder-write",
                snippet=hit.group(0),
            )
        )
    return violations


def check_responses(
    responses: list[str],
    *,
    rules: str | Path | None = None,
) -> ConventionReport:
    """Run :func:`check_text` over each response and aggregate."""
    all_violations: list[Violation] = []
    for idx, response in enumerate(responses):
        all_violations.extend(check_text(response, response_index=idx, rules=rules))
    return ConventionReport(total_responses=len(responses), violations=all_violations)
