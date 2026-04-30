# ADR-004: Tool-Call Matching (BFCL AST Equality)

- **Status**: Proposed
- **Date**: 2026-04-29
- **Deciders**: agentguard-architecture-swarm
- **Bounded Context**: ToolCallCorrectness

## Context

Tool-call correctness is the core of agent evaluation. The Berkeley Function Calling Leaderboard (BFCL) established the dominant approach: compare expected and actual tool calls by AST equality of name + arguments rather than by executing the tool. This scales to thousands of functions, handles single-turn, parallel, multiple, multi-turn, and "decide-not-to-act" categories, and has been ported into Inspect AI as a first-class evaluation (research §2.2, §3.1).

String comparison of serialised JSON is brittle (whitespace, key order, numeric formatting). Execution-based comparison is expensive, side-effecting, and infeasible in CI for many tool surfaces. Argument schemas come from the MCP/OpenAI tool definitions and can be used to normalise ordering and types before comparison.

For multi-turn / trajectory tests, ordered subsequence matching (with optional wildcards for non-load-bearing tool calls) is the established pattern from Inspect AI.

## Decision

Adopt **BFCL AST-equality semantics**: tool name compared as exact string; arguments compared by AST equality after schema-driven normalisation (whitespace and key order ignored, numerics canonicalised). For parallel tool calls in one turn, use **multiset equality**. For trajectories across turns, use **ordered subsequence match** with optional wildcards.

## Rationale

- BFCL is the de-facto industry standard, ported by Inspect AI (research §2.2).
- AST equality is deterministic, fast, and cleanly assertable from Robot keywords (`Tool Call Arguments Should Match`, `Parallel Tool Calls Should Match`, `Tool Sequence Should Match`).
- Multiset for parallel correctly handles unordered-by-design simultaneous calls.
- Ordered subsequence for trajectories permits non-load-bearing chatter without false negatives.
- Schema-driven normalisation eliminates the most common false-positive class (key order, numeric formatting).

## Consequences

- **Positive**: Deterministic, fast, no tool execution required, scales to thousands of test cases, reuses BFCL ground-truth datasets directly.
- **Negative**: AST-equal tool calls can still be semantically wrong (e.g., correct args but wrong intent) — mitigated by combining with LLM-as-Judge (ADR-011) for outcome correctness.
- **Neutral**: Wildcards in trajectory matching need careful documentation; a too-permissive wildcard erodes the test's value.

## Alternatives Considered

- **Option A — Execute tools and compare side-effects**: rejected, expensive, side-effecting, requires sandbox (ADR-013) for every test.
- **Option B — Plain JSON string equality**: rejected, brittle to formatting differences.
- **Option C — Embedding-similarity matching**: rejected for primary path (subjective threshold, slow); kept as optional `mode=semantic` fallback for free-text arguments.

## Related ADRs

- ADR-002 (In-memory MCP transport feeds AST matcher with deterministic input)
- ADR-008 (SubAgent trajectory comparison reuses this matcher)
- ADR-011 (LLM-as-Judge complements AST equality for semantic correctness)
- ADR-019 (Tier 1 Agent Booster handles AST equality with no LLM call)
