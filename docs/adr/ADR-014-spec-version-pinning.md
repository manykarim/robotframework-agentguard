# ADR-014: Spec Version Pinning (A2A, Skills, MCP)

- **Status**: Proposed
- **Date**: 2026-04-29
- **Deciders**: agentguard-architecture-swarm
- **Bounded Context**: cross-cutting

## Context

`agentguard` rides on three rapidly evolving open standards: **MCP** (Anthropic, ongoing version revisions), the **Agent Skills** specification (`agentskills.io`, published 2025-12-18, still under-specified for installation paths and `allowed-tools` mechanism per Simon Willison), and **A2A** (Linux Foundation, only reaching 1.0 in early 2026) (research §2.4, risk #5).

Spec churn manifests as silent semantic changes: a new MCP version may add or remove a tool field; A2A 1.0 → 1.1 may rename `AgentCard` properties; the Agent Skills spec may finally formalise `allowed-tools` semantics. Tests written today will silently pass-or-fail differently against new spec versions if the library doesn't pin.

Vendor-side changes amplify this: the April 23, 2026 Anthropic postmortem (research risk #6) showed that vendor changes can silently move metric distributions even with the spec held constant.

## Decision

Pin to specific spec versions (**MCP version**, **A2A 1.0**, **Agent Skills spec date**) in the top-level Library `version=` parameter and surface them in every JSON/HTML report. Emit `DeprecationWarning` (with version metadata) when a newer spec is detected at runtime. Maintain a `compatibility_matrix.json` mapping `agentguard` version → supported spec versions.

## Rationale

- Pinning makes silent spec churn loud and auditable.
- Version metadata in reports lets QA teams correlate test failures with spec bumps.
- DeprecationWarnings give 1+ release of migration time before forcing upgrade.
- Compatibility matrix is the standard pattern (e.g., Robot Framework's own RF-version compatibility) and lets users plan upgrades.

## Consequences

- **Positive**: Spec churn becomes auditable; users get advance warning; report metadata enables long-term comparison.
- **Negative**: Library releases must keep pace with spec releases; lag risk if a critical spec security fix lands and `agentguard` lags.
- **Neutral**: Multi-version support adds matrix-test cost in CI; mitigated by testing only "current + previous" pinned versions.

## Alternatives Considered

- **Option A — Always use latest spec**: rejected, silent semantic changes break tests with no audit trail.
- **Option B — Hardcode one version forever**: rejected, blocks adoption of standardised features (signed skills, A2A 1.x improvements).
- **Option C — Let users pin per-test**: rejected, fragments the test suite and hides the matrix from CI.

## Related ADRs

- ADR-002 (MCP transport choice tied to MCP spec version)
- ADR-006 (Agent Skills version drives discovery semantics)
- ADR-008 (A2A version pinned for SubAgent harness)
- ADR-012 (Telemetry includes pinned spec versions in span attributes)
