# ADR-020: AIDefence Skill Scanner & PII Filter

- **Status**: Proposed
- **Date**: 2026-04-29
- **Deciders**: agentguard-architecture-swarm
- **Bounded Context**: Security, Judge

## Context

Two security risks must be addressed before any skill is graded or any trajectory is sent to a judge:

1. **Skill content attacks** — prompt injection, exfiltration directives, ToxicSkills/ClawHavoc-class payloads embedded in `SKILL.md`, `references/`, or `scripts/` (research risk #3, ADR-006).
2. **PII leakage to judge** — `Session` JSONL captured from coding agents routinely contains internal file paths, environment variables, and occasionally customer data. Sending these to a third-party judge model violates CLAUDE.md security rules.

RuFlo exposes `aidefence_scan` (general prompt-injection / unsafe-content detection), `aidefence_is_safe` (boolean gate), `aidefence_has_pii` (PII detector), and `aidefence_learn` (corpus learning). These are project-default infrastructure (CLAUDE.md). The threat model (`docs/security/`, owner: `security-architect`) defines the broader attack tree; this ADR covers the runtime gating.

## Decision

Every skill is run through **`aidefence_scan`** before grading; flagged skills require explicit human override via `--allow-flagged-skill <skill-id>`. Captured `Session` trajectories (ADR-010) are run through **`aidefence_has_pii`** before being sent to the judge; PII fields are redacted (or the test fails when redaction would change semantics).

## Rationale

- Pairs with ADR-006 (default-deny discovery) and ADR-013 (sandboxed execution) for defence-in-depth: metadata-vetted (ADR-020) → discovery-allowlisted (ADR-006) → execution-sandboxed (ADR-013).
- AIDefence is project-default infrastructure (CLAUDE.md) — no new external dependency.
- PII filtering before judge is mandatory under CLAUDE.md security rules.
- Human-override path keeps the workflow usable when AIDefence false-positives a legitimate skill.

## Consequences

- **Positive**: Defence-in-depth against ToxicSkills-class supply-chain attacks; PII never reaches third-party judges by accident; AIDefence learning improves detection over time.
- **Negative**: AIDefence false positives add friction for legitimate skills; PII redaction can degrade judge accuracy on path-heavy content.
- **Neutral**: Override decisions are logged via `aidefence_learn` so the model improves; redaction policy is configurable per project.

## Alternatives Considered

- **Option A — No content scanning**: rejected, contradicts ADR-006 / CLAUDE.md security rules.
- **Option B — Scan only at install time, not at grade time**: rejected, doesn't catch skills mutated after install or referenced files added later.
- **Option C — Send raw `Session` to judge with TOS-based privacy assurance**: rejected, contractual privacy doesn't substitute for technical controls.

## Related ADRs

- ADR-006 (Discovery default-deny — this ADR is the runtime scanner gate)
- ADR-010 (`Session` schema is the artifact this ADR scans)
- ADR-011 (Judge only receives PII-filtered trajectories)
- ADR-013 (Sandbox is the execution-layer counterpart)
- See also `docs/security/threat-model.md` (security-architect)
