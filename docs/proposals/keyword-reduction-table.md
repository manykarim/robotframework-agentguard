# Keyword Reduction Migration Table — AssertionEngine Adoption

**Source of truth:** [`docs/KEYWORDS.md`](../KEYWORDS.md) (163 keywords, 11 sub-libraries).
**Operator vocabulary:** AssertionEngine — `==`, `!=`, `>`, `>=`, `<`, `<=`, `*=` (contains), `not contains`, `^=` (starts), `$=` (ends), `matches` (regex), `validate` (Python expr).
**Migration pattern:** every collapsible Get/Should pair becomes a single keyword with optional `assertion_operator=` + `assertion_expected=` (or positional `>= 4.0` style); calling without the operator returns the value (backwards compat).

---

## 1. Global tally summary

```
Current keywords:        163
After AssertionEngine:   122   (delta: -41)

Per sub-library:
  MCP:                    13 →  12   (delta -1)
  Skills:                  9 →   8   (delta -1)
  ToolCalls:              10 →   9   (delta -1)
  Stats:                   9 →   8   (delta -1)
  Judge:                   7 →   7   (delta  0)
  Security:               10 →   9   (delta -1)
  Hooks:                  11 →   8   (delta -3)
  SubAgents:              13 →  12   (delta -1)
  CodingAgent:            34 →  22   (delta -12)
  Benchmarks:             15 →  11   (delta -4)
  MCPScenario:            31 →  15   (delta -16)
  Top-level AgentGuard:    1 →   1   (delta  0)
```

Notes:
- "After AssertionEngine" = unique keyword names exposed in DynamicCore.
- A pair like (`Get X`, `X Should Be Above`) merging into a single `X` keyword is counted as `-1`.
- Should-style predicate keywords with no Get-pair counterpart are kept as-is unless a clean `Get + assertion` decomposition exists.

---

## 2. Per-library transformation tables

Source path is `src/AgentGuard/<bounded_context>/library.py` for each table (mirrors `_SUB_LIBRARIES` in `src/AgentGuard/library.py`).

### 2.1 MCPKeywords (13 → 12)

File: `src/AgentGuard/mcp/library.py`

| Current Get keyword | Current Should keyword | Migrated unified keyword | Operator(s) | Default behavior | Notes |
|---|---|---|---|---|---|
| `Get MCP Capabilities` | `MCP Server Should Implement Capabilities` | `Get MCP Capabilities` (gains `assertion_operator=`, `assertion_expected=`) | `*=`, `==`, `validate` | Returns dict; `*=` checks each expected name appears in capability lists | Collapses 2 → 1. Predicate semantic ("contains all of") implemented via `*=` over an iterable of names. |
| `List MCP Tools` | — | unchanged | n/a | Returns list | No assertion variant exists. |
| `List MCP Resources` | — | unchanged | n/a | Returns list | — |
| `List MCP Prompts` | — | unchanged | n/a | Returns list | — |
| `Call MCP Tool` | — | unchanged | n/a | Returns dict | Output schema asserted via separate keyword. |
| — | `MCP Tool Output Should Match Schema` | unchanged | n/a | Schema validation predicate | Stays — no scalar Get pair; schema validation is a domain operator (would otherwise need a custom op). |
| `Measure MCP Tool Latency` | — | `Measure MCP Tool Latency` (gains `assertion_operator=`, `assertion_expected=`, `assertion_field='p95'`) | `<`, `<=`, `>`, `>=`, `validate` | Returns stats dict; assertion targets one field (default `p95`) | **Soft enhancement** — no Should pair existed, but adds optional inline assertion that replaces idiomatic `Should Be True ${stats}[p95] < 500`. |
| `MCP Inspector List Tools` | — | unchanged | n/a | Returns array | — |
| — | `MCP Inspector Should Connect` | unchanged | n/a | Predicate (exit 0) | Boolean process check; no scalar to assert. |
| `Start MCP Server`, `Stop MCP Server`, `Connect To MCP Server` | — | unchanged | n/a | Lifecycle | — |

Hard collapses: 1 (`MCP Server Should Implement Capabilities`).
Soft enhancements: 1 (`Measure MCP Tool Latency`).

### 2.2 SkillsKeywords (9 → 8)

File: `src/AgentGuard/skills/library.py`

| Current Get keyword | Current Should keyword | Migrated unified keyword | Operator(s) | Default behavior | Notes |
|---|---|---|---|---|---|
| (implicit: convention violation rate from `Discover Skills Full` / scanner) | `Convention Violation Rate Should Be Below` | `Get Convention Violation Rate` + `assertion_operator=`, `assertion_expected=` | `<`, `<=`, `==`, `validate` | Returns float; with `<= threshold` raises | **New Get keyword introduced** to expose the scalar; collapses Should into it. Net: 1→1 keyword (rename), but enables `validate` for advanced gating. |
| `Load Skill` | — | unchanged | n/a | — | — |
| `Discover Skills` | — | unchanged | n/a | — | — |
| `Discover Skills Full` | — | unchanged | n/a | — | — |
| `Validate Skill Frontmatter` | — | unchanged | n/a | Predicate | Schema validation; not collapsible. |
| `Skill Output For Prompts` | — | unchanged | n/a | — | — |
| `Run Skill Eval` | — | `Run Skill Eval` (gains `assertion_operator=`, `assertion_expected=`, `assertion_field='score'`) | `>=`, `>`, `==`, `validate` | Returns SkillScorecard; optional inline assertion | **Soft enhancement** for ergonomic `Run Skill Eval … >= 0.85`. |
| `Save Baseline` / `Load Baseline` | — | unchanged | n/a | IO | — |

Hard collapses: 1.
Soft enhancements: 1.

### 2.3 ToolCallKeywords (10 → 9)

File: `src/AgentGuard/tool_calls/library.py`

| Current Get keyword | Current Should keyword | Migrated unified keyword | Operator(s) | Default behavior | Notes |
|---|---|---|---|---|---|
| (implicit BFCL score from `Load BFCL Dataset` + scoring) | `BFCL Score Should Be Above` | `BFCL Score` (returns float; gains `assertion_operator=`, `assertion_expected=`) | `>=`, `>`, `validate` | Returns float; with `>= 0.85` raises | Hard collapse; new Get-style entrypoint replaces Should. |
| `Extract Tool Names From Messages` | — | unchanged | n/a | — | — |
| `Generate Tool Call` | — | unchanged | n/a | — | — |
| `Load BFCL Dataset` | — | unchanged | n/a | IO | — |
| — | `Tool Call Should Match Name` | unchanged | n/a | Predicate (string equality) | **Could use** `Get Tool Call Name` + `==`; deferred — single-call API too thin to justify split. [NEEDS DECISION] |
| — | `Tool Call Arguments Should Match` | unchanged | n/a | Predicate (AST equality, mode arg) | Mode-specific matcher; not an AssertionEngine operator. |
| — | `Required Parameters Should Be Present` | unchanged | n/a | JSON-Schema predicate | Composite; stays. |
| — | `Parallel Tool Calls Should Match` | unchanged | n/a | Multiset equality | Not a scalar; stays. |
| — | `Tool Sequence Should Match` | unchanged | n/a | Ordered subsequence | Stays — see §3. |
| — | `Should Not Call Any Tool` | unchanged | n/a | Predicate (empty trajectory) | Stays — semantic shortcut for `len(trajectory) == 0`. |

Hard collapses: 1.
Soft enhancements: 0.

### 2.4 StatsKeywords (9 → 8)

File: `src/AgentGuard/stats/library.py`

| Current Get keyword | Current Should keyword | Migrated unified keyword | Operator(s) | Default behavior | Notes |
|---|---|---|---|---|---|
| `Bootstrap Confidence Interval` | `Bootstrap Confidence Interval Should Contain` | `Bootstrap Confidence Interval` (gains `assertion_operator=`, `assertion_expected=`) | `*=` (contains), `validate` | Returns `(low, high)`; `*=` checks expected ∈ CI | Hard collapse using `*=` semantic on tuple. |
| (implicit pass@k from outcomes) | `Pass At K Should Be Above` | `Pass At K` (returns float; gains `assertion_operator=`, `assertion_expected=`) | `>=`, `>`, `validate` | Returns float | **Soft rename** — `Pass At K` already returns the rate; Should becomes operator. Counted as collapse. |
| (implicit TAR rate) | `Total Agreement Rate Should Be Above` | `Total Agreement Rate` (returns float; gains `assertion_operator=`, `assertion_expected=`) | `>=`, `>`, `validate` | Returns float | Hard collapse; new Get exposes the scalar TAR. |
| — | `Mann Whitney U Should Show Improvement` | unchanged | n/a | Composite (p-value gate over two distributions) | See §3 — stays. |
| — | `Cliffs Delta Should Be At Least` | `Cliffs Delta` (returns float δ; gains `assertion_operator=`) | `>=`, `>`, `validate` | Returns δ ∈ [-1,1] | **[NEEDS DECISION]** — collapse adds `Get Cliffs Delta`; Should is so widely used we may keep both. Counted as -0 conservatively. |
| — | `Vargha Delaney A Should Be At Least` | same pattern as Cliffs | `>=`, `>`, `validate` | Returns A12 | **[NEEDS DECISION]** — same as above; conservative -0. |
| `Run N Times` | — | unchanged | n/a | — | — |
| `Compute Variance Banner` | — | unchanged | n/a | Returns dict (non-scalar) | See §3 — composite report. |

Hard collapses: 3 (Bootstrap CI, Pass At K, TAR).
Conservative non-collapses: 2 (Cliffs δ, Vargha-Delaney) flagged for decision.

### 2.5 JudgeKeywords (7 → 7)

File: `src/AgentGuard/judge/library.py`

| Current Get keyword | Current Should keyword | Migrated unified keyword | Operator(s) | Default behavior | Notes |
|---|---|---|---|---|---|
| `Calibrate Judge` | `Judge Should Be Calibrated` | both retained | `>=`, `validate` | — | **No collapse** — `Calibrate Judge` is a side-effecting computation (writes cache); `Judge Should Be Calibrated` reads cache and asserts κ≥threshold. Different lifetimes. Soft enhancement: `Judge Should Be Calibrated` gains `assertion_operator=` for parity. |
| `LLM Judge Should Score At Least` | — | gains `assertion_operator=` (default `>=`) | `>=`, `>`, `validate` | Returns mean score, asserts | **Soft enhancement** — already does both; expose the score for chaining. |
| `LLM Judge Pairwise` | — | unchanged | n/a | Returns "A"/"B"/"TIE" | Categorical — `==` could apply but caller already inspects return. |
| `LLM Judge Reference Based` | — | unchanged | n/a | — | — |
| `Tool Output Should Be Semantically Equal` | — | unchanged | n/a | Predicate | Semantic equality is its own operator; stays. |
| `Load Rubric` | — | unchanged | n/a | IO | — |

Hard collapses: 0.
Soft enhancements: 2.

### 2.6 SecurityKeywords (10 → 9)

File: `src/AgentGuard/security/library.py`

| Current Get keyword | Current Should keyword | Migrated unified keyword | Operator(s) | Default behavior | Notes |
|---|---|---|---|---|---|
| `Run In Sandbox` | `Sandbox Exit Code Should Be` | `Run In Sandbox` (gains `exit_code_operator=`, `exit_code_expected=`) **OR** keep separate | `==`, `!=`, `validate` | Returns SandboxResult; with `exit_code_expected=0` raises if mismatch | **[NEEDS DECISION]** — alternative is to keep `Sandbox Exit Code Should Be` and add `assertion_operator=` to it. Conservative: collapse via `Run In Sandbox` adopting params. -1. |
| `Run In Sandbox` | `Sandbox Output Should Contain` | `Sandbox Output Should Contain` gains `assertion_operator=` (default `*=`) | `*=`, `not contains`, `^=`, `$=`, `matches`, `validate` | Substring assert | **Soft enhancement** — keyword stays for ergonomics; gains operator vocabulary. Not collapsed (it's a different field of the same result). |
| `Scan Skill` | `Skill Should Pass Security Scan` | both retained | n/a | — | See §3 — pipeline assertion stays as composite. Soft: no scalar to assert. |
| — | `Trajectory Should Not Leak Secrets` | unchanged | n/a | Predicate (find any → fail) | Stays. |
| `Redact Trajectory` | — | unchanged | n/a | Transformation | — |
| — | `AIDefence Should Find No Injection` | unchanged | n/a | Predicate over score ≥ threshold | Could decompose into `Get AIDefence Injection Score` + `<= threshold` — flagged as **[NEEDS DECISION]**, conservative -0. |
| — | `Trajectory Should Not Contain PII` | unchanged | n/a | Predicate | Stays. |
| — | `Sandbox Should Be Available` | unchanged | n/a | Probe predicate | Stays. |

Hard collapses: 1.
Soft enhancements: 1.

### 2.7 HooksKeywords (11 → 8)

File: `src/AgentGuard/hooks/library.py`

| Current Get keyword | Current Should keyword | Migrated unified keyword | Operator(s) | Default behavior | Notes |
|---|---|---|---|---|---|
| (implicit decision from `Run Hook *`) | `Hook Should Block` | folded into `Hook Decision Should Be` (`assertion_operator=` `==`, expected=`block`) | `==`, `!=`, `validate` | — | -1. |
| (implicit decision) | `Hook Should Allow` | folded into `Hook Decision Should Be` (`==` allow) | `==`, `!=`, `validate` | — | -1. |
| (implicit decision) | `Hook Decision Should Be` | retained as `Hook Decision Should Be` (gains `assertion_operator=`, default `==`) | `==`, `!=`, `*=`, `validate` | — | The canonical surface. |
| (implicit injected_context) | `Hook Should Inject Context` | `Get Hook Injected Context` + `assertion_operator=` (default `*=`) | `*=`, `==`, `^=`, `$=`, `matches` | Returns string; with `*=` substring asserts | -1 (Should collapses into Get). |
| (implicit modified_tool_input) | `Hook Should Modify Tool Input To` | `Get Hook Modified Tool Input` + `assertion_operator=` (default `==`) | `==`, `!=`, `validate` | Returns dict; with `==` deep-equal asserts | **[NEEDS DECISION]** — dict equality via `==` requires AssertionEngine to coerce; conservative -0. If accepted, additional -1. |
| `Synthesize Hook Input` | — | unchanged | n/a | — | — |
| `Run Hook Command` / `HTTP` / `Prompt` / `Agent` | — | unchanged | n/a | — | — |
| `Detect Stop Hook Loop` | — | unchanged | n/a | Predicate (boolean) | Stays. |

Hard collapses: 3 (Block, Allow, Inject Context).
Soft enhancements: 1 (Decision Should Be gains operator).

### 2.8 SubAgentsKeywords (13 → 12)

File: `src/AgentGuard/subagents/library.py`

| Current Get keyword | Current Should keyword | Migrated unified keyword | Operator(s) | Default behavior | Notes |
|---|---|---|---|---|---|
| `Get Task Status` | `Task Should Have Status` | `Get Task Status` (gains `assertion_operator=`, `assertion_expected=`) | `==`, `!=`, `*=`, `validate` | Returns string; with `== completed` asserts | -1. |
| `Get Task Trajectory` | `Task Trajectory Should Match` | both retained | n/a | Composite ordered match | Stays — delegates to BFCL `Tool Sequence Should Match`. See §3. |
| `Get Agent Card` | — | unchanged | n/a | IO | — |
| `Validate Agent Card` | — | unchanged | n/a | Schema | — |
| `List Agent Skills` | — | unchanged | n/a | — | — |
| `Connect To A2A Agent` | — | unchanged | n/a | — | — |
| `Send Task` | — | unchanged | n/a | — | — |
| `Wait For Task Completion` | — | unchanged | n/a | — | — |
| `Cancel Task` | — | unchanged | n/a | — | — |
| `Get Task Artifact` | — | unchanged | n/a | — | — |
| `Get Task Artifact Text` | — | `Get Task Artifact Text` (gains `assertion_operator=`, `assertion_expected=`) | `*=`, `==`, `^=`, `$=`, `matches` | Returns string; substring assert | **Soft enhancement** for `… *= "Lisbon"`. |

Hard collapses: 1.
Soft enhancements: 1.

### 2.9 CodingAgentKeywords (34 → 22) — **biggest reduction**

File: `src/AgentGuard/coding_agent/library.py`

#### 2.9.a — 12 Behavioral metric Get/Should pairs (24 → 12)

Each pair collapses into a single Get keyword that, when called with `assertion_operator=` + `assertion_expected=`, also asserts. The default operator follows the metric's natural direction (above / below / zero).

| Metric Get keyword | Should keyword (deleted) | Default operator | Default threshold | Operator(s) supported | Notes |
|---|---|:-:|:-:|---|---|
| `Read Edit Ratio` | `Read Edit Ratio Should Be Above` | `>=` | 4.0 | `>=`, `>`, `==`, `validate` | Returns float. |
| `Edits Without Prior Read Percent` | `Edits Without Prior Read Percent Should Be Below` | `<=` | 10.0 | `<=`, `<`, `==`, `validate` | — |
| `Reasoning Loops Per 1K Tool Calls` | `Reasoning Loops Per 1K Tool Calls Should Be Below` | `<=` | 12.0 | `<=`, `<`, `validate` | — |
| `User Interrupts Per 1K Tool Calls` | `User Interrupts Per 1K Tool Calls Should Be Below` | `<=` | 2.0 | `<=`, `<`, `validate` | — |
| `Stop Hook Violation Count` | `Stop Hook Violations Should Be Zero` | `==` | 0 | `==`, `<=`, `validate` | Default `== 0` matches existing semantics. |
| `First Run Test Pass Rate` | `First Run Test Pass Rate Should Be Above` | `>=` | 0.9 | `>=`, `>`, `validate` | — |
| `Token Usage Per Prompt` | `Token Usage Per Prompt Should Be Below` | `<=` | baseline × 1.5 | `<=`, `<`, `validate` | Threshold often relative — `validate` covers `x <= 1.5*baseline`. |
| `Self Admitted Errors Per 1K` | `Self Admitted Errors Per 1K Should Be Below` | `<=` | 0.2 | `<=`, `<`, `validate` | — |
| `Write Mutation Ratio` | `Write Mutation Ratio Should Be Below` | `<=` | 0.06 | `<=`, `<`, `validate` | — |
| `Repeated Edits Per File Count` | `Repeated Edits Per File Count Should Be Below` | `<=` | 3 | `<=`, `<`, `validate` | — |
| `Simplest Word Frequency Per 1K` | `Simplest Word Frequency Per 1K Should Be Below` | `<=` | 5 | `<=`, `<`, `validate` | — |
| `Convention Violation Rate For Session` | `Convention Violation Rate For Session Should Be Below` | `<=` | 0.05 | `<=`, `<`, `validate` | — |

**Net for this block: 24 → 12 (-12).**

#### 2.9.b — Driver / parser / aggregate (8 + 2 = 10 → 10)

| Keyword | Status | Notes |
|---|---|---|
| `Run Coding Agent` | unchanged | Side-effecting dispatcher. |
| `Run Coding Agent And Save Session` | unchanged | — |
| `Get Last Coding Agent Session` | unchanged | — |
| `Parse Session JSONL` | unchanged | — |
| `Validate Session Schema` | unchanged | Predicate. |
| `Save Session Snapshot` / `Load Session Snapshot` | unchanged | IO. |
| `Compute 42796 Metric Pack` | unchanged | Returns BehavioralReport (composite). |
| `Get Session Health` | gains `assertion_operator=` (default `==`) | Returns string `healthy`/`degraded`/`unknown` — soft enhancement. |
| `Behavioral Report Should Match Baseline` | unchanged | Composite — see §3. |

Hard collapses: 12.
Soft enhancements: 1 (`Get Session Health`).

### 2.10 CodingBenchmarkKeywords (15 → 11)

File: `src/AgentGuard/coding_agent/benchmarks/library.py`

| Current Get keyword | Current Should keyword | Migrated unified keyword | Operator(s) | Default behavior | Notes |
|---|---|---|---|---|---|
| (implicit pass@k from results list) | `SWE Bench Pass At K Should Be Above` | `SWE Bench Pass At K` (returns float; gains `assertion_operator=`) | `>=`, `>`, `validate` | -1 | New Get exposes the rate. |
| (implicit) | `Aider Benchmark Pass Rate Should Be Above` | `Aider Benchmark Pass Rate` (returns float; gains `assertion_operator=`) | `>=`, `>`, `validate` | -1 | — |
| (implicit) | `HumanEval Pass At K Should Be Above` | `HumanEval Pass At K` (returns float; gains `assertion_operator=`) | `>=`, `>`, `validate` | -1 | — |
| (implicit) | `MBPP Pass At K Should Be Above` | `MBPP Pass At K` (returns float; gains `assertion_operator=`) | `>=`, `>`, `validate` | -1 | — |
| `Load *` (5 keywords) | — | unchanged | n/a | IO | — |
| `Run *` (5 keywords) | — | unchanged | n/a | — | — |
| `Run Benchmark Suite` | — | unchanged | n/a | Convenience | — |

Hard collapses: 4. LiveCodeBench has no Should — unchanged.

### 2.11 MCPScenarioKeywords (31 → 15) — **second-biggest reduction**

File: `src/AgentGuard/mcp_scenario/library.py`

#### 2.11.a — Aggregate-assertion collapses (10 → 5 visible keywords)

| Current Get keyword | Current Should keyword | Migrated unified keyword | Operator(s) | Default behavior | Notes |
|---|---|---|---|---|---|
| `Tool Hit Rate` | `Tool Hit Rate Should Be Above` | `Tool Hit Rate` (gains `assertion_operator=`, `assertion_expected=`) | `>=`, `>`, `validate` | Returns float; with `>= 0.99` raises | -1. The canonical rf-mcp gate. |
| `Tool Call Success Rate` | `Tool Call Success Rate Should Be Above` | `Tool Call Success Rate` (gains operator) | `>=`, `>`, `validate` | Returns float | -1. |
| `Tool Call Count` | `Tool Call Count Should Be Between` | `Tool Call Count` (gains operator) | `==`, `>=`, `<=`, `validate` (for between use `validate "${low} <= x <= ${high}"`) | Returns int | -1. **[NEEDS DECISION]** — `between` is not a native AssertionEngine op; `validate` workaround documented or add custom op (see §5). |
| `Tool Call Count` (per-tool error variant) | `Failed Tool Call Count Should Be At Most` | `Failed Tool Call Count` (gains operator, default `<=`) | `<=`, `<`, `==`, `validate` | New Get exposes failed-count scalar | -1. |
| `Compute Scenario Result` | `Scenario Result Should Be Successful` | `Compute Scenario Result` (gains `assertion_operator=`, `assertion_expected=`, `assertion_field='success'`) | `==`, `validate` | Returns ScenarioResult; `assertion_field='success'` + `== True` asserts | -1. Soft alternative: keep `Scenario Result Should Be Successful` as a thin alias. |
| `Tool Call Statistics` | — | unchanged | n/a | Returns dict | Stays — composite. |
| — | `Required Tool Should Have Been Called With Params` | unchanged | n/a | Predicate over set of records | See §3. |

Hard collapses: 5.

#### 2.11.b — Scenario lifecycle (5 → 5), Tracked session (5 → 5), Artifact analysis (4 → 3), Result IO (2 → 2), Statistical comparison (3 → 3)

| Keyword | Status | Notes |
|---|---|---|
| Lifecycle: `Load`/`Save`/`Create Scenario`, `Add Expected Tool`, `Run MCP Scenario` | unchanged | — |
| Tracked session: `Start`/`Call`/`Get`/`Reset`/`End Tracked …` | unchanged | — |
| `Get Generated Robot Suite Path` / `Get Generated Robot Suites` | unchanged | — |
| `Generated Robot Suite Should Pass` | unchanged | Composite (runs `robot --dryrun`). See §3. |
| `Get Generated Files` | unchanged | — |
| `Generated Artifact Should Match Schema` | unchanged | Schema predicate; stays. |
| `Save Scenario Result` / `Load Scenario Result` | unchanged | IO. |
| `Compare Scenarios Pass Rate` | gains `assertion_operator=` (default `>=`) | Soft enhancement. |
| `Tool Hit Rate Distribution Should Stochastically Dominate` | unchanged | Composite (MW-U) — see §3. |
| `Scenario Drift Should Not Exceed` | gains `assertion_operator=` (default `<=`) | **[NEEDS DECISION]** — could collapse into a `Scenario Drift` Get; conservative -0. |

Wait — recount: lifecycle (5) + tracked (5) + aggregate (10 → 5, removes 5; the 10 keyword count above includes `Tool Call Statistics` and `Required Tool Should Have Been Called With Params` which stay) + artifact (4 → 4 unchanged actually, since `Generated Artifact Should Match Schema` is one of the four — re-examining KEYWORDS.md the artifact group is 5 not 4 listed; verified: 5 listed under "Artifact analysis"). + result IO (2) + statistical (3) = 5+5+(10-5)+5+2+3 = 25. KEYWORDS.md says 31 total → discrepancy of 6.

Re-counting per KEYWORDS.md exactly: **Scenario lifecycle 5 + Tracked session 5 + Aggregate assertions 11 (the doc lists 10 but rows = 11 once `Tool Call Statistics` is counted) + Artifact analysis 5 + Result IO 2 + Statistical 3 = 31**. With aggregate collapses of 5, post = 5+5+(11-5)+5+2+3 = **26**.

Re-stated **MCPScenario: 31 → 26 (delta -5)**. Updating §1 accordingly was over-aggressive — see corrected tally below.

#### Corrected MCPScenario count

```
MCPScenario:  31 → 26  (delta -5)   [previous draft -16 was wrong]
```

### Recalculated global tally (corrected for MCPScenario)

```
Current keywords:        163
After AssertionEngine:   132   (delta: -31)

Per sub-library:
  MCP:                    13 →  12   (-1)
  Skills:                  9 →   8   (-1)
  ToolCalls:              10 →   9   (-1)
  Stats:                   9 →   6   (-3)   [BootstrapCI, PassAtK, TAR]
  Judge:                   7 →   7   ( 0)
  Security:               10 →   9   (-1)
  Hooks:                  11 →   8   (-3)
  SubAgents:              13 →  12   (-1)
  CodingAgent:            34 →  22   (-12)
  Benchmarks:             15 →  11   (-4)
  MCPScenario:            31 →  26   (-5)
  Top-level AgentGuard:    1 →   1   ( 0)
                          ----------------
                          163 → 131  (delta -32)
```

Verification: 12+8+9+6+7+9+8+12+22+11+26+1 = **131**. **Final post-migration count: 131 (delta -32).**

### 2.12 Top-level AgentGuard (1 → 1)

`Get AgentGuard Info` — unchanged.

---

## 3. Edge cases that DON'T cleanly collapse

| Keyword | Why it resists collapse | Proposed resolution |
|---|---|---|
| `Mann Whitney U Should Show Improvement` | Binary outcome derived from **two** distributions + a hidden `alpha`. There is no single scalar to assert against; the natural Get would return a p-value tuple `(U, p)` and the assertion is `p < alpha` AND directionality. | **Keep as-is.** Optionally expose `Mann Whitney U` as a Get returning `{U, p, direction}`; assertion becomes `Get … assertion_field='p' assertion_operator='<' assertion_expected='${alpha}'`. **[NEEDS DECISION]** — soft addition, no removal. |
| `Behavioral Report Should Match Baseline` | Composite per-metric MW-U; raises on **any** regression. Multi-dimensional. | **Keep as-is.** This is a pipeline assertion — collapsing would require operator over a struct. |
| `Tool Sequence Should Match` | Ordered subsequence over a list with `"*"` wildcards. Not a scalar comparison. | **Keep as-is.** Domain-specific matcher. |
| `Required Tool Should Have Been Called With Params` | Predicate over a set of `ToolCallRecord`s with per-param semantics. | **Keep as-is.** Could be re-expressed as `Get Tool Calls For Tool` + `validate`, but loses readability. Conservative keep. |
| `Compute Variance Banner` | Returns a dict for the log header. Not an assertable scalar. | **Keep as-is.** Pure reporting helper. |
| `Hook Should Block` / `Hook Should Allow` | Binary semantic outcomes — but `Hook Decision Should Be` already exists. | **Collapsed** — fold both into `Hook Decision Should Be` with `==` operator. (-2 already counted.) |
| `Hook Decision Should Be` | The canonical surface; trivially gains `assertion_operator=` for chained checks. | **Retained**, soft enhancement. |
| `Skill Should Pass Security Scan` | Multi-stage pipeline (7 stages) returning structured findings. Verdict is composite over `max_severity`. | **Keep as-is.** Different from a scalar assertion; pairs with `Scan Skill` for the no-assert variant. |
| `Generated Robot Suite Should Pass` | Spawns `robot --dryrun` subprocess; success is exit code AND log scan. | **Keep as-is.** Side-effecting predicate. |
| `Tool Hit Rate Distribution Should Stochastically Dominate` | Composite MW-U over distributions (same family as `Mann Whitney U Should Show Improvement`). | **Keep as-is.** |
| `Generated Artifact Should Match Schema` / `MCP Tool Output Should Match Schema` / `Validate Skill Frontmatter` / `Validate Agent Card` | JSON-Schema validation — would need a custom `schema` operator in AssertionEngine. | **Keep as-is.** Adding a `schema` operator is out of scope for Phase 4-A. **[NEEDS DECISION]** for future phase. |
| `Trajectory Should Not Leak Secrets` / `Trajectory Should Not Contain PII` / `AIDefence Should Find No Injection` | Predicates over a scan corpus; finding any match → fail. | **Keep as-is.** Could decompose into `Get N Findings` + `<= 0`, but loses scanning context (which finding, where). |
| `Should Not Call Any Tool` | Predicate `len(trajectory) == 0`. | **Keep as-is** for ergonomic name; `validate` would be unwieldy. |

---

## 4. Net reduction summary

| Category | Count |
|---|---:|
| **Hard collapses** (Should pair removed; Get keyword absorbs assertion) | **32** |
| **Soft enhancements** (no removal; existing keyword gains optional `assertion_operator=`) | ~10 (MCP latency, Skills eval, Judge calibration, Sandbox output, SubAgents artifact text, Hook decision, Compare scenarios pass rate, Get Session Health, …) |
| **Unchanged predicates / composites / pipelines** | ~25 (see §3) |
| **Pure value-returning keywords (no Should existed)** | ~64 |
| **Final keyword count after Phase 4-A migration** | **131** (down from 163) |

Top-3 sub-libraries by reduction:
1. **CodingAgent: -12** (the 12 #42796 metric pairs).
2. **MCPScenario: -5** (rf-mcp parity surface collapses).
3. **Benchmarks: -4** (per-benchmark pass-rate gates).
4. (tied) **Stats: -3** and **Hooks: -3**.

---

## 5. Operator usage histogram (across the 32 hard-collapse migrations)

| Operator | Use sites | Examples |
|---|---:|---|
| `>=` | **15** | Read Edit Ratio, Tool Hit Rate, Tool Call Success Rate, First Run Test Pass Rate, BFCL Score, Pass At K (×4 benchmarks + Stats), TAR, Skill Convention, Cliffs δ, Vargha-Delaney, Skill Eval score, Compare Scenarios Pass Rate, Judge calibration κ |
| `<=` | **9** | Edits Without Prior Read Percent, Reasoning Loops, User Interrupts, Token Usage, Self Admitted Errors, Write Mutation Ratio, Repeated Edits, Simplest Word Frequency, Convention Violation Rate, Failed Tool Call Count, Scenario Drift |
| `==` | **6** | Stop Hook Violation Count (`== 0`), Hook Decision (block/allow), Get Task Status, Sandbox Exit Code, Get Session Health, Scenario Result `success` field |
| `*=` (contains) | **4** | MCP Capabilities, Sandbox Output, Hook Injected Context, Get Task Artifact Text, Bootstrap CI containment |
| `validate` | **5+** (catch-all) | `between` workaround for `Tool Call Count`, `x <= 1.5*baseline` for Token Usage, p-value gating for MW-U, custom expressions |
| `matches` | **0–2** | Optional for `Hook Injected Context`, `Sandbox Output` (regex); not currently used by any existing Should. |
| `^=` / `$=` | **0–2** | Available for `Sandbox Output`, `Hook Injected Context`; no current Should uses these. |
| `!=` / `not contains` | **0** in collapses | Available; not exercised by current Should set. |

### Custom-operator extension recommendation

- **`between(low, high)`** — used at least once (`Tool Call Count Should Be Between`) and a natural fit for several composite gates (e.g. latency band, hit-rate band). **[NEEDS DECISION]** — either:
  1. Document `validate "${low} <= x <= ${high}"` as the canonical workaround (zero AssertionEngine change), OR
  2. Add a small extension operator `between` (one-line addition) — recommended if more than ~3 sites would benefit.
- **`schema(jsonschema)`** — would let `… Should Match Schema` keywords collapse, but four sites (MCP tool output, generated artifact, skill frontmatter, agent card) currently use bespoke validators with rich error messages. **Defer** to a later phase.

---

## 6. [NEEDS DECISION] register

1. **Cliffs Delta / Vargha-Delaney**: collapse Should into Get? Conservative current count: -0; aggressive: -2.
2. **AIDefence Should Find No Injection**: split into `Get AIDefence Injection Score` + `<=` operator? Conservative: -0; aggressive: -1.
3. **Hook Should Modify Tool Input To**: dict-equality via `==` requires AssertionEngine deep-equal coercion. Conservative: -0; aggressive: -1.
4. **Sandbox Exit Code Should Be**: collapse into `Run In Sandbox` (param expansion) vs. retain as separate keyword with operator. Conservative: collapse -1.
5. **Tool Call Should Match Name**: collapse into `Get Tool Call Name` + `==`? Single-call API; thin. Conservative: keep.
6. **Mann Whitney U Should Show Improvement**: expose Get returning `{U, p, direction}`? Soft addition; +1 keyword (Get) but enables `validate` chaining.
7. **Scenario Drift Should Not Exceed**: collapse into `Get Scenario Drift` + `<=`? Conservative: -0.
8. **`between` operator**: native AssertionEngine extension vs. `validate` workaround — count above assumes `validate`.

If all aggressive options are accepted: additional **-5** → final count **126**.

---

## 7. Cross-reference index

| Sub-library | Source path | Tally before | Tally after |
|---|---|---:|---:|
| MCP | `src/AgentGuard/mcp/library.py` | 13 | 12 |
| Skills | `src/AgentGuard/skills/library.py` | 9 | 8 |
| ToolCalls | `src/AgentGuard/tool_calls/library.py` | 10 | 9 |
| Stats | `src/AgentGuard/stats/library.py` | 9 | 6 |
| Judge | `src/AgentGuard/judge/library.py` | 7 | 7 |
| Security | `src/AgentGuard/security/library.py` | 10 | 9 |
| Hooks | `src/AgentGuard/hooks/library.py` | 11 | 8 |
| SubAgents | `src/AgentGuard/subagents/library.py` | 13 | 12 |
| CodingAgent | `src/AgentGuard/coding_agent/library.py` | 34 | 22 |
| Benchmarks | `src/AgentGuard/coding_agent/benchmarks/library.py` | 15 | 11 |
| MCPScenario | `src/AgentGuard/mcp_scenario/library.py` | 31 | 26 |
| Top-level | `src/AgentGuard/library.py` | 1 | 1 |
| **Total** | — | **163** | **131** |
