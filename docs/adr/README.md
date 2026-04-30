# Architecture Decision Records — robotframework-agentguard

This directory contains the Architecture Decision Records (ADRs) for `robotframework-agentguard`, a Robot Framework library for testing Agent Skills, Hooks, SubAgents, and MCP Servers with a security/regression-guard focus (ToxicSkills mitigation, `anthropics/claude-code#42796` metric drift detection, default-deny supply chain).

ADRs use a MADR-lite template. All ADRs are **Proposed** as of 2026-04-29; nothing is implemented yet. Source of truth for every decision is `docs/research/research.md`. Bounded contexts referenced (Provider, MCP, Skills, Hooks, SubAgents, CodingAgent, Statistics, Judge, Security, Telemetry, BehavioralMetrics, ToolCallCorrectness) are defined by the parallel `ddd-domain-expert` agent under `docs/ddd/`.

## Index

| ADR | Title | Bounded Context | Status |
|-----|-------|-----------------|--------|
| [ADR-001](ADR-001-provider-abstraction.md) | Provider Abstraction via LiteLLM | Provider | Proposed |
| [ADR-002](ADR-002-mcp-transport-strategy.md) | MCP Transport Strategy | MCP | Proposed |
| [ADR-003](ADR-003-library-composition.md) | Library Composition (PythonLibCore + DynamicCore) | cross-cutting | Proposed |
| [ADR-004](ADR-004-tool-call-matching.md) | Tool-Call Matching (BFCL AST Equality) | ToolCallCorrectness | Proposed |
| [ADR-005](ADR-005-statistical-assertion-api.md) | Statistical Assertion API | Statistics | Proposed |
| [ADR-006](ADR-006-skill-discovery-default-deny.md) | Skill Discovery + Default-Deny Allowlist | Skills, Security | Proposed |
| [ADR-007](ADR-007-hook-test-harness.md) | Hook Test Harness | Hooks | Proposed |
| [ADR-008](ADR-008-subagent-a2a-harness.md) | SubAgent / A2A Harness | SubAgents | Proposed |
| [ADR-009](ADR-009-coding-agent-driver.md) | Coding Agent Driver Pattern | CodingAgent | Proposed |
| [ADR-010](ADR-010-session-schema-and-42796-metrics.md) | Session JSONL Schema + #42796 Metrics | BehavioralMetrics, CodingAgent | Proposed |
| [ADR-011](ADR-011-llm-judge-calibration.md) | LLM-as-Judge Calibration (Cohen's κ ≥ 0.7) | Judge | Proposed |
| [ADR-012](ADR-012-otel-rf-listener.md) | OpenTelemetry + Robot Framework Listener | Telemetry | Proposed |
| [ADR-013](ADR-013-sandbox-policy.md) | Sandbox Policy for Agent-Generated Code | Security, CodingAgent | Proposed |
| [ADR-014](ADR-014-spec-version-pinning.md) | Spec Version Pinning (A2A, Skills, MCP) | cross-cutting | Proposed |
| [ADR-015](ADR-015-ruflo-sona-self-learning.md) | RuFlo SONA Self-Learning Integration | cross-cutting | Proposed |
| [ADR-016](ADR-016-ruflo-memory-hnsw-knowledge-graph.md) | RuFlo Memory + HNSW Knowledge Graph | cross-cutting | Proposed |
| [ADR-017](ADR-017-ruflo-hooks-integration.md) | RuFlo Hooks Integration | Hooks, cross-cutting | Proposed |
| [ADR-018](ADR-018-multi-agent-swarm-test-generation.md) | Multi-Agent Swarm Test Generation | cross-cutting | Proposed |
| [ADR-019](ADR-019-3-tier-model-routing.md) | 3-Tier Model Routing | Provider, Judge | Proposed |
| [ADR-020](ADR-020-aidefence-skill-scanner.md) | AIDefence Skill Scanner & PII Filter | Security, Judge | Proposed |

## Cross-References to Parallel Workstreams

- DDD bounded contexts → `docs/ddd/` (owner: `ddd-domain-expert`)
- Threat model → `docs/security/` (owner: `security-architect`)
- RuFlo capability map → `docs/integration/ruflo-capability-map.md` (owner: `v3-integration-architect`)
- Performance budgets → `docs/performance/budgets.md` (owner: `performance-engineer`)
- Experiment results → `docs/research/experiments/REPORT.md` and RuFlo namespace `agentguard/experiments` (owner: `researcher`)

## Status Lifecycle

`Proposed` → `Accepted` → (optionally) `Deprecated` or `Superseded by ADR-NNN`. No ADR may be marked `Accepted` until its referenced experiments land or its dependencies are confirmed.
