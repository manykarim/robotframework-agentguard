# ADR-010: Session JSONL Schema + #42796 Metrics

- **Status**: Proposed
- **Date**: 2026-04-29
- **Deciders**: agentguard-architecture-swarm
- **Bounded Context**: BehavioralMetrics, CodingAgent

## Context

Stella Laurenzo's analysis on `anthropics/claude-code#42796` (April 2026), corroborated by Ben Vanik with a Pearson r=0.971 correlation between thinking-block signature length and thinking-content length over 7,146 paired samples, established a machine-readable behavioral metric set rapidly being treated as a de-facto industry standard for coding-agent regression testing (research §2.6). The catalog covers 11 metrics with measured "good" baselines and "degraded" thresholds (Read:Edit ratio, Edits without prior Read %, Reasoning loops/1K, User interrupts/1K, Stop-hook violations, Convention violation rate, First-run test pass rate, Token efficiency, Self-admitted errors/1K, Write-vs-Edit ratio, Repeated edits per file, "simplest" word frequency).

All 11 metrics are computable from session JSONL alone, making them usable in CI without any vendor cooperation. To compute them, agentguard needs a single canonical `Session` schema that every coding-agent driver (ADR-009) normalises into.

Pending experiment `exp_07` is validating the parser against ≥1000 real Claude Code sessions to confirm field coverage.

## Decision

Define a canonical `Session` schema with fields: `messages`, `tool_calls`, `tool_responses`, `thinking_blocks`, `signature_lengths`, `interrupts`, `hook_events`, `usage`, `cwd`, `session_id`, `start_time`, `end_time`. Ship 11 #42796 metric calculators as Robot Framework keywords with `Should Be Above|Below|Equal` assertion variants, using the default thresholds from research §3.3 (Read:Edit ≥4.0; Edits-without-Read ≤10%; Reasoning loops/1K ≤12; Interrupts/1K ≤2; Stop-hook violations =0; First-run pass rate ≥0.9; Token efficiency ≤baseline×1.5; Self-admitted errors/1K ≤0.2; Write-mutation ratio ≤6%).

## Rationale

- 11 metrics × default thresholds give an out-of-the-box regression suite (research §2.6, §3.3).
- Single `Session` schema decouples metric calculators from agent-specific JSONL layouts.
- All metrics are post-hoc analysis on a captured artifact — no per-test instrumentation needed in the agent.
- Thresholds are research-derived, not fabricated; teams can override per-project.

## Consequences

- **Positive**: 11-metric regression sweep on every coding-agent run; vendor-independent; CI-friendly (parse JSONL, assert).
- **Negative**: Schema drift if vendors change JSONL format — driver parsers (ADR-009) must absorb the change.
- **Neutral**: Default thresholds are baseline numbers; teams should re-baseline on their own corpora.

## Alternatives Considered

- **Option A — Vendor-specific metric implementations**: rejected, breaks the cross-agent regression story.
- **Option B — Live tracing via OTel only**: rejected, requires vendor cooperation that isn't reliably available; JSONL exists today.
- **Option C — Subset of #42796 metrics (cherry-pick)**: rejected, the catalog's value is in covering all behavioral dimensions.

## Related ADRs

- ADR-009 (Drivers produce the JSONL this schema parses)
- ADR-005 (Stats API consumes per-metric distributions across runs)
- ADR-012 (OTel listener also reads `Session` and emits spans)
- ADR-015 (SONA records each `Session` for trajectory learning)
- **Hard dependency on pending experiment `exp_07` (parser coverage)**
