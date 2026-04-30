# RuFlo Capability Map — robotframework-agentguard

**Purpose.** This document is the implementation-detail companion to ADR-015..ADR-020. For every RuFlo capability listed in `CLAUDE.md` ("Memory & Vector Search", "Key MCP Tools", "Swarm Capabilities", "Memory Capabilities", "3-Tier Model Routing"), it states exactly which AgentGuard library feature uses it, in which DDD bounded context, when the call is triggered, and how we degrade if the capability is unavailable.

**Bounded contexts referenced** (from `docs/ddd/README.md`): Skills, Hooks, SubAgents, CodingAgent, MCP, ToolCallCorrectness, BehavioralMetrics, Judge, Statistics, Security, Provider, Telemetry.

**Performance/cost cells** are placeholders `<see docs/performance/budgets.md>` owned by the `performance-engineer` stream.

---

## 1. Capability-by-capability mapping

| RuFlo Capability | MCP Tool(s) / CLI | AgentGuard Feature | Bounded Context (DDD) | When Triggered | Failure Mode + Fallback |
|---|---|---|---|---|---|
| **AgentDB + DiskANN/HNSW vector search — skill baselines** | `memory_store`, `memory_search`, `memory_list` (ns `agentguard/baselines/skills`) | Skill grader stores last-good scorecards per `(skill_id, model_id, judge_id)`; future runs `memory_search` to fetch baseline before grading. (ADR-015) | Skills + Statistics | `Run Skill Eval` keyword setup; nightly canary suite | If AgentDB down → fall back to JSON file at `baselines/<skill>.json` (research §4.5). Grading still runs; regression test `Skill Improves Over Previous Baseline` is `SKIPPED` not failed. |
| **AgentDB — BFCL ground-truth datasets** | `memory_store` ns `agentguard/datasets/bfcl`, `memory_search` | `Load BFCL Dataset` keyword pulls expected `(prompt, tools, expected_call)` triples; semantic search finds nearest neighbour categories. (ADR-016) | ToolCallCorrectness | Phase-1 `Load BFCL Dataset category=...`; before every `Generate Tool Call` AST match | Bundled `bfcl_v3_simple.jsonl` shipped in `src/AgentTest/resources/` is the offline fallback. |
| **AgentDB — judge calibration sets** | `memory_store` ns `agentguard/judge/calibration`, `memory_search_unified` | `Calibrate Judge` keyword (research §8.1) stores human-labeled samples; on every judge invocation, fetch the k=20 nearest calibration items and compute Cohen's κ before allowing the judge verdict. (ADR-017) | Judge + Statistics | `AgentTest.__init__` if `judge_model` set; before first `LLM Judge Should Score At Least` per suite | If AgentDB unreachable → emit Robot WARN, run with κ=null, mark all judge assertions as `informational` not `assertive`. |
| **AgentDB — regression baselines for #42796 metrics** | `memory_store` ns `agentguard/baselines/behavioral`, `memory_search` | `BehavioralMetrics` repo persists per-session vector of all 11 #42796 metrics; Mann-Whitney compares current run vs nearest baseline cohort. (ADR-018) | BehavioralMetrics + Statistics | After every `Run Coding Agent` keyword | Local SQLite cache `~/.agentguard/baselines.db` mirrors writes; Mann-Whitney runs against cache. |
| **AgentDB — recurring failure patterns** | `memory_store` ns `agentguard/patterns/failures`, `memory_search` | When a test fails, the listener stores `(skill_id, metric, observed, expected, error_message)`; next pre-run, retrieves top-5 similar prior failures and surfaces them as Robot test documentation. | BehavioralMetrics + Skills | Robot listener `end_test` on FAIL; `start_test` for context | Failure is still reported; the "similar past failures" panel just stays empty. |
| **ONNX 384-dim embeddings — skill description similarity** | `memory_store` (auto-embedded), `embeddings_compare`, `embeddings_search` | "Find similar past failures for this skill" uses cosine similarity over the SKILL.md `description` frontmatter. (ADR-015 §3) | Skills | `Load Skill` keyword | If ONNX runtime missing → fall back to BM25 over skill descriptions (rapidfuzz). |
| **ONNX embeddings — tool description neighbourhood for BFCL** | `embeddings_search`, `memory_search` | For BFCL "decide-not-to-act" cases, embed the prompt and the available tool descriptions; if no tool's cosine similarity exceeds threshold τ, the expected call is "no tool". (ADR-016 §4) | ToolCallCorrectness | Inside `Tool Call Should Match Name` when `mode=semantic` | Threshold tuning falls back to AST-only matching (research §3.1). |
| **Claude Code ↔ AgentDB Bridge (auto-import)** | `memory_import_claude --allProjects=true`, `memory_bridge_status`, `.claude/helpers/auto-memory-hook.mjs` | On AgentGuard CI bootstrap, import this project's own `~/.claude/projects/.../*.jsonl` so BehavioralMetrics has a realistic training corpus from day one. (ADR-018 §5) | BehavioralMetrics | `npx ruflo memory_import_claude` invoked once in CI bootstrap script `scripts/ruflo-bootstrap.sh` | If user has no Claude history → metrics simply have no priors; bootstrap does not fail. |
| **DiskANN — large dataset alternative** | (same memory tools, AgentDB selects backend by size) | When BFCL or judge calibration sets exceed HNSW working-set memory (>~250k vectors per CLAUDE.md "Memory Capabilities"), AgentGuard configures the namespace with DiskANN — perfect-recall at 1K, 8000× faster insert. (ADR-019) | ToolCallCorrectness + Judge | Namespace creation when `dataset_size > threshold` | If DiskANN unavailable → degrade to HNSW with a Robot WARN; insert performance drops, search still correct. |
| **SONA Self-Learning — trajectory recording** | `hooks_intelligence_trajectory-start`, `hooks_intelligence_trajectory-step`, `hooks_intelligence_trajectory-end` | Every `Run Skill Eval`, `Run Hook Command`, `Run Coding Agent` execution emits a trajectory; SONA distills recurring assertion-failure patterns into reusable Robot keyword templates. (ADR-020) | Skills + Hooks + CodingAgent + Telemetry | `pre-task` hook starts trajectory; per-keyword event = `trajectory-step`; `post-task` ends it | If SONA disabled → trajectories not recorded; tests still execute; nightly `consolidate` worker becomes a no-op. |
| **SONA — pattern distillation (ReasoningBank)** | `hooks_intelligence_pattern-store`, `hooks_intelligence_pattern-search`, `hooks_intelligence_learn` | "We keep asserting that skill X emits no `eval(`" is distilled into a stored pattern; next run, the pattern is loaded into the SkillsLibrary as an auto-injected assertion. (ADR-020 §4) | Skills + BehavioralMetrics | `session-end` hook; consumed at next `Load Skill` | Pattern store empty on first run → no auto-injected assertions, manual rubric still in effect. |
| **SONA — EWC++ to prevent forgetting** | `hooks_intelligence_learn` (with `mode=ewc`), `neural_train` | When a new skill baseline is added, EWC++ ensures older skill baselines do not get overwritten. Critical because we expect 100s of skill baselines to coexist. (ADR-020 §5) | BehavioralMetrics + Statistics | After every successful `Calibrate Judge` or new baseline write | Without EWC++ → newer baselines bias the cluster; periodic `Mann Whitney U Should Show Improvement` drift alarm catches it. |
| **Hooks Intelligence — attention-weighted retrieval** | `hooks_intelligence_attention`, `hooks_intelligence_pattern-search` | Before re-running a flaky test, query "this test failed last 3 times for skill X"; surface the most attention-weighted prior failure to the test reporter so QA sees pattern, not noise. | Skills + BehavioralMetrics | `pre-task` hook on any test tagged `regression` | If no priors → attention returns empty list, test runs as normal. |
| **Hooks Routing — `hooks_route`** | `hooks_route`, `hooks_pre-task`, `hooks_post-task`, `hooks_post-edit`, `hooks_session-start`, `hooks_session-end` | Route each Robot Framework keyword call to the correct model tier (Tier 1/2/3 per ADR-026). Trigger memory consolidation on `session-end`; run skill scanning on `pre-edit` of any `SKILL.md`. | Hooks + Provider + Skills | Every keyword invocation; every file edit during test execution | If router down → default route = Tier 3 (Sonnet) for safety; no test fails. |
| **3-Tier Model Routing — Tier 1 (WASM Agent Booster)** | `hooks_model-route` (returns tier=1), `wasm_agent_*` | All 11 #42796 deterministic metric calculators (`Read Edit Ratio`, `Edits Without Prior Read Percent`, `Reasoning Loops Per 1K`, etc.) run as WASM modules — sub-1ms, $0. (ADR-018 §6, ADR-026) | BehavioralMetrics + ToolCallCorrectness | Inside every `... Should Be ...` assertion variant of a #42796 metric | Cost: $0. If WASM unavailable → Python pure-Python implementation, ~5-15ms per metric. `<see docs/performance/budgets.md>` |
| **3-Tier Model Routing — Tier 2 (Haiku)** | `hooks_model-route` (returns tier=2) | Simple judges: "is this hook decision reasonable", binary AST diff classification, frontmatter sanity ("does this `description` actually describe what `SKILL.md` does"). | Judge + Hooks + Skills | When `LLM Judge Should Score At Least` is invoked with `complexity=low` | If Haiku rate-limited → upgrade to Tier 3. Latency: `<see docs/performance/budgets.md>`. Cost: ~$0.0002/call. |
| **3-Tier Model Routing — Tier 3 (Sonnet/Opus)** | `hooks_model-route` (returns tier=3) | Full rubric judgments, multi-step trajectory analysis, `LLM Judge Should Score At Least` with rubric file, Mann-Whitney rationale generation. | Judge + Statistics + CodingAgent | When `complexity>30%` per ADR-026; default for `judge_model=...` set explicitly | Always available (primary). Cost: `<see docs/performance/budgets.md>` per 1K test runs. |
| **AIDefence — prompt-injection scan** | `aidefence_scan`, `aidefence_is_safe`, `aidefence_analyze` | Every `SKILL.md`, every hook stdout, every tool output, every judge prompt is scanned. `Skill Should Pass Security Scan` keyword (research §4 Phase-4, §8.3, *ToxicSkills*) is the user-facing assertion. (ADR-020 security ADR) | Security + Skills + Hooks + Judge | `pre-edit` of SKILL.md; `post-task` of any hook/tool; before judge call | If AIDefence unreachable → strict mode = block (fail-closed); permissive mode = warn-only. Configurable via `AgentTest(security_mode=strict|permissive)`. |
| **AIDefence — PII detection** | `aidefence_has_pii`, `transfer_detect-pii` | Session JSONL transcripts are PII-scrubbed before they reach the judge or get logged into `output.xml`. | Security + Telemetry + CodingAgent | `Run Coding Agent` post-step; before any `output.xml` write | If PII scan fails → transcript is redacted entirely (`[PII REDACTED]`) and Robot WARN emitted. |
| **AIDefence — adaptive learning** | `aidefence_learn`, `aidefence_stats` | False-positive corrections from QA engineers (e.g., "this `<script>` literal in a test fixture is not malicious") are fed back via `aidefence_learn`. | Security | After human-marked false positive in `output.xml` review | If learning disabled → AIDefence stays at baseline; no quality regression. |
| **Hive-Mind Consensus — flaky-test gating** | `hive-mind_init`, `hive-mind_spawn`, `hive-mind_consensus` (raft) | Auto-generated test suites are run N=20 times; hive-mind votes "deterministic enough" before the suite is allowed to commit to `tests/`. Threshold = TARr@20 ≥ 0.85 (research §2.7). | Statistics + Skills | `npx agentguard skill-eval --auto-generate --commit` workflow | If hive-mind unavailable → fall back to single-judge gate; emit WARN on commit message. |
| **Hive-Mind Consensus — judge disagreement** | `hive-mind_consensus` (Byzantine PBFT) | When two judges (e.g., Sonnet vs gpt-4o) disagree on a `LLM Judge Should Score At Least` verdict by more than σ=0.15, escalate to PBFT vote across N=5 judges. (ADR-017 §6) | Judge + Statistics | Inside `LLM Judge Should Score At Least` when `mode=consensus` | If Byzantine consensus times out → fall back to majority vote; record disagreement vector for SONA learning. |
| **Swarm Orchestration — multi-agent test generation** | `swarm_init --topology hierarchical-mesh --max-agents 15`, `agent_spawn`, `task_orchestrate` | One agent generates Robot test cases per skill; one agent per #42796 metric; one aggregator agent merges results into a single `.robot` suite. (ADR-019) | Skills + BehavioralMetrics + Telemetry | `agentguard generate-tests --skill <id>` CLI command | If swarm fails → sequential single-agent generation; ~10× slower but functional. |
| **Background Workers — `testgaps`** | `hooks_worker-dispatch type=testgaps`, `hooks_worker-list`, `hooks_worker-status` | Continuously identifies skills with no behavioral test; opens GitHub issues with `area:test-gap` label. | Skills + BehavioralMetrics | Cron: every 6h via `npx ruflo daemon` | Manual `agentguard scan-gaps` CLI replaces the worker. |
| **Background Workers — `consolidate`** | `hooks_worker-dispatch type=consolidate` | Nightly merge of ReasoningBank trajectories; deduplicates patterns, prunes <κ=0.3 ones. | BehavioralMetrics + Skills | Cron: 02:00 local | Patterns accumulate uncompressed; no functional impact, just storage growth. |
| **Background Workers — `benchmark`** | `hooks_worker-dispatch type=benchmark` | Hourly canary suite re-run against the same prompts/model; results compared to baseline via Mann-Whitney + Cliff's delta (research §8.6). | BehavioralMetrics + Statistics | Cron: hourly | Manual `agentguard canary run` keyword. |
| **Background Workers — others** (`audit`, `optimize`, `deepdive`, `document`, `refactor`, `ultralearn`, `predict`, `preload`, `map`) | `hooks_worker-list`, `hooks_worker-dispatch` | Used opportunistically: `audit` reviews new ADRs; `document` regenerates `libdoc` HTML; `predict` warms caches before scheduled CI runs. | Telemetry + Skills | On-demand or cron | All optional; AgentGuard runs without them. |
| **Neural Pattern Training — failure prediction** | `neural_train`, `neural_predict`, `neural_patterns`, `neural_status` | Train a small classifier on per-skill metric vectors → predict "this skill will likely fail BFCL"; if probability > 0.7, skip the expensive Tier-3 eval and report the prediction with confidence. Saves Tier-3 model calls. (ADR-016 §5) | BehavioralMetrics + Statistics + Provider | Before each `Run Skill Eval`; retrained nightly via `ultralearn` worker | If classifier underconfident (<0.6) → run the full eval anyway. Cost savings: `<see docs/performance/budgets.md>`. |
| **Coordination Topology — hierarchical-mesh** | `swarm_init --topology hierarchical --max-agents 15` (anti-drift, per CLAUDE.md "Swarm Configuration") | Long-running coding-agent runs are coordinated by a hierarchical lead; short critic agents (per-metric) are mesh peers under the lead. (ADR-019 §3) | CodingAgent + Skills + BehavioralMetrics | Every `agentguard generate-tests`; every multi-agent grading run | If `mesh-coordinator` unavailable → fall back to pure hierarchical (slower, but anti-drift preserved). |
| **WASM Agent Booster — Tier 1 deterministic checkers** | `wasm_agent_create`, `wasm_agent_prompt`, `wasm_agent_tool` | All 11 #42796 metric calculators (`Read Edit Ratio`, `Edits Without Prior Read Percent`, `Reasoning Loops Per 1K Tool Calls`, `User Interrupts Per 1K`, `Stop Hook Violations`, `Convention Violation Rate`, `Token Usage Per Prompt`, `Self Admitted Errors Per 1K`, `Write Mutation Ratio`, `Simplest Word Frequency`, `Repeated Edits Per File`) run inside WASM. Zero LLM calls, sub-ms. | BehavioralMetrics | Inside every `... Should Be ...` assertion of a #42796 metric | Pure-Python fallback (research §3.3). |
| **MCP Bridge — meta-test (eat-our-own-dogfood)** | the library's own `MCPLibrary` + RuFlo's MCP server | A `tests/meta/` suite uses AgentGuard to test RuFlo's own MCP server: protocol compliance, tool list completeness (target: 314 tools per CLAUDE.md), latency, judge agreement. (ADR-018 §8) | MCP + Telemetry | Manual `pytest tests/meta` or scheduled in CI on RuFlo updates | Failures here block AgentGuard releases; no fallback. |

---

## 2. Per-capability rationale notes

### 2.1 Why AgentDB everywhere, not local SQLite
Research §2.7 mandates baseline comparisons (Mann-Whitney, Cliff's delta) on every regression test. AgentDB's namespaces give us the per-`(skill, model, judge)` slicing for free, and `memory_search_unified` lets the BehavioralMetrics context cross-reference Claude-Code session priors with AgentGuard's own baselines without writing join logic. ADR-015 covers the baseline schema; ADR-018 covers the metric persistence schema.

### 2.2 Why ONNX embeddings for BFCL "decide-not-to-act"
Research §3.1 lists `Should Not Call Any Tool` as a first-class assertion. The honest implementation needs to know "did the model correctly decide nothing was a good fit" — that requires comparing the prompt embedding to the available tools' embeddings. ONNX gives us this for free per CLAUDE.md "ONNX Embeddings" line.

### 2.3 Why SONA (and not just static rules)
Research §8.6 notes vendor-side changes silently move metric distributions. Static thresholds drift. SONA's trajectory recording → pattern extraction loop is exactly the feedback signal the canary suite needs. EWC++ is needed because we expect 100s of skill baselines and naive online learning would forget older ones.

### 2.4 Why hooks intelligence rather than ad-hoc logging
Research §2.3 identified hook-testing as the single largest ecosystem gap. Hooks Intelligence (`pattern-store` + `attention`) is the only pre-built tool that gives us "tell me which prior failures look most like this one". Building it from scratch would duplicate ~2,500 LOC.

### 2.5 Why 3-tier routing is non-negotiable for cost
Research §2.7 + §8.4 mandate N≥10 runs for any LLM-mediated assertion. With Tier 3 alone, a 100-skill nightly canary @ N=10 costs ~$X (`<see docs/performance/budgets.md>`). With tier routing where 80% of assertions land in Tier 1, the same canary costs ~5% of the all-Sonnet number.

### 2.6 Why AIDefence is mandatory, not opt-in
Snyk *ToxicSkills* (research §8.3) found 36% of community skills are flawed and 76 are confirmed malicious. AgentGuard's `Skill Should Pass Security Scan` (research §4 Phase-4) literally cannot exist without a prompt-injection + PII detector. AIDefence is that detector.

### 2.7 Why hive-mind for flaky-test gating
Research §2.7 + §8.4 establish that `temperature=0` does not yield reproducibility (15% variance, 70% best-vs-worst). A single judge cannot reliably decide "this auto-generated test is non-flaky enough to commit". Raft consensus across N=20 trial runs is the closest available primitive to AISI-grade gating.

### 2.8 Why hierarchical-mesh and not pure mesh or pure hierarchical
CLAUDE.md "Swarm Configuration & Anti-Drift" mandates hierarchical for coding swarms. AgentGuard mixes long-running coding-agent runs (need hierarchical lead for anti-drift) with short per-metric critic agents (cheap, parallel — mesh fits). Hierarchical-mesh is the documented hybrid.

### 2.9 Why WASM for the 11 metric calculators
Each metric is a pure function over a JSONL session. Deterministic by definition. Tier 1 is the right tier (CLAUDE.md ADR-026: "<1ms, $0"). Anything else burns money for no quality gain.

### 2.10 Why testgaps + consolidate + benchmark are the three workers we depend on
- `testgaps`: directly serves research §3.3 ("ship the eleven #42796 metrics as keywords") — finds skills missing them.
- `consolidate`: keeps SONA's pattern store from unbounded growth.
- `benchmark`: implements research §8.6's "ship a canary suite" recommendation.

The other 9 workers are nice-to-have.

---

## 3. Coverage matrix — capability × bounded context

| Bounded Context | Primary RuFlo capabilities used |
|---|---|
| **Skills** | AgentDB baselines, ONNX embeddings, AIDefence scan, SONA pattern store, hive-mind consensus, swarm orchestration, `testgaps` worker |
| **Hooks** | Hooks routing, Hooks Intelligence (trajectory + attention), AIDefence scan, Tier-2 simple judges |
| **SubAgents** | A2A coordination via swarm topology, hive-mind consensus on delegation chains, hooks intelligence trajectory |
| **CodingAgent** | Claude Code bridge (auto-import), SONA trajectory recording, Tier-3 routing, hierarchical-mesh topology |
| **MCP** | MCP bridge meta-test, AgentDB tool-schema cache, hooks routing |
| **ToolCallCorrectness** | AgentDB BFCL datasets, ONNX tool-description embeddings, WASM AST matchers (Tier 1), DiskANN at scale |
| **BehavioralMetrics** | AgentDB regression baselines, Claude bridge auto-import, SONA EWC++, neural pattern training, WASM Tier-1 calculators, `consolidate` + `benchmark` workers |
| **Judge** | AgentDB calibration sets, hive-mind Byzantine consensus, Tier-2/3 routing |
| **Statistics** | AgentDB baselines (for Mann-Whitney input), neural prediction, hive-mind raft |
| **Security** | AIDefence (scan + PII + learn) — sole consumer |
| **Provider** | Hooks routing (model-route + model-stats), `ruvllm_status` |
| **Telemetry** | All trajectory hooks, OpenTelemetry bridge, `document` worker for libdoc regeneration |

---

## 4. Coordination notes

- This map is the implementation companion to **ADR-015..ADR-020** authored in parallel by `adr-architect`. ADRs reference back to this file for the "which tool, which call site" detail.
- All concrete latency / cost / token numbers are owned by `performance-engineer` and tracked in `docs/performance/budgets.md` (placeholder cells above).
- Canonical mapping (count + tool list) is mirrored to RuFlo memory: `npx -y ruflo@latest memory store --key "ruflo_capability_count" --namespace agentguard/planning`.
- Mapped-tool count: **31 distinct RuFlo capabilities** spread across **45+ MCP tools** from the 314-tool catalogue.
