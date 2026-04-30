# ADR-017: RuFlo Hooks Integration

- **Status**: Proposed
- **Date**: 2026-04-29
- **Deciders**: agentguard-architecture-swarm
- **Bounded Context**: Hooks, cross-cutting

## Context

The Claude Code hooks system (12 lifecycle events, ADR-007) fires during every coding-agent session that `agentguard` drives. RuFlo exposes complementary tools — `hooks_route` (intelligent task routing), `hooks_intelligence_pattern-store` and `hooks_intelligence_pattern-search` (pattern persistence), `hooks_intelligence_attention` (intelligent test selection per file/symbol), `hooks_session-start` and `hooks_session-end` (session-scoped state) — that turn raw hook events into a learning signal feeding ADR-015 (SONA) and ADR-016 (memory graph).

This ADR is about wiring those RuFlo hooks into the `agentguard` test runner. It does **not** replace ADR-007's harness — that ADR remains the canonical surface for unit-testing user-supplied hook scripts. The two compose: ADR-007 tests hooks; ADR-017 uses RuFlo hooks to make the tester smarter.

The RuFlo capability map (`docs/integration/ruflo-capability-map.md`) is the source of truth for which RuFlo hook tools are stable.

## Decision

Wire **`PostToolUse`**, **`Stop`**, and **`SessionStart`** Claude Code hooks into the `agentguard` test runner so that `hooks_intelligence_pattern-store` learns from every test run. Use **`hooks_intelligence_attention`** to drive intelligent test selection (run only the tests touching files the agent modified). Use **`hooks_route`** to dispatch test work across the 3-tier model router (ADR-019).

## Rationale

- These three lifecycle events cover the highest-signal moments: tool completion (`PostToolUse`), end-of-session reflection (`Stop`), and bootstrap (`SessionStart`).
- Pattern-store on every test run gives ADR-015's SONA pipeline its raw material.
- `hooks_intelligence_attention` directly enables impact-based test selection — a major win for large suites.
- `hooks_route` is the routing fabric ADR-019 depends on.

## Consequences

- **Positive**: Test suite learns continuously; impact-based test selection cuts CI time on small change-sets; routing fabric reuses RuFlo investment.
- **Negative**: Test runner now has a hard dependency on RuFlo daemon being healthy in CI — must degrade gracefully when RuFlo is unavailable.
- **Neutral**: RuFlo hook events are stored in AgentDB (ADR-016); storage growth must be monitored.

## Alternatives Considered

- **Option A — No RuFlo hook integration**: rejected, forfeits the SONA / attention / routing infrastructure CLAUDE.md provides.
- **Option B — Wire all 12 lifecycle events**: rejected, low-signal events (`UserPromptExpansion`, `PostToolBatch`) inflate storage with little learning value; can be added later if needed.
- **Option C — Replace ADR-007's harness with RuFlo hooks**: rejected, conflates "test the user's hooks" with "use hooks to make the tester smarter" — these are orthogonal concerns.

## Related ADRs

- ADR-007 (Hook test harness; this ADR composes with it, doesn't replace it)
- ADR-015 (SONA consumes the patterns this ADR records)
- ADR-016 (Memory graph stores the events)
- ADR-019 (`hooks_route` is the per-keyword router)
