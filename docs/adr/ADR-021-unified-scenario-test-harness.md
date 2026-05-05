# ADR-021: Unified Scenario Test Harness for MCP Servers, Agent Skills, and Coding Agents

- **Status**: Proposed
- **Date**: 2026-05-01
- **Deciders**: agentguard-architecture-swarm
- **Bounded Context**: **TestHarness** (NEW; cross-cutting orchestrator over MCP, Skills, CodingAgent, ToolCallCorrectness, Stats, Telemetry)
- **Supersedes**: none — extends ADR-002 (MCP transports), ADR-004 (BFCL matching), ADR-009 (CodingAgentDriver), ADR-010 (Session schema)
- **Drivers**: drop-in replacement for `manykarim/rf-mcp` `tests/e2e/` (research §6.1, §6.6); unify "agent runs scenario against server, record every tool call" across the three currently-separate test surfaces.

## Context

rf-mcp's `tests/e2e/` defines a remarkably clean five-piece harness — Scenario (YAML), `TrackedMCPClient`, `MetricsCollector` with **Tool Hit Rate**, `ScenarioResult` JSON artifact, autonomous Pydantic AI agent driver — that **AgentGuard cannot currently emulate without a per-test rewrite** (Phase 1 only knows AST per-call equality via BFCL; Phase 3 only knows synthetic ReAct loops via LocalDriver, with no MCP-server target).

Three independent strands of evidence point at the same gap:

1. **rf-mcp's harness covers patterns AgentGuard's existing keywords cannot express.** "Tool was called between 4 and 20 times AND `required_params` matched on every call AND total error count ≤ N" is a multi-call aggregate; BFCL's per-call AST matcher does not aggregate.
2. **The `ScenarioResult` artifact is the canonical interchange format** (rf-mcp `tests/e2e/metrics/*.json`, 375+ files in the upstream repo). AgentGuard's `SkillScorecard` does not match this shape, so a one-way adapter is needed even if we wanted to consume rf-mcp's existing artifacts.
3. **Autonomous-agent driving with auto-recorded tool calls is the load-bearing primitive** for evaluating MCP servers under realistic LLM workloads. We have `LocalDriver` for the agent loop and `MCPKeywords.call_mcp_tool` for individual calls, but no glue: a driver that targets a specific MCP server, lets the LLM choose tools freely, and emits a `Session` whose `tool_calls` came from the MCP wire (not from synthetic mocks).

The user-facing goal — "a full and complete test harness for MCP Servers, Agent Skills and Coding Agents" — requires one more bounded context whose responsibility is **scenario orchestration + tool-call statistics + persistent JSON artifacts**, sitting on top of the five existing contexts that already handle protocol, parsing, AST matching, and agent driving.

## Decision

Adopt rf-mcp's harness shape **verbatim** (same field names, same JSON artifact schema, same hit-rate formula) and expose it as a new **TestHarness** bounded context with the following keyword surface:

### Scenario lifecycle (5 keywords)
- `Load MCP Scenario` — load YAML (rf-mcp v1 schema).
- `Save MCP Scenario` — round-trip back to YAML.
- `Run MCP Scenario` — drive a chosen `driver` (`local` | `claude-code` | `codex` | `aider` | `none-direct-call`) against a chosen MCP server (target=path | URL | in-memory instance) with the scenario prompt; auto-track tool calls; return `ScenarioResult`.
- `Save Scenario Result` — write the canonical `ScenarioResult` JSON to disk (drop-in compatible with rf-mcp `metrics/*.json`).
- `Load Scenario Result` — parse one of those JSONs back.

### Tracked-session primitives (3 keywords)
- `Start Tracked MCP Session` — wraps an existing `ServerHandle` so every subsequent `Call MCP Tool` auto-records to the session-scope `MetricsCollector`.
- `Get Tool Call Records` — return the recorded `ToolCallRecord[]`.
- `End Tracked MCP Session` — flush + close.

### Aggregate assertions (8 keywords — the meat)
- `Tool Hit Rate` (Get) / `Tool Hit Rate Should Be Above` (Assert) — implements rf-mcp's exact formula.
- `Tool Call Success Rate` / `Tool Call Success Rate Should Be Above`.
- `Tool Call Count` / `Tool Call Count Should Be Between` — total or per-tool with `name=` filter.
- `Failed Tool Call Count Should Be At Most` — direct upper bound on errors.
- `Required Tool Should Have Been Called With Params` — per-`ExpectedToolCall.required_params` semantics.
- `Scenario Result Should Be Successful` — checks `success` flag (which is `tool_hit_rate ≥ scenario.min_tool_hit_rate AND len(errors) == 0` per rf-mcp).

### Artifact analysis (4 keywords)
- `Get Generated Robot Suite Path` / `Generated Robot Suite Should Pass` — extract artifact paths from a `ScenarioResult.metadata`, then `robot --dryrun` (or full run) against the generated suite.
- `Get Generated Files` — return the list of files the agent produced under `cwd` during the scenario.
- `Generated Artifact Should Match Schema` — JSON-schema validate any structured artifact (e.g. the suite-builder's emitted YAML).

### Statistical comparison (delegates to existing Stats module — 3 keywords)
- `Compare Scenarios Pass Rate` — pass@k across N runs of the same scenario (delegates to `pass_at_k`).
- `Tool Hit Rate Distribution Should Stochastically Dominate` — Mann-Whitney over hit-rates from current vs baseline (delegates to `mann_whitney_u`).
- `Scenario Drift Should Not Exceed` — Cliff's δ on `total_tool_calls` distribution vs baseline.

**Total: 23 new keywords**, composed into the top-level `Library AgentGuard` as a new sub-library (`MCPScenarioKeywords`).

### Schema decisions

- **Scenario YAML format**: byte-identical to rf-mcp's. Same field names (`id`, `name`, `description`, `context`, `prompt`, `expected_tools`, `expected_outcome`, `min_tool_hit_rate`, `tags`). Reuse `ExpectedToolCall(tool_name, min_calls, max_calls, required_params)`.
- **`ScenarioResult` JSON**: byte-identical to rf-mcp's (`scenario_id`, `success`, `tool_calls`, `tool_hit_rate`, `total_tool_calls`, `expected_tool_calls_met`, `expected_tool_calls_total`, `errors`, `execution_time_seconds`, `agent_output`, `metadata`). Drop-in adoption guarantee.
- **`ToolCallRecord`**: `(tool_name, arguments, success, result, error, timestamp)`. Identical to rf-mcp.
- **Hit-rate formula**: identical to rf-mcp `metrics_collector.py:57-99`.

### Driver wiring decision

Extend the Phase 3 `LocalDriver` with an `mcp_server` parameter:
```python
LocalDriver().run(prompt, DriverConfig(model=..., mcp_server=ServerHandle))
```
When `mcp_server` is set, the synthetic ReAct loop's tool definitions come from `List MCP Tools(mcp_server)` and tool calls are dispatched to `Call MCP Tool` — every dispatch is intercepted by the `TrackedMCPSession` and recorded. This replaces the canned mock toolset with real MCP server calls, closing the autonomous-agent gap.

For non-Local drivers (Claude Code, Codex), the same `mcp_server` parameter writes an MCP server entry into a tmp `.mcp.json` and points the CLI at it via `--mcp-config`.

## Rationale

- **rf-mcp drop-in** — adopting the schema verbatim means existing rf-mcp scenarios + artifacts work without translation. The user's stated goal ("replace most of the agent and e2e tests of rf-mcp via this robot framework library") is satisfied with a one-line YAML load + a five-line Robot suite.
- **Hit rate is fundamentally aggregate** — BFCL (ADR-004) covers `Tool Sequence Should Match` (per-call ordered) but not "called between 4 and 20 times". The formal distinction: BFCL = transcript-level structural match; Tool Hit Rate = multi-call statistical aggregate. They are complementary, not competing.
- **TrackedMCPSession reuses the existing `ServerHandle`** — no new transport surface, just a recording hook installed on the session-scope library state. Zero impact on Phase 1 MCP keywords for users who don't opt in.
- **ScenarioResult.metadata is intentionally open** — rf-mcp uses it to stash the generated Robot suite path, model name, OPENAI_API_KEY presence boolean, etc. Keeping it as `dict[str, Any]` matches their pattern and avoids over-specification.
- **Reuses Phase 1+3 statistics** — the comparison keywords delegate to `pass_at_k`, `mann_whitney_u`, `cliffs_delta` — no new statistics math.

## Consequences

### Positive
- **Drop-in rf-mcp e2e replacement.** Users with existing rf-mcp scenarios run them via `Load MCP Scenario` + `Run MCP Scenario` + `Tool Hit Rate Should Be Above` — three keywords. The 17 scenario YAMLs and 375 metrics JSONs in the upstream repo become test fixtures for AgentGuard's own validation.
- **Unified harness across the three pillars.** The same Scenario abstraction works for testing an MCP server (driver runs scenario → MCP server records calls), for testing an Agent Skill (driver runs scenario with skill loaded → assert tool selection matches expectations), and for evaluating a Coding Agent on a benchmark (existing benchmarks become Scenarios).
- **Persistent artifact pipeline.** `ScenarioResult` JSONs + `Generated Robot Suite Should Pass` close the loop: not just "did the agent call the right tools" but "did the agent produce a working Robot suite".
- **Statistical baselines for free.** Mann-Whitney + Cliff's δ on hit-rate distributions catches regressions in agent behavior across model versions — research §2.7 / §3.4 / ADR-005 already justified this machinery.

### Negative
- **One more bounded context (12 → 13).** The DDD model gains a context with three aggregates (Scenario, ScenarioRun, ToolCallRecord). Worth it: every other context already exists for a *layer*; TestHarness is for *workflow* and pulls them together.
- **Driver coupling.** `LocalDriver.run(mcp_server=...)` is the cleanest extension but wires Phase 3 driver code into Phase 4-equivalent harness behavior. Mitigated by keeping the `mcp_server` parameter optional.
- **Two overlapping keyword groups for tool calls.** Users have to learn when to reach for `Tool Sequence Should Match` (BFCL — when you can name the exact expected calls) vs `Tool Hit Rate Should Be Above` (when you can only declare bounds). Documented in the new context's README.
- **YAML format pinned to rf-mcp v1.** If rf-mcp evolves the schema (e.g. adds `max_total_calls`), AgentGuard either follows or diverges; we follow per ADR-014 spec-version-pinning policy.

### Neutral
- The TestHarness context emits the same `MetricResult` and `BehavioralReport` types Phase 3 already uses, so existing baselines + Mann-Whitney machinery slot in without change.
- The `metadata` field stays as `dict[str, Any]` — no schema gating until users ask.

## Alternatives Considered

- **Extend the MCP context instead of adding TestHarness.** Rejected — MCP's responsibility is wire protocol and session lifecycle. Aggregating multi-call statistics belongs to a context that owns the run, not the connection.
- **Reuse `SkillScorecard` instead of `ScenarioResult`.** Rejected — `SkillScorecard` is per-skill (one row per response) and lacks `tool_hit_rate`/`expected_tool_calls_met`. The two will live side by side; we do not want lossy down-conversion.
- **Implement scenarios as Robot resource files (`.resource`) instead of YAML.** Rejected — rf-mcp users have YAML; making them rewrite breaks the "drop-in" promise.
- **Map `ExpectedToolCall` onto the existing BFCL `ExpectedCall` with a `count_min/count_max` extension.** Rejected — conflates per-call AST equality with multi-call aggregate semantics. Two distinct value objects.
- **Defer to "users wrap rf-mcp with our keywords manually".** Rejected — the user explicitly asked for replacement, and our existing keywords are insufficient by themselves.

## Related ADRs

- **ADR-002** — MCP transports (TestHarness sits on top of `Connect To MCP Server`).
- **ADR-004** — BFCL AST matching (TestHarness adds aggregate-statistics layer; coexists).
- **ADR-005** — Statistical assertion API (cross-scenario stats delegate here).
- **ADR-009** — CodingAgentDriver (extended with `mcp_server=` parameter).
- **ADR-010** — Session schema + #42796 metrics (TestHarness can compute the #42796 pack against any `ScenarioResult.tool_calls`).
- **ADR-012** — OTel + RF listener (every scenario run emits an OTel trace tagged with `scenario.id` for cross-run aggregation).
- **ADR-014** — Spec version pinning (we pin to rf-mcp scenario schema v1).

## Implementation Phasing (proposed)

- **Phase 4-A (1 month, MVP)** — `MCPScenarioKeywords` class, scenario loader, tracked-session wrapper, hit-rate + statistics keywords, `ScenarioResult` save/load. **Goal**: AgentGuard runs every existing rf-mcp scenario (17 YAMLs) with byte-equivalent JSON artifacts.
- **Phase 4-B (1 month, autonomous driving)** — `LocalDriver(mcp_server=...)`, Claude Code driver `--mcp-config` injection, generated-suite analysis keywords. **Goal**: AgentGuard reproduces rf-mcp's `test_autonomous_agent_with_scenario` parametrized run end-to-end with real OpenRouter LLM.
- **Phase 4-C (½ month, polish)** — Mann-Whitney + Cliff's δ across N-run hit-rate distributions; OTel trace tagging; libdoc HTML; `examples/12_mcp_scenario_replacement.robot` with three of rf-mcp's scenarios.

Total Phase-4 budget: ≈ 2.5 months (sequential) or ≈ 1.5 months (parallel swarm).
