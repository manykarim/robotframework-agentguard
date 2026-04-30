# ADR-008: SubAgent / A2A Harness

- **Status**: Proposed
- **Date**: 2026-04-29
- **Deciders**: agentguard-architecture-swarm
- **Bounded Context**: SubAgents

## Context

Multi-agent frameworks each have proprietary delegation primitives (CrewAI `Crew/Agent/Task`, LangGraph graph nodes, AutoGen conversational agents, OpenAI Agents SDK `Agents/Handoffs/Guardrails`). Claude Code surfaces sub-agents via `SubagentStop` hook and skill frontmatter. At the protocol layer, **A2A (Agent2Agent)** — open-sourced by Google in April 2025, donated to the Linux Foundation, reaching 1.0 in 2026 — provides a vendor-neutral way to discover (`AgentCard`), authenticate, and delegate via JSON-RPC and SSE, with a `task` lifecycle and `artifacts` (research §2.4).

LiteLLM ships `A2AClient` and an A2A Gateway with bridges for LangGraph, Vertex AI Agent Engine, Azure AI Foundry, Bedrock AgentCore, and Pydantic AI. A standardised, framework-agnostic test harness over A2A does not yet exist as a Robot Framework library and is a clear opportunity (research §2.4).

Trajectory comparison can reuse the BFCL AST matcher from ADR-004.

## Decision

Adopt **A2A as the framework-agnostic protocol** for SubAgent testing. `SubAgentKeywords` exposes `Get Agent Card`, `Send Task`, `Wait For Task Completion`, `Get Task Artifact`, `Task Should Have Status`. Ship bridges to LangGraph (checkpointer state assertions), CrewAI (replay), AutoGen (state introspection), and OpenAI Agents SDK (handoff trace). Trajectory comparison uses the BFCL matcher from ADR-004.

## Rationale

- A2A 1.0 is the only vendor-neutral standard for agent-to-agent delegation (research §2.4).
- LiteLLM already provides the bridges to major frameworks — minimise the wheel-reinvention surface.
- Reusing the BFCL AST matcher (ADR-004) avoids duplicating trajectory comparison logic across MCP and SubAgent contexts.
- `SubagentStop` integration is delegated to the Hooks module (ADR-007) — one source of truth per hook event.

## Consequences

- **Positive**: One harness covers all major multi-agent frameworks; protocol-level testing survives framework version churn; trajectory analysis unified with MCP testing.
- **Negative**: A2A 1.0 only stabilised in early 2026 — spec churn risk (mitigated by ADR-014).
- **Neutral**: Framework-specific bridges still need per-framework maintenance, but they're thin adapters not full reimplementations.

## Alternatives Considered

- **Option A — Per-framework test harnesses (LangGraph, CrewAI, AutoGen separately)**: rejected, N×M maintenance, no portable test suite.
- **Option B — Wait for a winner among multi-agent frameworks**: rejected, A2A is already the convergence layer.
- **Option C — Test via MCP only**: rejected, MCP is for vertical (agent ↔ tool); A2A is for horizontal (agent ↔ agent) — different shapes, both needed (research §7.4).

## Related ADRs

- ADR-004 (BFCL AST matcher reused for trajectory comparison)
- ADR-007 (`SubagentStop` lives in Hooks)
- ADR-014 (A2A spec version pinned)
