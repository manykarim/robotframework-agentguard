# Tier Routing — Per-Keyword Decision Table

> **Authoritative source** for ADR-019 (3-tier routing). Maps every canonical keyword in `docs/research/research.md` §3 to a tier per CLAUDE.md ADR-026.
>
> **Routing mechanism.** At runtime a feature-extraction step (cheap, Tier-1 itself) computes a complexity score s ∈ [0, 1]. The score is fed to the `hooks_route` MCP tool which returns `tier ∈ {1, 2, 3}` and a chosen handler/model. Per-test `tier=` keyword arg overrides the router with a hard pin. The router never *upgrades* across the Tier-2 → Tier-3 boundary without an explicit `allow_escalate=True` because that is where the cost cliff is.
>
> **Default models** (overridable via `Library AgentTest model=…`):
> - Tier 1: WASM/pure-Python (no model)
> - Tier 2: `anthropic/claude-haiku-4`
> - Tier 3 economy: `anthropic/claude-sonnet-4-5`
> - Tier 3 deep: `anthropic/claude-opus-4-7`

---

## 1. Tier Cost/Latency Recap (CLAUDE.md ADR-026)

| Tier | Latency (p50 / p95) | Cost / call (typical 2K-in / 500-out) | Provider |
|------|---------------------|----------------------------------------|----------|
| **1** | <1 ms / <1 ms | **$0** | None — local execution |
| **2** | ~500 ms / ≤900 ms | **$0.0002** ($0.0034 at 2K-in / 500-out) | Haiku via LiteLLM |
| **3** | 2-5 s / ≤8 s | **$0.003 (Sonnet) / $0.015 (Opus)** ($0.0135 / $0.0675 at 2K-in / 500-out) | Sonnet/Opus via LiteLLM |

The "$0.0002 / call" figure in CLAUDE.md is the *minimum* for a small Haiku call (≤200 tokens round-trip). `budgets.md §4` uses the realistic 2K-in / 500-out mix; both numbers are correct in their own context — the router uses the realistic number for cost-projection math.

---

## 2. Per-Keyword Tier Mapping

### 2.1 Tool-Call Correctness — Research §3.1 (BFCL-derived)

| Keyword | Tier | Handler | Rationale |
|---------|------|---------|-----------|
| `Tool Call Should Match Name` | **1** | string compare | Pure equality |
| `Tool Call Arguments Should Match` | **1** | AST diff (BFCL port) | Deterministic AST equality, no LLM needed |
| `Required Parameters Should Be Present` | **1** | JSON Schema validator | Schema validation only |
| `Parallel Tool Calls Should Match` | **1** | multiset compare | Pure set equality |
| `Tool Sequence Should Match` | **1** | ordered subsequence + wildcards | Pattern match |
| `Should Not Call Any Tool` | **1** | length check on trajectory | Trivial |
| `BFCL Score Should Be Above` | **1** | aggregate of above | All inputs Tier-1 |

### 2.2 Tool-Execution & Outcome — Research §3.2

| Keyword | Tier | Handler | Rationale |
|---------|------|---------|-----------|
| `Tool Execution Success Rate Should Be Above` | **1** | counter | Pure stats |
| `Tool Output Should Match Schema` | **1** | JSON Schema | Schema only |
| `Tool Output Should Be Semantically Equal` (short, ≤500 tok) | **2** | Haiku judge | Simple semantic similarity |
| `Tool Output Should Be Semantically Equal` (long, >500 tok) | **3** | Sonnet judge | Long-context comprehension |
| `Tool Latency Should Be Below` | **1** | OTel timer compare | Numeric assertion |
| `Token Cost Should Be Below` | **1** | LiteLLM cost ledger compare | Numeric assertion |

### 2.3 Behavioral / #42796 Catalog — Research §3.3

All 11 metric calculators are pure session-JSONL transforms. Tier 1 across the board.

| Keyword | Tier | Handler |
|---------|------|---------|
| `Read Edit Ratio Should Be Above` | **1** | counter |
| `Edits Without Prior Read Percent Should Be Below` | **1** | set-membership over read history |
| `Reasoning Loops Per 1K Tool Calls Should Be Below` | **1** | regex token scan |
| `User Interrupts Per 1K Should Be Below` | **1** | event filter |
| `Stop Hook Violations Should Be Zero` | **1** | regex over hook events |
| `Convention Violation Rate Should Be Below` | **1** | regex/AST against project CLAUDE.md rules |
| `First Run Test Pass Rate Should Be Above` | **1** | parse pytest/RF output |
| `Token Usage Per Prompt Should Be Below` | **1** | usage ledger compare |
| `Self Admitted Errors Per 1K Should Be Below` | **1** | regex |
| `Write Mutation Ratio Should Be Below` | **1** | counter |
| `"Simplest" Word Frequency Should Be Below` | **1** | n-gram count |

### 2.4 Statistical / Non-Determinism — Research §3.4

| Keyword | Tier | Handler | Rationale |
|---------|------|---------|-----------|
| `Run N Times` | **1** | iteration helper (no model) | Loop construct |
| `Pass At K Should Be Above` | **1** | scipy/numpy | Pure stats |
| `Total Agreement Rate Should Be Above` | **1** | hash compare | Pure stats |
| `Mann Whitney U Should Show Improvement` | **1** | scipy.stats | Pure stats |
| `Cliffs Delta Should Be At Least` | **1** | numpy | Pure stats |
| `Bootstrap Confidence Interval Should Contain` | **1** | numpy resample | Pure stats |
| `LLM Judge Should Score At Least` (1 criterion, short rubric) | **2** | Haiku | Single-axis classification |
| `LLM Judge Should Score At Least` (multi-criterion, full rubric) | **3** | Sonnet (default) / Opus (calibration) | Multi-axis with rationale capture |
| `Calibrate Judge` | **3** | Opus | One-shot, accuracy-critical, infrequent |

### 2.5 MCP / Hook / SubAgent Keywords (research §6 examples)

| Keyword | Tier | Handler | Rationale |
|---------|------|---------|-----------|
| `Get MCP Capabilities`, `List MCP Tools`, `Call MCP Tool` | **1** | FastMCP client | Pure protocol I/O — *transport latency* governed by `budgets.md §2`, not tier cost |
| `Hook Should Block`, `Hook Should Allow`, `Hook Decision Should Be` | **1** | exit-code + JSON parse | Deterministic |
| `Hook Should Be Reasonable` (semantic plausibility check) | **2** | Haiku | Single-criterion plausibility judge |
| `Send Task` (A2A), `Wait For Task Completion`, `Get Task Artifact` | **1** | A2A protocol I/O | Pure protocol |
| `plan_is_efficient` (mcp-eval) | **3** | Sonnet | Multi-step trajectory reasoning |

---

## 3. Routing Algorithm

```
score = 0.4 * (criteria_count > 1)        # multi-criterion → Tier 3
      + 0.2 * (rubric_len_tokens > 200)   # long rubric → upgrade
      + 0.2 * (subject_output_tokens > 500)
      + 0.2 * (requires_rationale)        # judge must explain its score
```

| Score range | Tier |
|-------------|------|
| s == 0 (pure deterministic) | 1 |
| 0 < s < 0.30 | 2 (Haiku) |
| 0.30 ≤ s < 0.70 | 3 (Sonnet) |
| s ≥ 0.70 OR `tier=opus` override | 3 (Opus) |

Threshold values come straight from CLAUDE.md ADR-026's "low complexity (<30%)" boundary. `[ASSUMPTION → exp_08]`: validate the score → tier mapping against a 200-skill-judgment human-labeled set; recalibrate weights if Cohen's κ vs. human < 0.7.

---

## 4. Per-Test Override

```robotframework
LLM Judge Should Score At Least
...    rubric=eval/browser_rubric.md
...    threshold=0.85
...    tier=opus              # hard pin — bypass router
...    allow_escalate=False   # forbid router from going Tier-2 → Tier-3
```

The override is intentional friction: cost-sensitive teams pin to `tier=haiku`; safety-critical evaluations pin to `tier=opus`. Default behavior is *router-decided* with `allow_escalate=False` to keep the cost ceiling predictable.

---

## 5. Routing Telemetry

The router emits an OTel span per decision (`agentguard.route`) with attributes `score`, `chosen_tier`, `chosen_model`, `escalated`, and `cost_estimate_usd`. The HTML report aggregates a "tier mix" pie chart per suite — operationally the most useful debugging artifact when cost surprises a team.

---

## 6. What is *Never* Tier-2 or Tier-3

To prevent silent cost regressions, the following classes are hard-pinned to Tier 1 and the router refuses to upgrade them even with `allow_escalate=True`:

- All `* Should Be Below`, `* Should Be Above`, `* Should Match Schema` numeric/structural assertions.
- All BFCL AST matchers.
- All 11 #42796 metric calculators.
- All scipy stats keywords (`Mann Whitney U`, `Cliffs Delta`, `Bootstrap CI`, `pass@k`, `TAR*`).

If a test wants LLM judgment of a metric, it calls `LLM Judge Should Score At Least` *separately* — the metric calculator itself is sacrosanct.
