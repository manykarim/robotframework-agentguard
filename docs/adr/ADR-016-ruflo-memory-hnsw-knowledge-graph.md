# ADR-016: RuFlo Memory + HNSW Knowledge Graph

- **Status**: Proposed
- **Date**: 2026-04-29
- **Deciders**: agentguard-architecture-swarm
- **Bounded Context**: cross-cutting

## Context

`agentguard` accumulates several long-lived knowledge artifacts: per-skill baselines, regression baselines, BFCL ground-truth datasets, judge calibration sets, distilled SONA patterns (ADR-015), and `Session` archives (ADR-010). Without similarity-based retrieval, finding the "most relevant past failure" for a new degraded run is an O(N) scan.

RuFlo's AgentDB provides ONNX 384-dim embeddings (`all-MiniLM-L6-v2`) and HNSW indexing for vector similarity search. Per the capability map (`docs/integration/ruflo-capability-map.md`), DiskANN is also available for SSD-friendly indices when the corpus exceeds 1M vectors. PageRank over a memory graph (failures cite earlier failures cite earlier baselines) surfaces the "most influential" nodes — useful for triage prioritisation.

Performance budgets (`docs/performance/budgets.md`, owner: `performance-engineer`) target sub-100ms semantic retrieval at 100k vectors.

## Decision

Store skill baselines, regression baselines, BFCL ground truth, judge calibration sets, and SONA-distilled patterns in **AgentDB with ONNX 384-dim embeddings**. Use **HNSW** for similarity-based retrieval (DiskANN above 1M vectors). Build a memory graph linking failures → baselines → patterns and run **PageRank** to surface the most influential past failures during triage.

## Rationale

- AgentDB + ONNX is project-default infrastructure (CLAUDE.md).
- HNSW gives sub-100ms similarity retrieval at the corpus sizes `agentguard` will produce in its first 12 months.
- PageRank over the failure-baseline graph translates "noisy graph of failures" into "top-N to investigate" — high-leverage triage primitive.
- DiskANN fallback path exists for organisations with very large corpora.

## Consequences

- **Positive**: Sub-100ms similarity retrieval; PageRank-prioritised triage; cross-namespace search (`memory_search_unified`) makes Claude Code memories reachable from the test suite.
- **Negative**: ONNX runtime dependency on every CI runner; embedding-store size grows linearly with run count.
- **Neutral**: Quantization (4-32× memory reduction, per agentdb-optimization skill) available if memory pressure becomes an issue.

## Alternatives Considered

- **Option A — Plain SQLite without embeddings**: rejected, no similarity retrieval, no SONA integration.
- **Option B — External vector DB (Pinecone, Weaviate)**: rejected, network dependency at test time; AgentDB embedded is more CI-friendly.
- **Option C — HNSW only, no PageRank**: rejected, loses the triage-prioritisation value; PageRank computation cost is amortisable.

## Related ADRs

- ADR-005 (Baseline distributions stored here)
- ADR-010 (`Session` archive lives in AgentDB)
- ADR-011 (Judge calibration sets stored here)
- ADR-015 (SONA-distilled patterns stored here)
- ADR-018 (Swarm test generation queries this for "tests we already have")
