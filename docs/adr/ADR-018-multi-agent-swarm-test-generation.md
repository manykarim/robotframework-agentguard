# ADR-018: Multi-Agent Swarm Test Generation

- **Status**: Proposed
- **Date**: 2026-04-29
- **Deciders**: agentguard-architecture-swarm
- **Bounded Context**: cross-cutting

## Context

`mcp-eval` already auto-generates baseline test suites for MCP servers (research §2.1). For `agentguard` to scale across the dozens of skills and MCP servers a typical project ships, comparable auto-generation is needed for both surfaces. Hand-writing baseline suites for every skill/MCP server is intractable — the Agent Skills spec was adopted by 32 tools in 90 days (research §2.2); skill catalogs grow faster than any single team can write tests.

CLAUDE.md provisions a hierarchical-mesh swarm with up to 15 agents and a hive-mind raft consensus mechanism. RuFlo skills (`swarm-orchestration`, `v3-swarm-coordination`, `swarm-advanced`) are first-class. The natural composition: the swarm generates candidate tests in parallel, then hive-mind raft consensus votes on which generated tests are non-flaky enough to commit.

Flakiness gating is essential — auto-generated tests are notoriously flaky and silently erode trust in the suite if shipped unfiltered.

## Decision

Use the **RuFlo hierarchical-mesh swarm** (max 15 agents) to auto-generate baseline test suites per skill and per MCP server, mirroring `mcp-eval`'s auto-generation pattern. Use **hive-mind raft consensus** to vote on which generated tests pass a flakiness threshold (run candidate ≥10 times, require ≥0.95 pass rate, ADR-005) before they are committed to the test suite.

## Rationale

- Hierarchical-mesh + 15 agents is the project-recommended topology (CLAUDE.md).
- Raft consensus (single leader, deterministic) suits "vote on test quality" better than gossip or PBFT.
- Flakiness gating before commit prevents the documented "auto-generated suite collapses to noise" failure mode.
- ADR-005's N≥10 statistical machinery already exists — flakiness gate reuses it.

## Consequences

- **Positive**: Baseline coverage scales with skill catalog growth; no human bottleneck for test creation; flakiness gate keeps signal high.
- **Negative**: 15-agent swarm consumes meaningful API budget — must cap by skill/MCP-server count and rate-limit.
- **Neutral**: Generated tests still require human review for intent correctness before merge — flakiness gate addresses noise, not correctness.

## Alternatives Considered

- **Option A — Hand-written tests only**: rejected, doesn't scale.
- **Option B — Single-agent generation**: rejected, no consensus mechanism for flakiness gating.
- **Option C — Mesh topology without hive-mind**: rejected, hierarchical-mesh + raft is the explicit project-recommended pattern (CLAUDE.md, anti-drift).

## Related ADRs

- ADR-004 (Generated tests use the BFCL AST matcher)
- ADR-005 (Flakiness gate uses N≥10 statistical machinery)
- ADR-016 (Generated tests checked against existing test corpus via similarity search)
- ADR-019 (Generation work routed via `hooks_route` across tiers)
