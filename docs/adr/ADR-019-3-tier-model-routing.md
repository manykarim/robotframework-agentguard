# ADR-019: 3-Tier Model Routing

- **Status**: Proposed
- **Date**: 2026-04-29
- **Deciders**: agentguard-architecture-swarm
- **Bounded Context**: Provider, Judge

## Context

`agentguard` keywords have wildly different cost profiles. AST equality (ADR-004), JSON-Schema validation, and regex convention checks are pure computation — sending them to a frontier LLM is wasteful. Simple judge classifications (binary "valid Robot Framework syntax: yes/no") are well within Haiku's competence. Rubric grading, complex trajectory analysis, and architectural reasoning need Sonnet/Opus.

CLAUDE.md formalises a 3-tier routing model with documented latency/cost characteristics: Tier 1 (Agent Booster WASM, <1ms, $0) for simple transforms; Tier 2 (Haiku, ~500ms, $0.0002) for low-complexity tasks (<30%); Tier 3 (Sonnet/Opus, 2-5s, $0.003-0.015) for complex reasoning (>30%). The performance budget (`docs/performance/budgets.md`, owner: `performance-engineer`) targets ≥80% of keyword invocations served by Tier 1/2.

`hooks_route` is the per-keyword routing primitive exposed by RuFlo (ADR-017).

## Decision

Implement the CLAUDE.md 3-tier model routing for every keyword: **Tier 1 (Agent Booster WASM)** for AST equality, regex, and JSON-Schema validation; **Tier 2 (Haiku)** for simple classification judges; **Tier 3 (Sonnet/Opus)** for rubric judging and complex trajectory analysis. Routing decisions made per keyword via **`hooks_route`** (ADR-017).

## Rationale

- 80%+ of keyword invocations are deterministic AST/regex/schema work — Tier 1 saves substantial cost and latency.
- Haiku at $0.0002/call makes binary judges affordable at scale (ADR-005's N≥10 default).
- Sonnet/Opus reserved for rubric judging where their reasoning quality is load-bearing.
- `hooks_route` is the project-default routing primitive — no new infrastructure required.

## Consequences

- **Positive**: Cost-optimised by default; latency budgets met (per performance-engineer); routing decisions auditable via `hooks_model-stats`.
- **Negative**: Tier-1 misclassification (sending a complex task to Agent Booster) silently produces wrong answers — must be caught by routing-confidence threshold.
- **Neutral**: Tier choice is a per-keyword default; users can override via `force_tier=3` for specific assertions.

## Alternatives Considered

- **Option A — Single model for all keywords**: rejected, 64×–80× cost overhead measured in research §2.6 token-efficiency metric.
- **Option B — Two tiers (Haiku + Sonnet)**: rejected, leaves Tier 1 free-and-instant savings on the table.
- **Option C — Per-test routing instead of per-keyword**: rejected, too coarse — a single test routinely mixes AST checks and rubric judges.

## Related ADRs

- ADR-001 (Provider adapter is the substrate the router sits on top of)
- ADR-004 (BFCL AST matching is the canonical Tier 1 workload)
- ADR-011 (Judge tier choice driven by rubric complexity)
- ADR-017 (`hooks_route` is the routing primitive)
- See `docs/performance/budgets.md` for tier-level budget targets.
