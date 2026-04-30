# ADR-015: RuFlo SONA Self-Learning Integration

- **Status**: Proposed
- **Date**: 2026-04-29
- **Deciders**: agentguard-architecture-swarm
- **Bounded Context**: cross-cutting

## Context

`agentguard` produces a high-volume stream of `Session` artifacts (ADR-010) and per-metric distributions (ADR-005). Manually distilling recurring failure patterns into reusable assertions is laborious. RuFlo's SONA self-learning pipeline (`ruvllm_sona_create`, `ruvllm_sona_adapt`, ReasoningBank) is designed to record trajectories, distill recurring patterns, and persist them as reusable knowledge — and CLAUDE.md exposes it as first-class infrastructure on this project.

Catastrophic forgetting is a known SONA risk: as new failure patterns are learned, older skill baselines may be overwritten. EWC++ (Elastic Weight Consolidation, online variant) is the standard mitigation. The RuFlo capability map (`docs/integration/ruflo-capability-map.md`, owner: `v3-integration-architect`) confirms this is supported.

Pending experiment `exp_15` is measuring SONA pattern-extraction recall on 1000 historical degraded sessions to validate that learned patterns reproduce manual triage decisions.

## Decision

Record every test-run trajectory into RuFlo's ReasoningBank via `hooks_intelligence_trajectory-start | trajectory-step | trajectory-end`. Distill recurring failure patterns into reusable Robot Framework assertions via the SONA pipeline. Use **EWC++** to prevent forgetting older skill baselines as new patterns are added.

## Rationale

- ReasoningBank is project-default infrastructure (CLAUDE.md, RuFlo capability map).
- Trajectory recording is "free" once hooks are in place (ADR-017) — cost is amortised.
- Pattern distillation produces reusable assertions, compounding test-suite value over time.
- EWC++ is the established defence against catastrophic forgetting in continual learning.

## Consequences

- **Positive**: Test suite gets smarter over time; recurring failures become explicit assertions; institutional knowledge persists across personnel turnover.
- **Negative**: SONA storage and computation cost scales with run count; requires periodic consolidation (`agentdb_consolidate`).
- **Neutral**: Distilled patterns require human review before promotion into the CI suite — guardrail against learned biases.

## Alternatives Considered

- **Option A — No self-learning; manual pattern extraction**: rejected, doesn't scale beyond a small team.
- **Option B — Vanilla SONA without EWC++**: rejected, will erode old baselines as new patterns are learned.
- **Option C — Fine-tuning a small model on trajectories**: rejected for v0.x; SONA pattern extraction gives most of the value at far lower cost and complexity.

## Related ADRs

- ADR-005 (Stats API consumes baseline distributions stored by SONA)
- ADR-010 (`Session` is the input artifact)
- ADR-016 (HNSW retrieval finds the "most similar past failure" for a given new run)
- ADR-017 (Hooks pipeline feeds SONA)
- **Hard dependency on pending experiment `exp_15` (SONA recall on degraded sessions)**
