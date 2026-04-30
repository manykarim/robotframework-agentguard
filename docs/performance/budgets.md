# Performance Budgets — `robotframework-agentguard`

> **Scope.** Hard numeric ceilings every Phase-1 release must meet. CI gates fail if any budget is exceeded by >20% on the canary suite. All budgets are *per* canonical keyword / artifact, not amortized.
>
> **Sources.** CLAUDE.md ADR-026 (3-tier routing); Anthropic public pricing page snapshot Apr 2026; `mcp-eval` README (latency/token telemetry); Inspect AI docs (`Task → Solver → Scorer` cost accounting); FastMCP transport docs. Items marked `[ASSUMPTION → exp_NN]` are unvalidated and must be confirmed by the matching experiment in `benchmarks-plan.md`.

---

## 1. Per-Keyword Latency Budgets (single invocation, p95)

Maps the three tiers from CLAUDE.md ADR-026 onto agentguard keyword classes.

| Tier | Handler | Budget (p95) | Cost / call | Keyword classes |
|------|---------|--------------|-------------|-----------------|
| **1** | WASM / pure-Python (no LLM) | **<1 ms** | $0 | All BFCL AST matchers (§3.1), JSON-schema validators, `SKILL.md` frontmatter validator, all 11 #42796 metric calculators (§3.3), scipy stats keywords (§3.4 except judge), regex convention scanner |
| **2** | Haiku (claude-haiku-4) | **≤500 ms** mean, **≤900 ms** p95 | **$0.0002** | `Hook Should Be Reasonable`, single-criterion `Tool Output Should Be Semantically Equal` for outputs ≤500 tokens, simple rubric judging |
| **3** | Sonnet (claude-sonnet-4-5) / Opus (claude-opus-4-7) | **2-5 s** mean, **≤8 s** p95 | $0.003 (Sonnet) / $0.015 (Opus) | Full `LLM Judge Should Score At Least` with multi-criterion rubric, `plan_is_efficient`, trajectory-quality assessment, judge-calibration runs |

**Rationale.** Tier-1 numbers are CLAUDE.md ADR-026 verbatim. Tier-2/Tier-3 latency assumes a warm LiteLLM client and a single round-trip; cold-start adds ≤300 ms one-time per suite. p95 (not mean) is the gating metric because LLM tail latency dominates wall-clock. `[ASSUMPTION → exp_03]`: validate Haiku p95 against Anthropic prod traffic in eu-central.

---

## 2. MCP Tool Latency Budgets (transport overhead, excludes server work)

| Transport | p50 | p95 | Notes |
|-----------|-----|-----|-------|
| In-memory (`Client(server)`) | **<0.5 ms** | **<1 ms** | FastMCP in-process binding; CI default for unit tests |
| stdio | **<2 ms** | **<5 ms** | Default for local CLI integration tests |
| streamable-HTTP | **<20 ms** | **<50 ms** | Default for deployed-server validation |
| SSE | (deprecated — emit warning, do not enforce) | — | Spec-deprecated since MCP 0.4 |

Budgets cover *transport+framing only*. Server-side tool execution is measured separately by `Tool Latency Should Be Below` (§3.2), which in turn feeds the per-keyword Tier-1 budget (the assertion itself is Tier 1; the *tool* it asserts on can be arbitrarily slow). `[ASSUMPTION → exp_01]`: streamable-HTTP p95 in CI runners depends heavily on loopback NIC behavior — confirm on GitHub-hosted runners.

---

## 3. End-to-End Skill Grading Latency

Single-skill grading run = N reps × (model call + scoring assertion + JSONL parse). Defaults are derived from Inspect AI's `Task` cost-accounting model.

| Configuration | N (reps) | Judge tier | Wall-clock target | p95 ceiling |
|---------------|----------|------------|-------------------|-------------|
| **Fast preflight** | 3 | Tier 1 only (no judge) | **≤15 s** | 30 s |
| **Default CI** | 10 | Tier 2 (Haiku judge) | **≤1 min** | 90 s |
| **Nightly canary** | 30 | Tier 3 (Sonnet judge) | **≤5 min** | 8 min |
| **Calibration** | 100 | Tier 3 (Opus judge) | ≤30 min | 45 min |

Math (default CI): `10 reps × (3 s subject + 0.5 s Haiku judge + <1 ms parse) ≈ 35 s sequential`, padded to 60 s for client setup, retries, and OTel export. Parallelizable to ~12 s with `asyncio.gather`. `[ASSUMPTION → exp_05]`: confirm `LiteLLM` async concurrency does not trigger per-key rate limits on Anthropic for ≥10 in-flight requests.

---

## 4. Cost Ceilings (per skill, N=10 reps)

Anthropic pricing as published Apr 2026 (USD per 1M tokens):

| Model | Input | Output | Source |
|-------|-------|--------|--------|
| claude-haiku-4 | $0.80 | $4.00 | anthropic.com/pricing 2026-04 |
| claude-sonnet-4-5 | $3.00 | $15.00 | anthropic.com/pricing 2026-04 |
| claude-opus-4-7 | $15.00 | $75.00 | anthropic.com/pricing 2026-04 |

Working assumption per rep (skill grading, mean over BFCL+#42796 mix): **2,000 input tokens, 500 output tokens** for the *judge call*. Subject-model cost is not counted here — it is attributed to the system-under-test, not the harness. `[ASSUMPTION → exp_02]`: confirm token-mix average across 30 reference skills.

| Tier | Per rep | Per skill (N=10) | Per 30-skill suite |
|------|---------|------------------|--------------------|
| **1** (WASM, no LLM) | $0.0000 | **$0.00** | $0.00 |
| **2** (Haiku) | $0.0034 | **≤ $0.10** ✓ (matches CLAUDE.md ADR-026 Tier-2 economics: $0.0002/call ×10 × ~5 judge calls/skill) | ≤$3.00 |
| **3** (Sonnet) | $0.0135 | **≤ $1.50** | ≤$45.00 |
| **3** (Opus) | $0.0675 | **≤ $7.50** | ≤$225.00 |

CI gate: budgets are enforced via the `Token Cost Should Be Below` keyword (§3.2). A run that exceeds **150%** of the per-skill ceiling fails the suite. The 30-skill projection is the canonical number stored in RuFlo memory under `perf_cost_projection_30skills`.

---

## 5. Robot Framework Startup Overhead

| Phase | Budget | Notes |
|-------|--------|-------|
| `Library AgentTest` import | **<1.0 s** | Lazy-load LiteLLM + FastMCP; defer scipy until `Stats` keywords used |
| `Suite Setup` (default) | **<2.0 s total** including library import | ONNX model warmup MUST be lazy; counts only if user opts in |
| First Tier-1 keyword call after import | **<10 ms** | No additional warmup beyond import |
| First Tier-2 keyword call after import | **<1.5 s** | Includes LiteLLM client cold-connect |

`[ASSUMPTION → exp_04]`: scipy import alone is ~300 ms; if it leaks into the import path the budget breaks. Validate via `python -X importtime`.

---

## 6. OpenTelemetry Export Overhead

| Mode | Overhead vs. no-OTel baseline | Behavior |
|------|-------------------------------|----------|
| Disabled | 0% | `telemetry=False` library kwarg |
| BatchSpanProcessor (default) | **≤5%** of test wall-clock | `OTEL_BSP_SCHEDULE_DELAY=5000ms`, batch=512 |
| SimpleSpanProcessor | up to 30% (debug only) | Forbidden in CI; emit deprecation warning |

Source: `mcp-eval` README documents OTel as default-on with negligible overhead at batch settings. `[ASSUMPTION → exp_06]`: re-measure with the custom `OTelListener` injecting per-keyword spans.

---

## 7. Memory Footprint Cap

| Component | Cap (per project) | Notes |
|-----------|-------------------|-------|
| HNSW index (sessions × #42796 metrics) | **≤350 MB** RSS | Quantized int8 vectors per memory-specialist plan |
| ONNX embeddings model (`all-MiniLM-L6-v2`) | **≤120 MB** RSS | Loaded once per process, shared across keywords |
| LiteLLM + transports + scipy | **≤30 MB** RSS | Excludes interpreter base |
| **TOTAL (project-level cap)** | **≤500 MB** | CI gate via `psutil` poll in `Suite Teardown` |

Above 500 MB the suite emits a `Memory Footprint Should Be Below` failure (Tier-1 keyword). For very large baselines (>10K stored sessions) the cap rises linearly with a documented opt-in. `[ASSUMPTION → exp_07]`: confirm HNSW + int8 quantization actually fits in 350 MB at 10K vectors × 384 dims.

---

## 8. Budget Enforcement & Reporting

- Every numeric budget above is asserted by a Tier-1 keyword, named `<Metric> Should Be Below`. Violations fail the suite.
- The `OTelListener` writes a per-suite `budgets.json` summarizing actual vs. budget for the HTML report.
- Nightly canary compares against the `baselines/` snapshot using Mann-Whitney U + Cliff's δ (§3.4) so that *trends* are flagged before any single run breaches a hard budget.
- All `[ASSUMPTION → exp_NN]` markers above MUST be cleared before Phase-1 GA.
