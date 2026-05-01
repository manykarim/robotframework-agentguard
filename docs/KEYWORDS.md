# AgentGuard Robot Framework Keywords — Complete Reference

**163 keywords** across **11 sub-libraries**, all composed via `DynamicCore` on the top-level
`Library AgentGuard`. Importing `AgentGuard` makes every keyword in this document
available; advanced users can also import a single sub-library directly
(e.g. `Library AgentGuard.mcp.library`) for namespace isolation.

## Index

| Sub-library | Keywords | Bounded context (DDD) | Purpose |
|---|---:|---|---|
| [MCPKeywords](#mcpkeywords-13) | 13 | MCP | Test MCP servers — connect, enumerate, call, validate schema, measure latency. |
| [SkillsKeywords](#skillskeywords-9) | 9 | Skills | Discover, parse, validate, and grade Agent Skills. |
| [ToolCallKeywords](#toolcallkeywords-10) | 10 | ToolCallCorrectness | BFCL-style AST equality + trajectory matching for tool calls. |
| [StatsKeywords](#statskeywords-9) | 9 | Statistics | Mann-Whitney U, Cliff's δ, Vargha-Delaney A, bootstrap CIs, pass@k, TARr@N. |
| [JudgeKeywords](#judgekeywords-7) | 7 | Judge | Classification-based LLM-as-Judge with Cohen's κ calibration. |
| [SecurityKeywords](#securitykeywords-10) | 10 | Security | Default-deny skill scanner, redactor, sandbox dispatch, AIDefence integration. |
| [HooksKeywords](#hookskeywords-11) | 11 | Hooks | Synthesize and drive the 12 Claude Code hook events across 4 handler types. |
| [SubAgentsKeywords](#subagentskeywords-13) | 13 | SubAgents | A2A 1.0 task lifecycle; trajectory comparison; framework bridges. |
| [CodingAgentKeywords](#codingagentkeywords-34) | 34 | CodingAgent + BehavioralMetrics | Drive coding agents (Claude Code, Codex, Aider, …) + the 12 #42796 metrics. |
| [CodingBenchmarkKeywords](#codingbenchmarkkeywords-15) | 15 | CodingAgent | SWE-bench Verified, Aider, HumanEval, MBPP, LiveCodeBench loaders + scorers. |
| [MCPScenarioKeywords](#mcpscenariokeywords-31) | 31 | TestHarness (ADR-021) | Unified scenario harness — drop-in replacement for rf-mcp `tests/e2e/`. |
| [Top-level AgentGuard](#top-level-agentguard-1) | 1 | cross-cutting | Library introspection. |

**Conventions used below**

- Every keyword is a sync facade; async work happens internally via `asyncio.run`.
- Tier-1 (deterministic, no LLM) keywords are marked **T1**; Tier-2/3 (LLM-touching) are marked **T2/3**.
- All assertion keywords raise `AssertionError` so Robot Framework reports them as test failures.
- Default model resolution: `OPENROUTER_API_KEY` from `.env` → `default_model()` from `AgentGuard.config`.

---

## MCPKeywords (13)

`AgentGuard.mcp.library.MCPKeywords` — wrap any MCP server (stdio / SSE / streamable-HTTP / in-memory).

| Keyword | Tier | Purpose |
|---|:-:|---|
| `Start MCP Server` | T1 | Spawn or bind an MCP server; returns a `ServerHandle`. |
| `Stop MCP Server` | T1 | Tear down an owned server; returns child exit code. |
| `Connect To MCP Server` | T1 | Connect to an already-running server; handle does not own its lifetime. |
| `Get MCP Capabilities` | T1 | Returns `{tools, resources, prompts}` (lists of names). |
| `MCP Server Should Implement Capabilities` | T1 | Assert every expected name appears in capabilities. |
| `List MCP Tools` | T1 | Return tool dicts (`name`, `description`, `inputSchema`, `outputSchema`). |
| `List MCP Resources` | T1 | Return resource dicts. |
| `List MCP Prompts` | T1 | Return prompt dicts. |
| `Call MCP Tool` | T1 | Invoke a tool; returns `{data, is_error, structured_content, raw}`. |
| `MCP Tool Output Should Match Schema` | T1 | Validate `result.data` against a JSON Schema (dict, JSON string, or path). |
| `Measure MCP Tool Latency` | T1 | Run N times; return `{runs, mean, p50, p95, p99, min, max}` in ms. |
| `MCP Inspector Should Connect` | T1 | Wrap `npx @modelcontextprotocol/inspector --cli`; assert exit 0. |
| `MCP Inspector List Tools` | T1 | Inspector CLI `--method tools/list`; returns the tools array. |

```robot
${handle}=    Start MCP Server    uv run python my_server.py    transport=stdio
${tools}=    List MCP Tools    ${handle}
Should Be True    len($tools) >= 5
${result}=    Call MCP Tool    ${handle}    add    {"x": 2, "y": 3}
Should Be Equal As Integers    ${result}[data]    5
Stop MCP Server    ${handle}
```

---

## SkillsKeywords (9)

`AgentGuard.skills.library.SkillsKeywords` — discover, parse, validate, and grade Agent Skills (rf-skill-eval pattern).

| Keyword | Tier | Purpose |
|---|:-:|---|
| `Load Skill` | T1 | Parse `SKILL.md` (or skill directory) and validate frontmatter. |
| `Discover Skills` | T1 | Scan the four standard install paths (or custom roots); returns `{tool: [Skill]}`. |
| `Discover Skills Full` | T1 | Same as `Discover Skills` but returns the full `DiscoveryResult` (errors + warnings). |
| `Validate Skill Frontmatter` | T1 | Assert spec compliance (name regex, description, allowed-tools shape). |
| `Skill Output For Prompts` | T2/3 | Drive the configured provider with the skill loaded as system message. |
| `Run Skill Eval` | T2/3 | Wrap an Inspect AI Task; returns `SkillScorecard`. |
| `Convention Violation Rate Should Be Below` | T1 | Run conventions checker; raise if rate ≥ threshold. |
| `Save Baseline` | T1 | Persist a `SkillScorecard` as JSON for later diffing. |
| `Load Baseline` | T1 | Inverse of `Save Baseline`. |

```robot
${skill}=    Load Skill    skills/robotframework-browser-skill
Skill Should Pass Security Scan    ${skill}    allow_unsigned=${True}
${scorecard}=    Run Skill Eval    ${skill}    runs=10    judge_model=openrouter/openai/gpt-4o-mini
Save Baseline    ${scorecard}    baselines/browser-2026-q2.json
```

---

## ToolCallKeywords (10)

`AgentGuard.tool_calls.library.ToolCallKeywords` — BFCL-style per-call AST equality + trajectory matching.

| Keyword | Tier | Purpose |
|---|:-:|---|
| `Tool Call Should Match Name` | T1 | Exact-string assertion on the called tool's name. |
| `Tool Call Arguments Should Match` | T1 | AST equality of arguments; `mode` ∈ `{strict, ast, semantic}`. |
| `Required Parameters Should Be Present` | T1 | Validate `actual.arguments` against a JSON Schema (`required` only). |
| `Parallel Tool Calls Should Match` | T1 | Multiset equality of `(name, args)` over the two lists. |
| `Tool Sequence Should Match` | T1 | Ordered subsequence match; `"*"` matches any single call. |
| `Should Not Call Any Tool` | T1 | BFCL "decide-not-to-act"; assert empty trajectory. |
| `Load BFCL Dataset` | T1 | Load BFCL cases from `inspect_evals.bfcl` (or fixture fallback). |
| `BFCL Score Should Be Above` | T1 | Compute mean per-case score; assert ≥ threshold. |
| `Generate Tool Call` | T2/3 | Call the suite-level provider; return parsed tool calls. |
| `Extract Tool Names From Messages` | T1 | Pull the ordered tool-name list from an assistant transcript. |

```robot
${call}=    Generate Tool Call    Find weather in Lisbon    tools=${TOOLS}
Tool Call Should Match Name    ${call}[0]    weather.lookup
Tool Call Arguments Should Match    ${call}[0]    {"city": "Lisbon"}    mode=ast
```

---

## StatsKeywords (9)

`AgentGuard.stats.library.StatsKeywords` — non-determinism math; default `N≥10` per ADR-005.

| Keyword | Tier | Purpose |
|---|:-:|---|
| `Run N Times` | T1 | Run a keyword N times and collect return values. |
| `Pass At K Should Be Above` | T1 | HumanEval-formula `pass@k(outcomes) > threshold`. |
| `Total Agreement Rate Should Be Above` | T1 | TARr@N (raw) or TARa@N (parsed-answer) over outputs. |
| `Mann Whitney U Should Show Improvement` | T1 | scipy MW-U; assert `p < alpha`. |
| `Cliffs Delta Should Be At Least` | T1 | Effect-size assertion (`δ ∈ [-1, 1]`). |
| `Vargha Delaney A Should Be At Least` | T1 | A12 effect size. |
| `Bootstrap Confidence Interval` | T1 | Returns `(low, high)` for a sample. |
| `Bootstrap Confidence Interval Should Contain` | T1 | Assert expected value ∈ bootstrap CI. |
| `Compute Variance Banner` | T1 | Run-to-run variance summary for the log.html header. |

```robot
${current}=    Run N Times    runs=30    Skill Eval    skill=${SKILL}
${baseline}=   Load Baseline    baselines/2026-q1.json
Mann Whitney U Should Show Improvement    ${current}    ${baseline}    alpha=0.05
Cliffs Delta Should Be At Least           ${current}    ${baseline}    delta=0.2
```

---

## JudgeKeywords (7)

`AgentGuard.judge.library.JudgeKeywords` — classification-based LLM-as-Judge; calibration-gated per ADR-011.

| Keyword | Tier | Purpose |
|---|:-:|---|
| `Load Rubric` | T1 | Load a rubric from `.md` / `.yaml` / dict / Rubric. |
| `LLM Judge Should Score At Least` | T2/3 | Classification judge over N runs; assert mean ≥ threshold. |
| `LLM Judge Pairwise` | T2/3 | Pairwise winner: `"A"` / `"B"` / `"TIE"`. |
| `LLM Judge Reference Based` | T2/3 | Classify each response against its corresponding reference. |
| `Tool Output Should Be Semantically Equal` | T2/3 | Equivalent / partial / not — short-output specialised. |
| `Calibrate Judge` | T2/3 | Run model over labeled set; compute Cohen's κ vs human labels. |
| `Judge Should Be Calibrated` | T1 | Assert cached κ ≥ threshold within expiry. |

```robot
Calibrate Judge    openrouter/openai/gpt-4o-mini    fixtures/calibration_set.jsonl    min_kappa=0.7
LLM Judge Should Score At Least    ${responses}    rubric=eval/rubric.md    threshold=0.85
```

---

## SecurityKeywords (10)

`AgentGuard.security.library.SecurityKeywords` — supply-chain default-deny + sandbox + redaction.

| Keyword | Tier | Purpose |
|---|:-:|---|
| `Skill Should Pass Security Scan` | T1 | Full 7-stage pipeline; raise on findings exceeding `max_severity` or deny verdict. |
| `Scan Skill` | T1 | Run pipeline; return report without asserting. |
| `Trajectory Should Not Leak Secrets` | T1 | Scan trajectory for credentials/PII; raise if found; optionally redact. |
| `Redact Trajectory` | T1 | Strict / balanced / tokenize redaction modes. |
| `AIDefence Should Find No Injection` | T2/3 | Call AIDefence over MCP; raise if injection score ≥ threshold. |
| `Trajectory Should Not Contain PII` | T2/3 | AIDefence `has_pii`; optionally filter by PII type. |
| `Sandbox Should Be Available` | T1 | Probe Docker / K8s / Proxmox / process backend. |
| `Run In Sandbox` | T1 | Execute command inside the configured sandbox; ADR-013 defaults enforced. |
| `Sandbox Output Should Contain` | T1 | Substring assertion on `result.stdout` or stderr. |
| `Sandbox Exit Code Should Be` | T1 | Assert `result.exit_code == expected`. |

```robot
${report}=    Skill Should Pass Security Scan    ${SKILL_PATH}    max_severity=HIGH
${result}=    Run In Sandbox    ["python", "-c", "print('ok')"]    image=python:3.12-alpine
Sandbox Exit Code Should Be    ${result}    0
Sandbox Output Should Contain  ${result}    ok
```

---

## HooksKeywords (11)

`AgentGuard.hooks.library.HooksKeywords` — Claude Code hook lifecycle (12 events × 4 handlers).

| Keyword | Tier | Purpose |
|---|:-:|---|
| `Synthesize Hook Input` | T1 | Build canonical Claude Code stdin JSON envelope for a given event. |
| `Run Hook Command` | T1 | Shell handler — JSON-on-stdin, exit-2 = block. |
| `Run Hook HTTP` | T1 | POST envelope to URL (Feb 2026 HTTP handler type). |
| `Run Hook Prompt` | T2/3 | Suite-level provider evaluates the envelope (LLM-judged hook). |
| `Run Hook Agent` | T1 | Invoke a Python callable or `pkg.module:attr` import-path. |
| `Hook Should Block` | T1 | Assert exit_code == 2 OR decision == "block". |
| `Hook Should Allow` | T1 | Assert exit_code == 0 AND decision != "block". |
| `Hook Decision Should Be` | T1 | Assert `result.decision == expected` (block / allow / escalate). |
| `Hook Should Inject Context` | T1 | Assert injected-context string contains substring. |
| `Hook Should Modify Tool Input To` | T1 | Assert hook returned `modified_tool_input == expected`. |
| `Detect Stop Hook Loop` | T1 | Detect `stop_hook_active` infinite-Stop antipatterns. |

```robot
${envelope}=  Synthesize Hook Input    event=PreToolUse    tool_name=Bash    tool_input={"command": "rm -rf /"}
${result}=    Run Hook Command    handler=hooks/security_check.sh    stdin=${envelope}
Hook Should Block    ${result}
```

---

## SubAgentsKeywords (13)

`AgentGuard.subagents.library.SubAgentsKeywords` — A2A 1.0 (Linux Foundation) task lifecycle; framework bridges (LangGraph, CrewAI, AutoGen, OpenAI Agents) when their optional deps are installed.

| Keyword | Tier | Purpose |
|---|:-:|---|
| `Get Agent Card` | T1 | Fetch `/.well-known/agent.json` from a URL. |
| `Validate Agent Card` | T1 | Validate dict / Path / URL against A2A 1.0 AgentCard schema. |
| `List Agent Skills` | T1 | Return skill list declared on a card. |
| `Connect To A2A Agent` | T1 | Build a client for a card / URL / in-process server. |
| `Send Task` | T2/3 | Submit a task to an agent and return `Task`. |
| `Get Task Status` | T1 | Return current status string. |
| `Wait For Task Completion` | T1 | Block until terminal state or timeout. |
| `Task Should Have Status` | T1 | Assert `task.status == expected`. |
| `Cancel Task` | T1 | Request cancellation; assert transition. |
| `Get Task Artifact` | T1 | Return artifacts (optionally filtered by mime type). |
| `Get Task Artifact Text` | T1 | Concatenate text content of all artifacts. |
| `Get Task Trajectory` | T1 | Extract tool-call sequence from task. |
| `Task Trajectory Should Match` | T1 | Assert trajectory matches expected (delegates to BFCL matcher). |

```robot
${card}=    Get Agent Card    http://localhost:7001/.well-known/agent.json
${client}=  Connect To A2A Agent    ${card}    transport=http
${task}=    Send Task    ${client}    Plan a 3-day trip to Lisbon
Wait For Task Completion    ${task}    timeout=60s
Task Should Have Status    ${task}    completed
Task Trajectory Should Match    ${task}    ["weather.lookup", "places.search", "summary.compose"]
```

---

## CodingAgentKeywords (34)

`AgentGuard.coding_agent.library.CodingAgentKeywords` — drive coding-agent CLIs + the 12 `#42796` behavioral metric calculators.

### Driver + parser (8)

| Keyword | Purpose |
|---|---|
| `Run Coding Agent` | Dispatch to `local` / `claude-code` / `codex` / `aider` / `opencode` / `cline` / `continue` / `copilot` driver. |
| `Run Coding Agent And Save Session` | Same; additionally persists the parsed Session. |
| `Get Last Coding Agent Session` | Suite-scope memory of the most recent run. |
| `Parse Session JSONL` | Auto-detect format (Claude Code / Codex / Aider / OpenCode); returns `Session`. |
| `Validate Session Schema` | Sanity check (id present, messages list non-degenerate). |
| `Save Session Snapshot` | JSON dump for later diffing / replay. |
| `Load Session Snapshot` | Inverse. |
| `Compute 42796 Metric Pack` | Run all 12 calculators; return `BehavioralReport`. |

### #42796 metric Get/Should pairs (24)

Every metric below ships in a Get-then-Should pair (e.g. `Read Edit Ratio` and `Read Edit Ratio Should Be Above`). Defaults follow research §2.6 baseline values.

| Metric | Default threshold | Direction |
|---|---|---|
| `Read Edit Ratio` | ≥ 4.0 | above |
| `Edits Without Prior Read Percent` | ≤ 10 % | below |
| `Reasoning Loops Per 1K Tool Calls` | ≤ 12 | below |
| `User Interrupts Per 1K Tool Calls` | ≤ 2 | below |
| `Stop Hook Violation Count` | = 0 | zero |
| `First Run Test Pass Rate` | ≥ 0.9 | above |
| `Token Usage Per Prompt` | baseline × 1.5 | below |
| `Self Admitted Errors Per 1K` | ≤ 0.2 | below |
| `Write Mutation Ratio` | ≤ 6 % | below |
| `Repeated Edits Per File Count` | ≤ 3 | below |
| `Simplest Word Frequency Per 1K` | ≤ 5 | below |
| `Convention Violation Rate For Session` | ≤ 5 % | below |

### Aggregate (2)

| Keyword | Purpose |
|---|---|
| `Get Session Health` | Returns `healthy` / `degraded` / `unknown` from the metric pack. |
| `Behavioral Report Should Match Baseline` | Per-metric Mann-Whitney U vs baseline; raise on regression. |

```robot
${result}=  Run Coding Agent    Refactor src/foo.py to use type hints    driver=local
${session}=  Set Variable    ${result.session}
Read Edit Ratio Should Be Above              ${session}    threshold=4.0
Edits Without Prior Read Percent Should Be Below    ${session}    10
First Run Test Pass Rate Should Be Above     ${session}    0.9
Behavioral Report Should Match Baseline      ${result.report}    baselines/2026-q1.json
```

---

## CodingBenchmarkKeywords (15)

`AgentGuard.coding_agent.benchmarks.library.CodingBenchmarkKeywords` — five benchmark loaders + per-benchmark scorers (delegates pass@k to Stats).

| Group | Keywords |
|---|---|
| **SWE-bench Verified** | `Load SWE Bench Dataset`, `Run SWE Bench Task`, `SWE Bench Pass At K Should Be Above` |
| **Aider** | `Load Aider Benchmark Dataset`, `Run Aider Benchmark Task`, `Aider Benchmark Pass Rate Should Be Above` |
| **HumanEval** | `Load HumanEval Dataset`, `Run HumanEval Task`, `HumanEval Pass At K Should Be Above` |
| **MBPP** | `Load MBPP Dataset`, `Run MBPP Task`, `MBPP Pass At K Should Be Above` |
| **LiveCodeBench** | `Load LiveCodeBench Dataset`, `Run LiveCodeBench Task` |
| **Convenience** | `Run Benchmark Suite` (load → iterate → score in one call) |

```robot
${tasks}=    Load HumanEval Dataset    limit=20
${results}=  Create List
FOR    ${task}    IN    @{tasks}
    ${r}=    Run HumanEval Task    ${task}    driver=local    model=openrouter/openai/gpt-4o-mini
    Append To List    ${results}    ${r}
END
HumanEval Pass At K Should Be Above    ${results}    k=1    threshold=0.6
```

---

## MCPScenarioKeywords (31)

`AgentGuard.mcp_scenario.library.MCPScenarioKeywords` — **Phase 4-A test harness (ADR-021)**. Drop-in replacement for `manykarim/rf-mcp` `tests/e2e/`. Two equally first-class usage patterns: pure RF keywords (no YAML) and YAML-driven (rf-mcp v1 schema).

### Scenario lifecycle (5)

| Keyword | Purpose |
|---|---|
| `Load MCP Scenario` | Parse a Scenario YAML (rf-mcp v1 schema). |
| `Save MCP Scenario` | Round-trip back to YAML. |
| `Create Scenario` | Build a Scenario inline — no YAML required. |
| `Add Expected Tool` | Append an `ExpectedToolCall` (name + min/max calls + required_params). |
| `Run MCP Scenario` | Drive the scenario via `manual` or `local` driver; returns `ScenarioResult`. |

### Tracked session (5)

| Keyword | Purpose |
|---|---|
| `Start Tracked MCP Session` | Wrap an MCP `ServerHandle` with a recording overlay. |
| `Call Tracked Tool` | Dispatch a tool call — auto-records as `ToolCallRecord`. |
| `Get Tool Call Records` | Return the in-memory record list (read-only snapshot). |
| `Reset Tracked MCP Session` | Clear records (scope hit rate to one suite phase). |
| `End Tracked MCP Session` | Mark session ended; records remain readable. |

### Aggregate assertions — the rf-mcp parity surface (10)

| Keyword | Purpose |
|---|---|
| `Compute Scenario Result` | Aggregate session.records vs scenario.expected_tools → `ScenarioResult`. |
| `Tool Hit Rate` | rf-mcp formula: (met expected) / total expected. |
| `Tool Hit Rate Should Be Above` | Assert ≥ threshold (the canonical rf-mcp gate). |
| `Tool Call Success Rate` | successful / total over recorded calls. |
| `Tool Call Success Rate Should Be Above` | Assertion variant. |
| `Tool Call Count` | Total or per-tool count (`name=`). |
| `Tool Call Count Should Be Between` | Min/max bounds. |
| `Failed Tool Call Count Should Be At Most` | Direct upper bound on errors. |
| `Required Tool Should Have Been Called With Params` | Per `ExpectedToolCall.required_params` semantics. |
| `Scenario Result Should Be Successful` | Assert `result.success` flag. |
| `Tool Call Statistics` | Return rf-mcp-shaped summary stats dict. |

### Artifact analysis (4)

| Keyword | Purpose |
|---|---|
| `Get Generated Robot Suite Path` | First agent-emitted Robot suite path (or None). |
| `Get Generated Robot Suites` | All emitted suite paths. |
| `Generated Robot Suite Should Pass` | `robot --dryrun` the suite; assert exit 0. |
| `Get Generated Files` | Arbitrary files the agent produced. |
| `Generated Artifact Should Match Schema` | JSON-Schema validate any structured artifact. |

### Result IO (2)

| Keyword | Purpose |
|---|---|
| `Save Scenario Result` | Persist as JSON (rf-mcp `metrics/*.json` shape). |
| `Load Scenario Result` | Read a previously-saved `ScenarioResult` JSON. |

### Statistical comparison across N runs (3)

| Keyword | Purpose |
|---|---|
| `Compare Scenarios Pass Rate` | pass@k over the success flags (delegates to Stats). |
| `Tool Hit Rate Distribution Should Stochastically Dominate` | Mann-Whitney U on hit-rate distributions vs baseline. |
| `Scenario Drift Should Not Exceed` | Cliff's δ on `total_tool_calls` distributions. |

```robot
# Pure RF API — no YAML needed
${scenario}=    Create Scenario    id=demo    prompt=Use add(2,3)    expected_outcome=returns 5    min_tool_hit_rate=0.99
Add Expected Tool    ${scenario}    add    min_calls=1    max_calls=2

${session}=    Start Tracked MCP Session    ${HANDLE}
Call Tracked Tool    ${session}    add    {"x": 2, "y": 3}
End Tracked MCP Session    ${session}

${result}=    Compute Scenario Result    ${scenario}    ${session}
Scenario Result Should Be Successful    ${result}
Tool Hit Rate Should Be Above    ${result}    0.99
Required Tool Should Have Been Called With Params    ${session}    add    {"x": 2, "y": 3}
```

```robot
# YAML drop-in for rf-mcp users
${scenario}=    Load MCP Scenario    scenarios/restful_booker_api.yaml
${result}=    Run MCP Scenario    ${scenario}    server=${HANDLE}
...    driver=local    model=openrouter/openai/gpt-4o-mini
Tool Hit Rate Should Be Above    ${result}    ${scenario.min_tool_hit_rate}
Save Scenario Result    ${result}    metrics/${scenario.id}.json
```

---

## Top-level AgentGuard (1)

`AgentGuard.library.AgentGuard` — the entry point. One own keyword for introspection.

| Keyword | Purpose |
|---|---|
| `Get AgentGuard Info` | Returns `{version, provider, model, judge_model, transport, telemetry, baseline_path, components}`. |

```robot
*** Settings ***
Library    AgentGuard    provider=litellm    model=openrouter/anthropic/claude-sonnet-4-5

*** Test Cases ***
Library Loads All Eleven Components
    ${info}=    Get AgentGuard Info
    Length Should Be    ${info.components}    11
```

---

## Common usage patterns

### MCP server smoke test
```robot
Library    AgentGuard

*** Test Cases ***
Server Implements Required Tools
    ${handle}=    Connect To MCP Server    http://localhost:8080/mcp
    MCP Server Should Implement Capabilities    ${handle}    tools    resources
    ${stats}=    Measure MCP Tool Latency    ${handle}    search    runs=50
    Should Be True    ${stats}[p95] < 500
    Stop MCP Server    ${handle}
```

### Skill grading regression test
```robot
Library    AgentGuard    judge_model=openrouter/openai/gpt-4o-mini

*** Test Cases ***
Skill Improves Over Baseline
    Calibrate Judge    openrouter/openai/gpt-4o-mini    fixtures/calibration.jsonl    min_kappa=0.7
    Skill Should Pass Security Scan    skills/my-skill    allow_unsigned=${True}
    ${current}=    Run N Times    runs=30    Run Skill Eval    skills/my-skill
    ${baseline}=   Load Baseline    baselines/2026-q1.json
    Mann Whitney U Should Show Improvement    ${current}    ${baseline}    alpha=0.05
```

### #42796 behavioral regression
```robot
*** Test Cases ***
Coding Agent Maintains Healthy Discipline
    ${result}=    Run Coding Agent    Refactor src/   driver=claude-code
    Read Edit Ratio Should Be Above              ${result.session}    4.0
    Edits Without Prior Read Percent Should Be Below    ${result.session}    10
    Reasoning Loops Per 1K Tool Calls Should Be Below    ${result.session}    12
    Stop Hook Violations Should Be Zero          ${result.session}
    First Run Test Pass Rate Should Be Above     ${result.session}    0.9
```

### MCP scenario harness — drop-in for rf-mcp e2e
```robot
*** Test Cases ***
Restful Booker API Scenario
    ${scenario}=    Load MCP Scenario    scenarios/restful_booker_api.yaml
    ${result}=    Run MCP Scenario    ${scenario}    server=${RF_MCP_HANDLE}
    ...    driver=local    model=openrouter/openai/gpt-4o-mini
    Tool Hit Rate Should Be Above              ${result}    ${scenario.min_tool_hit_rate}
    Failed Tool Call Count Should Be At Most   ${result}    2
    ${suite}=    Get Generated Robot Suite Path    ${result}
    Generated Robot Suite Should Pass    ${suite}
    Save Scenario Result    ${result}    metrics/${scenario.id}.json
```

---

## How to regenerate this document

Run `uv run python tests/scripts/dump_keywords.py` (script captured below for reference) to re-emit the keyword tables when new keywords land. The `libdoc` HTMLs under `docs/api/` provide a richer browser-friendly view per sub-library.

```python
import importlib, inspect
from AgentGuard.library import _SUB_LIBRARIES
from AgentGuard.providers.mock import MockProvider

for mod_name, cls_name in _SUB_LIBRARIES:
    mod = importlib.import_module(mod_name)
    instance = getattr(mod, cls_name)(provider=MockProvider())
    for attr in sorted(dir(instance)):
        method = getattr(instance, attr, None)
        robot_name = getattr(method, "robot_name", None)
        if robot_name:
            sig = inspect.signature(method)
            doc = (inspect.getdoc(method) or "").splitlines()[:1]
            print(f"- `{robot_name}` `{sig}` — {doc[0] if doc else ''}")
```
