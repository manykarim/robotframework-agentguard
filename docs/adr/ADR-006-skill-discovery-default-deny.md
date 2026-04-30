# ADR-006: Skill Discovery + Default-Deny Allowlist

- **Status**: Proposed
- **Date**: 2026-04-29
- **Deciders**: agentguard-architecture-swarm
- **Bounded Context**: Skills, Security

## Context

The Agent Skills specification was adopted by 32 tools within ~90 days of publication, each installing skills under different paths: `.claude/skills/`, `.agents/skills/`, `~/.gemini/antigravity/skills/`, `~/.codex/skills/`, plus VS Code/Copilot, JetBrains Junie, Block Goose, Cursor, etc. (research §2.2). Cross-vendor skill testing requires unified discovery.

Snyk's *ToxicSkills* study (research risk #3) found 36% of community skills had security flaws, 76 confirmed malicious, and identified the *ClawHavoc* coordinated campaign delivering AMOS infostealers. The CLAUDE.md security rules require validating input at system boundaries and treating supply-chain artifacts as untrusted by default.

A naive "scan everything in `~/.claude/skills/`" discovery would silently load attacker-controlled skills into a CI grader. The threat-model doc (`docs/security/`, owner: `security-architect`) covers the broader supply-chain analysis.

## Decision

`SkillsLibrary` discovers skills across `.claude/skills/`, `.agents/skills/`, `~/.gemini/antigravity/skills/`, and `~/.codex/skills/` by default. **All third-party (i.e., not project-local) skills require explicit allowlist entry** in `agentguard.toml` (`[skills.allowlist] paths = [...]`). Unsigned third-party skills loaded without allowlist entry raise `UnauthorizedSkillError`. Discovery is paired with an `aidefence_scan` pre-flight (ADR-020).

## Rationale

- Default-deny matches OWASP/CLAUDE.md "validate at boundaries" guidance.
- Project-local skills (in repo, under version control, reviewed via PR) are trusted; user-installed skills are not.
- Allowlist is auditable and version-controllable.
- Pairing with AIDefence scan (ADR-020) catches malicious payloads even in allowlisted skills.

## Consequences

- **Positive**: Defends against ToxicSkills/ClawHavoc-class supply-chain attacks; auditable allowlist; no surprise skill execution.
- **Negative**: Adds friction for genuine third-party skills; requires user education on the allowlist concept.
- **Neutral**: Project-local skills are trusted by convention; teams that don't review their own repo are out of scope for this defence.

## Alternatives Considered

- **Option A — Discover everything by default**: rejected, directly enables ToxicSkills attack vector.
- **Option B — Require signature on every skill**: rejected, Agent Skills spec doesn't (yet) standardise signing; would block adoption.
- **Option C — Sandbox every skill at runtime**: rejected as primary defence (still useful, see ADR-013), but doesn't prevent metadata-based attacks (poisoned descriptions misleading the agent).

## Related ADRs

- ADR-013 (Sandbox policy for actually executing skill code)
- ADR-014 (Skills spec version pinning)
- ADR-020 (AIDefence skill scanner runs as part of discovery)
- See also `docs/security/threat-model.md` (security-architect)
