# Bounded Context: MCPScenario / TestHarness (NEW — proposed in ADR-021)

> **Status**: Proposed — gates on acceptance of ADR-021. To be folded into
> `bounded-contexts.md` as the 13th context once accepted.

## Strategic classification

**Core** — this is the workflow orchestrator that ties Provider, MCP, Skills,
CodingAgent, ToolCallCorrectness, Stats, Judge, and Telemetry together for the
"agent runs scenario, tool calls recorded, hit rate asserted" workflow.

It is the only context whose *raison d'être* is end-to-end scenario gating,
not protocol mechanics or per-call correctness.

## Purpose

Run a declarative **Scenario** against any combination of:
- an MCP server (rf-mcp pattern — primary),
- an Agent Skill (skill loaded into system message — extension),
- a Coding Agent (driver runs prompt against a workspace — extension),

while **auto-recording every tool call** through a tracked session, **computing
aggregate statistics** (Tool Hit Rate, success rate, per-tool counts), and
**persisting a portable JSON artifact** (`ScenarioResult`) compatible with
rf-mcp's `tests/e2e/metrics/*.json` schema.

## Aggregates

### `Scenario` (entity)
- **Identifier**: `id` (string, unique per project).
- **Invariants**:
  - `min_tool_hit_rate ∈ [0, 1]`.
  - `expected_tools[].min_calls ≤ expected_tools[].max_calls` when both set.
  - `context ∈ {web, api, mobile, desktop, generic}`.
- **Eager**: frontmatter (id, name, description, prompt, context, tags, min_tool_hit_rate).
- **Lazy**: `expected_tools[]` (loaded by the runner when the scenario starts).
- **Source of truth**: a YAML file with rf-mcp v1 schema OR an in-memory dict.

### `ScenarioRun` (entity)
- **Identifier**: `(scenario_id, started_at)`.
- **Invariants**:
  - `success = (tool_hit_rate ≥ scenario.min_tool_hit_rate) AND (failed_count ≤ tolerance)`.
  - `tool_calls` is append-only during the run.
  - `ended_at ≥ started_at`.
- **Lifecycle**: created by `Run MCP Scenario`; finalised on driver return; serialised to `ScenarioResult` JSON.
- **Loaded together**: scenario reference + tool_calls + statistics + agent_output + metadata.

### `ToolCallRecord` (value object)
- Immutable; emitted exactly once per `Call MCP Tool` invocation while a
  TrackedMCPSession is active.
- Fields: `tool_name`, `arguments`, `success`, `result`, `error`, `timestamp`.
- Identity by composite of all fields (no surrogate id).

### `TrackedMCPSession` (aggregate root)
- Wraps a `ServerHandle` from the MCP context (Customer/Supplier upstream).
- Owns the in-memory `tool_calls: list[ToolCallRecord]` for the suite scope.
- **Invariant**: every successful or failed `Call MCP Tool` made through the
  wrapped handle appends exactly one record.
- **Lifecycle**: `Start Tracked MCP Session` → N `Call MCP Tool` → `End Tracked MCP Session`.

## Value objects

| Name | Shape | Source / Notes |
|---|---|---|
| `ExpectedToolCall` | `(tool_name, min_calls=1, max_calls=None, required_params=None)` | rf-mcp `models.py:7` verbatim |
| `ScenarioContext` | enum: `web | api | mobile | desktop | generic` | rf-mcp v1 |
| `ToolHitRate` | `float ∈ [0, 1]` — (met expected) / (total expected) | rf-mcp `metrics_collector.py:57` |
| `ToolCallStatistics` | `{total, successful, failed, success_rate, by_tool: dict[name, count], unique_tools}` | rf-mcp `metrics_collector.py:174` |
| `ScenarioResult` | `(scenario_id, success, tool_calls[], tool_hit_rate, total_tool_calls, expected_tool_calls_met, expected_tool_calls_total, errors[], execution_time_seconds, agent_output, metadata: dict[str, Any])` | rf-mcp `models.py:52` verbatim |
| `GeneratedArtifactRef` | `(kind: "robot_suite" | "json" | "file", path: Path, schema: dict | None)` | NEW — extends rf-mcp |

## Domain events

| Event | Triggered by | Subscribers |
|---|---|---|
| `ScenarioLoaded` | `Load MCP Scenario` | Telemetry (OTel span attribute `scenario.id`) |
| `ScenarioStarted` | `Run MCP Scenario` entry | Telemetry, MCPScenarioCollector |
| `ToolCallRecorded` | `TrackedMCPSession.append` (every call) | Telemetry (per-call span), Stats (running counts) |
| `ScenarioFailed` | `success == False` after run | Telemetry (error span), Judge (calibration miss?) |
| `ScenarioCompleted` | success final | Telemetry, Memory (HNSW: scenario→result for ADR-016 retrieval) |
| `ArtifactProduced` | `Get Generated Robot Suite Path` returns non-empty | Security (`Generated Robot Suite Should Pass` later runs scanner pre-flight) |
| `ScenarioBaselineDrifted` | Mann-Whitney on hit-rate distribution shows p < α | BehavioralMetrics (cross-context regression signal) |

## Repositories

- **ScenarioRepository** — load/save Scenario YAMLs from a configurable
  `scenarios/` root + an optional in-memory dict provider.
- **ScenarioResultRepository** — write/read `ScenarioResult` JSONs under a
  configurable `metrics/` root (default `.agentguard/scenarios/`); maintains
  an index keyed on `scenario_id` for baseline retrieval.
- **TrackedSessionRegistry** — suite-scoped registry mapping
  `ServerHandle.name` → active `TrackedMCPSession` so multiple `Call MCP Tool`
  invocations across a suite roll into one record list.

## Anti-corruption layers

| Adjacent context | Direction | Translation responsibility |
|---|---|---|
| **MCP** | upstream | Wrap `ServerHandle` into `TrackedServerHandle`; intercept `call_tool` to emit `ToolCallRecorded`. |
| **CodingAgent** | upstream | When `driver=local|claude-code|...`, the driver returns a `Session`; we map `Session.tool_calls → ToolCallRecord[]` (drop fields, add `success` derived from absence of error tool_response). |
| **ToolCallCorrectness** | downstream | Optionally re-validate the recorded calls against an `ExpectedCall[]` schema using BFCL semantics (per-call), as a stricter alternative to hit-rate (aggregate). |
| **Stats** | downstream | Hit-rate distributions across N runs flow through `pass_at_k`, `mann_whitney_u`, `cliffs_delta`, `bootstrap`. |
| **Telemetry** | downstream | Every domain event emits a span; OTel span attribute `scenario.id` ties the trace to the scenario. |
| **Skills** | upstream (extension) | Skill body becomes the system message in the driver's prompt; `expected_tools` are MCP tools the agent should call **given the skill is loaded**. |
| **Security** | upstream | `Generated Robot Suite Should Pass` runs the scanner pre-flight on the agent-emitted suite per ADR-006; sandbox enforced per ADR-013 if the suite is fully executed. |
| **Judge** | downstream | The scenario's `expected_outcome` (free-text) can be validated by an LLM-as-Judge against `agent_output`. |

## Surface (Robot Framework keywords — 23 new)

| Group | Keyword | Purpose |
|---|---|---|
| Lifecycle | `Load MCP Scenario` | YAML → `Scenario`. |
| | `Save MCP Scenario` | `Scenario` → YAML. |
| | `Run MCP Scenario` | Drive a `Scenario` against a `driver` + (server | skill | repo). Returns `ScenarioResult`. |
| | `Save Scenario Result` | Persist `ScenarioResult` JSON (rf-mcp shape). |
| | `Load Scenario Result` | Read prior `ScenarioResult` JSON. |
| Tracked session | `Start Tracked MCP Session` | Wrap an MCP `ServerHandle` so subsequent `Call MCP Tool` records. |
| | `Get Tool Call Records` | Return the in-memory record list. |
| | `End Tracked MCP Session` | Flush and detach. |
| Aggregate assertions | `Tool Hit Rate` | Get the rate from a `ScenarioResult` or the live session. |
| | `Tool Hit Rate Should Be Above` | Assertion variant. |
| | `Tool Call Success Rate` / `… Should Be Above` | Successful/total. |
| | `Tool Call Count` / `… Should Be Between` | Total or per-tool with `name=`. |
| | `Failed Tool Call Count Should Be At Most` | Hard upper bound. |
| | `Required Tool Should Have Been Called With Params` | Per `ExpectedToolCall.required_params`. |
| | `Scenario Result Should Be Successful` | Checks `success` flag. |
| Artifact analysis | `Get Generated Robot Suite Path` | From `result.metadata["generated_suites"]`. |
| | `Generated Robot Suite Should Pass` | `robot --dryrun` (or `--include-tag <…>` for full). |
| | `Get Generated Files` | `result.metadata["files_created"]`. |
| | `Generated Artifact Should Match Schema` | JSON-schema validation. |
| Statistical comparison | `Compare Scenarios Pass Rate` | pass@k via `Stats`. |
| | `Tool Hit Rate Distribution Should Stochastically Dominate` | Mann-Whitney via `Stats`. |
| | `Scenario Drift Should Not Exceed` | Cliff's δ. |

## Ubiquitous-language additions

- **Scenario** — declarative description of a multi-step agent task with
  expected tool-call shape.
- **Tool Hit Rate** — fraction of `expected_tools[]` whose call counts and
  required parameters were observed in a run.
- **Tracked MCP Session** — a per-suite recording overlay on an MCP
  `ServerHandle`.
- **Tool Call Statistics** — the `(total, successful, failed, success_rate,
  by_tool, unique_tools)` summary computed from the recorded call list.
- **ScenarioResult** — the canonical JSON artifact persisted after a run;
  byte-equivalent to rf-mcp `tests/e2e/metrics/*.json`.
- **Expected Tool Call** — `(name, min_calls, max_calls, required_params)`
  declaring an aggregate-counting expectation, distinct from BFCL's
  per-call `ExpectedCall`.
- **Generated Artifact** — any file the agent produces during a scenario
  run (typically a Robot Framework suite from rf-mcp's `build_test_suite`).
