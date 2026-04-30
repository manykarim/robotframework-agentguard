# ADR-003: Library Composition (PythonLibCore + DynamicCore)

- **Status**: Proposed
- **Date**: 2026-04-29
- **Deciders**: agentguard-architecture-swarm
- **Bounded Context**: cross-cutting

## Context

`agentguard` covers six orthogonal surfaces (MCP, Skills, Hooks, SubAgents, CodingAgent, Statistics) with two cross-cutting concerns (Provider, Judge). Robot Framework users expect to import just what they need (`Library AgentGuard.Skills`) rather than a monolith that pulls every dependency on import. The research's reference architecture (§4.1, §4.3) uses `PythonLibCore` + `DynamicCore` to compose sub-libraries into a single top-level Library while still allowing standalone import.

Key constraints from CLAUDE.md: files <500 lines; typed interfaces for all public APIs; sub-libraries importable individually so a CI job that only checks MCP doesn't pay the import cost of LangGraph, A2A, scipy, etc.

## Decision

Build the library as a `DynamicCore`-backed top-level `AgentGuard` class composing six sub-libraries (`MCPKeywords`, `SkillsKeywords`, `HooksKeywords`, `SubAgentKeywords`, `CodingAgentKeywords`, `StatsKeywords`), each independently importable as a standalone Robot Framework library (`Library AgentGuard.Skills`, etc.), all built on `PythonLibCore`.

## Rationale

- `PythonLibCore` is the Robot Framework community standard for typed, decorator-driven keyword libraries.
- `DynamicCore` lets the top-level library aggregate multiple sub-libraries without exploding into one giant class.
- Per-sub-library import keeps dependency surface minimal: a Skills-only test job avoids importing `a2a-sdk`, `langgraph`, `scipy`, `inspect_ai`.
- Library `scope=SUITE` (default) gives shared state per `.robot` suite — natural for "open one MCP connection, run 50 tests".
- 500-line file cap is enforceable per sub-library file.

## Consequences

- **Positive**: Modular import surface; clean dependency graph; easy to add Phase 2/3 sub-libraries (Hooks, SubAgents, CodingAgent) without touching MCP/Skills code.
- **Negative**: `DynamicCore` keyword discovery is slightly less debuggable than static `@keyword` libraries; library-scope state must be reasoned about per sub-library.
- **Neutral**: Top-level `AgentGuard` Library becomes the documented "easy on-ramp"; advanced users compose sub-libraries explicitly.

## Alternatives Considered

- **Option A — Single static `AgentGuard` Library class**: rejected, violates 500-line cap and forces every user to install every dependency.
- **Option B — Pure `@keyword` decorators without `DynamicCore`**: rejected, duplicates aggregation plumbing already solved by `DynamicCore`.
- **Option C — One PyPI package per sub-library**: rejected for v0.x, multiplies release coordination cost; revisit for v1.0 if dependency bloat becomes painful.

## Related ADRs

- ADR-001 (Provider injected at top-level constructor)
- ADR-002 (MCP sub-library houses transport selection)
- ADR-005 (Stats sub-library)
- ADR-007, ADR-008, ADR-009 (Hooks, SubAgents, CodingAgent sub-libraries)
- ADR-012 (OTel listener registered alongside library)
