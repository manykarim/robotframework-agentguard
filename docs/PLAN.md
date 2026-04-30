# AgentGuard — Implementation Plan

**Project**: `robotframework-agentguard`
**Status**: Planning complete, implementation NOT started
**Date**: 2026-04-29
**Topology**: hierarchical-mesh, 15 agents, raft consensus, hybrid memory + HNSW
**Source of truth**: `docs/research/research.md` (41 KB research report)

This plan synthesises the Phase 0 planning swarm output into one navigable index. Every claim links to the canonical artifact; this file contains no decisions of its own.

---

## 1. Documentation map

| Track | Owner agent | Artifact | Purpose |
|---|---|---|---|
| Architecture decisions | adr-architect | `docs/adr/` (20 ADRs + index) | Bounded, append-only design record |
| Domain model | ddd-domain-expert | `docs/ddd/` (5 files) | Bounded contexts, ubiquitous language, aggregates |
| RuFlo integration | v3-integration-architect | `docs/integration/` (3 files) | 31 RuFlo capabilities mapped to library features |
| Security | security-architect | `docs/security/` (6 files) | STRIDE threat model, default-deny policy, sandbox spec |
| Performance | performance-engineer | `docs/performance/` (4 files) | Cost ceilings, tier routing, non-determinism cost model |
| Experiments | researcher | `docs/research/experiments/` (REPORT.md + 10 logs) | Validated 10 load-bearing assumptions before commit |

---

## 2. Bounded contexts (DDD)

12 contexts grouped Core / Supporting / Generic per `docs/ddd/bounded-contexts.md`:

**Core** (the differentiated value): Skills, Hooks, SubAgents, CodingAgent, BehavioralMetrics.
**Supporting**: MCP, Provider, ToolCallCorrectness, Statistics, Judge.
**Generic**: Security, Telemetry.

Three load-bearing relationships from `docs/ddd/context-map.md`:

1. **Provider as Shared Kernel** for MCP / Skills / Judge / CodingAgent / SubAgents — locks in provider-agnosticism by construction.
2. **CodingAgent → BehavioralMetrics is Conformist** — CodingAgent owns the canonical `Session` schema; metrics adapt, not vice versa, so adding a new CLI is a driver-only change.
3. **Security is Customer/Supplier upstream of Skills + CodingAgent** — default-deny for unsigned skills, mandatory sandbox for code execution.

---

## 3. Architecture Decision Records

20 ADRs in `docs/adr/`, all status `Proposed`:

| # | Title | Bounded context |
|---|---|---|
| 001 | Provider Abstraction (LiteLLM) | Provider |
| 002 | MCP Transport Strategy (`auto`: memory/stdio/HTTP) | MCP |
| 003 | Library Composition (PythonLibCore + DynamicCore) | cross-cutting |
| 004 | Tool-Call Matching (BFCL AST) | ToolCallCorrectness |
| 005 | Statistical Assertion API (scipy, N≥10 default) | Statistics |
| 006 | Skill Discovery + Default-Deny | Skills + Security |
| 007 | Hook Test Harness (12 events, 4 handlers) | Hooks |
| 008 | SubAgent / A2A Harness | SubAgents |
| 009 | Coding Agent Driver Pattern | CodingAgent |
| 010 | Session Schema + #42796 Metrics | CodingAgent + BehavioralMetrics |
| 011 | LLM-as-Judge Calibration (Cohen's κ ≥ 0.7) | Judge |
| 012 | OTel + RF Listener | Telemetry |
| 013 | Sandbox Policy (`--allow-code-execution` opt-in) | Security |
| 014 | Spec Version Pinning (MCP / A2A 1.0 / Skills) | cross-cutting |
| 015 | RuFlo SONA Self-Learning | cross-cutting |
| 016 | RuFlo Memory + HNSW Knowledge Graph | cross-cutting |
| 017 | RuFlo Hooks Integration | cross-cutting |
| 018 | RuFlo Swarm Test Generation | cross-cutting |
| 019 | 3-Tier Model Routing | cross-cutting |
| 020 | AIDefence Skill Scanner | Security |

ADRs blocked on follow-up evidence before promotion to `Accepted`:

- **ADR-010** ⟵ blocked on ≥1000 real Claude Code session parses (exp_07 confirms field stability with one fixture; need scale).
- **ADR-011** ⟵ blocked on judge calibration against 200-item human-labeled set.
- **ADR-015** ⟵ blocked on SONA pattern-extraction recall on 1000 historical degraded sessions.

---

## 4. RuFlo capability coverage

`docs/integration/ruflo-capability-map.md` covers **31 capabilities** across:

- **Memory**: AgentDB skill baselines · BFCL ground-truth · judge calibration sets · regression baselines · failure-pattern store · ONNX 384-dim embeddings · DiskANN fallback · Claude-Code↔AgentDB bridge.
- **Self-learning**: SONA trajectory recording · ReasoningBank pattern distillation · EWC++ to prevent forgetting · neural pattern training (predict BFCL failures).
- **Hooks**: Intelligence attention · routing · 12 lifecycle events wired into the test runner.
- **Tier routing**: Tier-1 WASM Agent Booster (all 11 #42796 calculators) · Tier-2 Haiku (simple judges) · Tier-3 Sonnet/Opus (rubric judges).
- **Security**: AIDefence scan / PII detection / adaptive learning · supply-chain controls.
- **Coordination**: Swarm orchestration (hierarchical-mesh × 15) · Hive-mind raft (flaky-test gating, TARr@20 ≥ 0.85) · Hive-mind Byzantine (judge disagreement, N=5 PBFT) · 12 background workers (testgaps, consolidate, benchmark, audit, optimize, deepdive, document, refactor, ultralearn, predict, preload, map).
- **Eat-our-own-dogfood**: `tests/meta/` uses AgentGuard to test RuFlo's own MCP server.

End-to-end data flow: see `docs/integration/data-flow.md` (mermaid sequence).
Anti-drift: see `docs/integration/anti-drift.md`.

---

## 5. Security posture

`docs/security/threat-model.md` catalogues 5 surfaces (skill ingestion, MCP servers, hook execution, coding-agent driving, A2A delegation). Top 5 threats:

1. **Skill prompt-injection escalating to host-agent EoP** (ToxicSkills 36% baseline; OWASP LLM01 / CWE-1427).
2. **Sandbox escape during code execution** (CVE-2024-21626 *Leaky Vessels* class).
3. **MCP tool-description injection / rug-pull** — bypasses every downstream check.
4. **Hook HTTP exfiltration of `transcript_path`** — secrets leak with no user signal.
5. **Skill `scripts/` infostealer** (ClawHavoc / AMOS) — proven in-the-wild.

Phase-1 mitigations:

1. Default-deny skill scanner pipeline (`docs/security/skill-scanner-spec.md`, 7 stages with `aidefence_scan` + cosign signature) → closes #1, #5, most of #2. Cited by ADR-006.
2. Docker sandbox profile (`--network=none`, read-only root, dropped caps, no docker-socket mount, `--allow-code-execution` flag gate) → closes #2. Required by ADR-013.
3. Universal redactor + recording HTTP-hook proxy → closes #4 and the secret-leak portions of #2/#5. Informs ADR-020.

Sandbox backends matrix: `docs/security/sandbox-spec.md`.
Supply-chain controls (SBOM, `uv.lock` hashes, cosign-signed releases): `docs/security/supply-chain.md`.

---

## 6. Performance budgets

`docs/performance/budgets.md`:

| Tier | Latency | Cost / call | Use |
|---|---|---|---|
| Tier 1 (WASM Agent Booster) | <1 ms | $0 | All 11 #42796 calculators, BFCL AST, JSON schema, regex |
| Tier 2 (Haiku) | ~500 ms | $0.0002 | Simple judges, frontmatter sanity |
| Tier 3 (Sonnet) | 2–5 s | $0.003 | Multi-criterion rubrics |
| Tier 3 (Opus) | 2–5 s | $0.015 | Trajectory analysis, calibration |

**Cost projection (30 skills × N=10 reps)**: tier1 = $0, tier2 = $1.02, tier3-Sonnet = $4.05, tier3-Opus = $20.25 (stored in RuFlo memory `agentguard/planning/perf_cost_projection_30skills`).

Three highest-leverage optimisations (compounding):

1. **Cached judgments** — hash `(skill, rubric, judge_model)` → ~70% reduction on stable suites.
2. **Adaptive N** — start at N=3, expand only on bootstrap-CI non-convergence → ~50% additional reduction.
3. **Smart routing prefilter** — string→regex→AST→cosine cascade before any LLM judge → ~30% additional reduction.

Combined stack drops realistic-mix daily CI from ~$0.45 to ~$0.05 per skill grading.

Budgets most likely to break first:

1. **Tier-2 latency (≤500 ms mean)** — Anthropic Haiku tail latency volatile during traffic spikes.
2. **Robot Framework startup <2 s** — scipy import alone is ~300 ms; must be lazy.
3. **Memory cap 500 MB** — HNSW + ONNX at 10K stored sessions; int8 quantization mandatory.

---

## 7. Phase 0 experiment validations

`docs/research/experiments/REPORT.md` documents 9 PASS / 1 PARTIAL / 0 FAIL across 10 experiments. Confirmed toolchain: fastmcp 3.2.4, mcp 1.27.0, litellm 1.83.0, inspect-ai 0.3.213, scipy 1.17.1, robotframework 7.4.2, robotframework-pythonlibcore 4.5.0, a2a-sdk 1.0.2.

**Three architectural implications fed back into the plan:**

1. **MCP-first end-to-end.** In-memory FastMCP is ~2.22 ms/call (exp_01); aidefence is reachable over the same MCP transport (exp_10). Collapse the security module's CLI shim into the MCP client surface — affects ADR-020.
2. **Session-JSONL parser is Phase-3 IP.** The canonical schema in research §7.2 is NOT top-level in real Claude Code JSONL (exp_07). All `tool_calls`/`tool_responses`/`interrupts`/`hook_events`/`usage` fields must be derived by walking `assistant.message.content[]` and pairing via `parentUuid`. Schedule a dedicated parser design spike before any #42796 metric keyword — affects ADR-010.
3. **Python 3.12 floor recommended.** `mcp-eval 0.0.1` requires ≥3.12; the upside (mature, async, OTel-native eval engine) outweighs user-base friction. Recommend bumping `requires-python` to `>=3.12` — affects ADR-014.

---

## 8. Phased delivery roadmap

### Phase 1 — MCP + Skills (≈ 3 months)

Goal: usable 0.x release covering the two highest-priority surfaces.

- **Week 1–2**: bootstrapping (RF 7.x, PythonLibCore skeleton per ADR-003, OTel listener stub per ADR-012).
- **Week 3–8**: MCP module — wrap FastMCP `Client` for all 4 transports per ADR-002; wrap MCP Inspector `--cli`; implement `MCP Inspector Should Connect`, `List MCP Tools`, `Call MCP Tool`, `MCP Tool Output Should Match Schema`, `MCP Server Should Implement Capabilities`. Port `inspect_evals.bfcl` AST matcher (exp_09) per ADR-004.
- **Week 6–12**: Skills module — `SKILL.md` parser, frontmatter validator, discovery across 4 paths per ADR-006. Skill grader keyword running an Inspect AI Task per ADR-003 (exp_04). Convention-violation scorer.
- **Week 10–12**: Stats module — scipy-backed Mann-Whitney/Wilcoxon, Cliff's δ, Vargha-Delaney A, bootstrap CIs, pass@k, TARr@N/TARa@N (exp_06). Classification-based judge per ADR-011.
- **Phase-1 mitigations** (security): default-deny scanner pipeline, redactor, recording HTTP-hook proxy.

Deliverable: `robotframework-agentguard 0.1` on PyPI; ten reference `.robot` suites; Grafana reporting integration; GitHub Actions template.

### Phase 2 — Hooks + SubAgents (≈ 2 months)

- **Hooks module** per ADR-007: `Synthesize Hook Input`, `Run Hook {Command,HTTP,Prompt,Agent}`, decision assertions, loop-safety. Cross-tool shim (Claude Code, OpenCode, Copilot, Cline, Continue).
- **SubAgents module** per ADR-008: `a2a-sdk 1.0.2` adapter (exp_08); `Get Agent Card`, `Send Task`, `Wait For Task Completion`, `Get Task Artifact`, `Task Should Have Status`. Bridges to LangGraph / CrewAI / AutoGen / OpenAI Agents SDK. Trajectory comparison via the BFCL matcher.
- **Sandbox** per ADR-013: Docker backend with read-only fs + no network as default; opt-in `--allow-code-execution`.

### Phase 3 — Coding-agent harness (≈ 2 months)

- **`CodingAgentDriver`** per ADR-009 wrapping Claude Code, OpenAI Codex CLI, GitHub Copilot CLI, Aider, OpenCode, Cline, Continue.
- **`Session.parse_jsonl` design spike** (week 1, blocking) per exp_07 implication — Claude Code parser first; fixture from `~/.claude/projects/`.
- **#42796 metric pack** per ADR-010 — 11 calculators in WASM (Tier-1 routing per ADR-019).
- **Benchmark integration**: SWE-bench Verified, Aider, LiveCodeBench, HumanEval, MBPP — each producing pass@1/pass@3 keywords.
- **Replay/time-travel** for LangGraph and CrewAI bridges from Phase 2.

### Phase 4 — OSS hardening + RuFlo full integration

- **AIDefence** wired over MCP per exp_10 / ADR-020.
- **SONA** ReasoningBank trajectory recording, pattern distillation, EWC++ per ADR-015.
- **HNSW knowledge graph** of skill baselines, regression baselines, judge calibration sets per ADR-016.
- **Hive-mind raft** flaky-test gating per ADR-018.
- **12 background workers** wired (testgaps, consolidate, benchmark prioritised).
- **Tool Approval / human-in-the-loop** hook (mirrors Inspect AI policy gating).
- **Skill marketplace security scanner** — ToxicSkills mitigation per ADR-006/ADR-020.
- **Meta-test suite** at `tests/meta/` — AgentGuard tests RuFlo's own MCP server.

---

## 9. Risk register

| # | Risk | Owner | Mitigation | ADR |
|---|---|---|---|---|
| R1 | LLM-as-Judge calibration drift | Judge context | Cohen's κ ≥ 0.7 hard gate before scoring real runs | ADR-011 |
| R2 | Sandbox escape during arbitrary code execution | Security | Inspect AI sandbox toolkit; `--allow-code-execution` flag | ADR-013 |
| R3 | Skill marketplace supply-chain compromise | Security | Default-deny unsigned third-party; AIDefence pre-grading scan | ADR-006, ADR-020 |
| R4 | Determinism vs reproducibility (temp=0 not enough) | Statistics | N≥10 (ideally ≥30) default; non-deterministic-test-report header in HTML | ADR-005 |
| R5 | Standards velocity (A2A 1.0 fresh, Skills spec churning) | cross-cutting | Pin spec versions; deprecation warnings; `compatibility_matrix.json` | ADR-014 |
| R6 | Vendor-side regressions (e.g. Anthropic 2026-04-23 postmortem, Claude Code #42796) | BehavioralMetrics | Canary suite with Mann-Whitney + Cliff's δ vs stored baseline | ADR-005, ADR-010 |
| R7 | Session-JSONL parser is the IP and is harder than research suggests | CodingAgent | Dedicated Phase-3 design spike; ship Claude-Code parser first | ADR-010, exp_07 |
| R8 | `mcp-eval` 3.12-only tightens user base | cross-cutting | Recommend 3.12 floor; document `pytest-mcp` fallback for 3.11 holdouts | ADR-014, exp REPORT |
| R9 | Tier-2 (Haiku) tail latency breaks budget under provider load | Performance | LiteLLM Router fallback; cached judgments | ADR-019, perf docs |
| R10 | Memory footprint at scale (HNSW + ONNX, 10K sessions) | Memory | Mandatory int8 quantization; DiskANN fallback >250K vectors | ADR-016, perf docs |

---

## 10. Open questions (require follow-up before Phase 1 GA)

- Does `mcp-eval` ship a 3.11-compatible release in the Phase-1 window, or is 3.12 the floor?
- What is the realistic upper bound on session JSONL size? (sampled 3.6 MB; some agents may produce 100+ MB sessions → streaming parser required)
- Does `a2a-sdk 1.0.2` cover all four bridge targets natively (LangGraph, CrewAI, AutoGen, OpenAI Agents SDK), or do we need adapter shims?
- Is the MCP Inspector CLI `--method` flag stable enough to pin against, or do we need to call FastMCP directly for protocol-compliance probes?
- Which judge model(s) (Sonnet vs Opus vs Haiku) clear Cohen's κ ≥ 0.7 against a 200-item human-labeled rubric?
- Does the SONA pattern-extraction recall hold on 1000 historical degraded sessions (ADR-015 acceptance criterion)?

---

## 11. What to do next (when implementation begins — NOT now)

1. Adopt `requires-python = ">=3.12"` (per exp REPORT recommendation).
2. Move ADRs 001–005 + 010 to `Accepted` after the Python-floor decision and the `Session.parse_jsonl` spike.
3. Run the canary suite once on a current Claude Sonnet 4.5 to seed `baselines/2026-Q2.json`.
4. Stand up the Phase-1 GitHub Actions template and Grafana dashboard scaffolding.
5. Calibrate the default judge against the 200-item human-labeled set; gate ADR-011 promotion.

---

**Planning swarm IDs**: `swarm-1777488372908-agcf36` (RuFlo) · 6 specialised agents · 1.3M tokens delivered across 5 parallel Agent calls.
