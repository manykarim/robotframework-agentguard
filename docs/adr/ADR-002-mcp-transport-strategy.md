# ADR-002: MCP Transport Strategy

- **Status**: Proposed
- **Date**: 2026-04-29
- **Deciders**: agentguard-architecture-swarm
- **Bounded Context**: MCP

## Context

MCP defines four transports: in-memory (FastMCP `Client(server)` direct binding), stdio (JSON-RPC over child-process pipes), SSE (Server-Sent Events; deprecated by Anthropic), and streamable-HTTP (the modern remote transport). Each transport has different latency, determinism, and CI characteristics (research §2.1, §7.3).

Tests run in three contexts: unit tests need to be fast and deterministic; integration tests need to exercise the real wire protocol (CLI parity); deployment validation must hit the actual remote server. Picking one transport for all three forces a bad tradeoff. The Arm Learning Path uses Testcontainers + stdio for canonical CI; FastMCP docs recommend in-memory for unit tests.

Pending experiment `exp_02` (researcher namespace `agentguard/experiments`) is benchmarking in-memory vs stdio determinism over 1000 runs to confirm the recommended default.

## Decision

The library selects MCP transport via `transport=auto`, with the policy: **in-memory for unit tests, stdio for integration tests, streamable-HTTP for deployment validation, SSE supported but flagged deprecated** with a `DeprecationWarning` on use.

## Rationale

- In-memory is the only transport that gives true determinism (no network, no subprocess scheduling) — required for the BFCL AST tests in ADR-004.
- stdio matches the canonical MCP CI pattern (Arm Learning Path, FastMCP examples) and exercises real JSON-RPC framing.
- Streamable-HTTP is the modern remote transport; SSE is on Anthropic's deprecation roadmap.
- `auto` resolution mirrors FastMCP convention so users coming from FastMCP have zero learning curve.

## Consequences

- **Positive**: One mental model (`transport=auto`), correct default per layer, deterministic unit tests by default.
- **Negative**: Three transport drivers to maintain; auto-resolution heuristics need clear documentation when they pick "wrong".
- **Neutral**: SSE support is kept for backwards compatibility but emits warnings; users must explicitly opt-in.

## Alternatives Considered

- **Option A — stdio only**: rejected, blocks unit-test determinism and adds subprocess overhead for in-process servers.
- **Option B — In-memory only**: rejected, never exercises real wire protocol, will miss framing/encoding bugs.
- **Option C — Force user to specify transport**: rejected, raises the floor for new adopters; auto-detection covers ≥90% of cases.

## Related ADRs

- ADR-003 (Library Composition — `MCPLibrary` houses transport drivers)
- ADR-004 (Tool-Call Matching — relies on in-memory determinism)
- ADR-014 (Spec Version Pinning — MCP spec version pinned alongside transport choice)
