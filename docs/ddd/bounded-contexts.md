# Bounded Contexts — robotframework-agentguard

Twelve contexts (Phase 1–3 baseline) plus **TestHarness / MCPScenario** as a 13th
context proposed by **ADR-021** (status: Proposed; full spec in
`docs/ddd/MCPScenario-bounded-context.md`). Each section lists: **purpose**,
**aggregates**, **value objects**, **domain events**, **repositories**, and
**ACL** required at every boundary with adjacent contexts. Aggregates are
described conceptually — no Python class definitions.

Research citations point to `docs/research/research.md`. ADR-021 cites
`manykarim/rf-mcp/tests/e2e/` as the load-bearing prior art for the
TestHarness context's shape.

> **Shared Kernel addition — AssertionEngine (ADR-022).** Per
> `docs/adr/ADR-022-assertion-engine-shared-kernel.md`, the PyPI
> `assertionengine` library is adopted as a **utility-level Shared Kernel** for
> value-comparison primitives (`AssertionOperator`, `verify_assertion`,
> formatter scope, polling). It is consumed by every context that ships
> `Get/Should` keyword pairs — Stats, MCP, Skills, Hooks, SubAgents, CodingAgent,
> MCPScenario, ToolCallCorrectness, Security, Judge — through a thin
> `AssertionAdapter` ACL per sub-library. AssertionEngine owns no domain and is
> therefore **not** a 14th bounded context; it is a shared kernel utility in
> the same sense Python's `dataclasses` is. Full DDD model in
> `docs/ddd/assertion-engine-shared-kernel.md`.

---

## 1. Provider Context

- **Purpose:** Uniform LLM access. Default LiteLLM (100+ providers), with thin per-vendor adapters where features leak through (Anthropic extended thinking, OpenAI Responses, Gemini grounding, Bedrock prompt caching). §4.1, §4.4, §7.1.
- **Aggregates:** `LLMProvider` — root that owns model selection, vendor knobs, retry/backoff, cost accounting.
- **Value Objects:** `Model` (name + capabilities), `ChatMessage`, `ToolDefinition`, `ChatResponse`, `Cost`, `ProviderCapability` (e.g. `extended_thinking`, `structured_outputs`, `grounding`).
- **Domain Events:** `ChatRequested`, `ChatCompleted`, `ChatStreamChunk`, `RateLimited`, `ProviderError`, `CostObserved`.
- **Repositories:** `ModelRegistry` (capability lookup), `CostLedger`.
- **ACL:** A `LiteLLMNormalizer` ACL maps every provider's exception, response, and tool-call schema to OpenAI-shaped objects so downstream contexts never see vendor specifics. Vendor-specific kwargs are gated by `Provider.supports(capability)`.

---

## 2. MCP Context

- **Purpose:** Test MCP servers — protocol compliance, tool/resource/prompt invocation, capability discovery, latency probes. §2.1, §4.4, §7.3.
- **Aggregates:** `MCPServer` — root owning a `ConnectionTransport`, the discovered `Capabilities`, the `Tool` / `Resource` / `Prompt` catalogs, and the in-flight `MCPCall` collection.
- **Value Objects:** `Tool` (name + JSON Schema), `Resource` (URI + MIME type), `Prompt` (template), `MCPCall` (request + response + latency), `Transport` (`stdio` | `sse` | `streamable-http` | `in-memory`), `Capabilities`.
- **Domain Events:** `ServerConnected`, `ServerDisconnected`, `ServerCapabilitiesDiscovered`, `ToolCalled`, `ToolFailed`, `ResourceFetched`, `PromptInvoked`, `LatencyMeasured`.
- **Repositories:** `ToolCatalog`, `TransportRegistry` (factory for the four transports), `ServerSessionStore`.
- **ACL:**
  - To **Provider:** Provider supplies any LLM that consumes MCP tool descriptions; an ACL converts MCP tool schemas to the Provider's `ToolDefinition` shape.
  - To **ToolCallCorrectness:** `MCPCall` is exposed via a published `ActualCall` value object — MCP's transport metadata is stripped at the boundary.
  - To **MCP Inspector CLI:** subprocess wrapper translates Inspector text/JSON output into domain `Capabilities` and `Tool` objects.

---

## 3. Skills Context

- **Purpose:** Discover, parse, validate, and grade Agent Skills under controlled agent sessions. §2.2, §5 Phase 1.
- **Aggregates:** `Skill` — root composed of `SkillFrontmatter`, optional `Scripts`, `References`, `Assets`, and the resulting `SkillScorecard` after grading.
- **Value Objects:** `SkillFrontmatter` (`name`, `description`, optional `allowed-tools`), `SkillInstallPath`, `SkillScorecard` (per-prompt verdicts + aggregate score), `Rubric` (passed in from Judge), `EvalPrompt`.
- **Domain Events:** `SkillDiscovered`, `SkillLoaded`, `SkillFrontmatterValidated`, `SkillGraded`, `SkillFailed`, `SkillScorecardEmitted`, `SkillConventionViolationDetected`.
- **Repositories:** `SkillRepository` (filesystem walker over the four install paths; pluggable for marketplace fetchers), `RubricLibrary`, `BaselineSkillScorecardStore`.
- **ACL:**
  - To **Security:** every `SkillDiscovered` event is gated by `SecurityPolicy.evaluate(skill)` (see §9). Unsigned third-party skills are denied by default per §8.3.
  - To **Provider:** the grader uses Provider to drive the model under test; an ACL keeps Skills agnostic of which vendor backs the grader.
  - To **Judge:** Judge consumes a `Rubric` and the grader's transcripts and returns `JudgmentResult`s. Skills never reaches into Judge internals.
  - To **CodingAgent:** when grading runs against a real CLI (e.g. Claude Code via `rf-skill-eval`), Skills delegates session execution to CodingAgent and consumes its normalized `Session` schema.

---

## 4. Hooks Context

- **Purpose:** Simulate the 12 Claude Code hook events and assert handler behavior across the four handler types. §2.3, §5 Phase 2.
- **Aggregates:** `HookHarness` — root owning the synthesized envelopes, captured handler outputs, and decision verdicts of one hook test run. `HookExecution` is a child entity per fired event.
- **Value Objects:** `HookEvent` (one of the 12 types), `HookEnvelope` (`tool_name`, `tool_input`, `tool_response`, `transcript_path`, `cwd`, `session_id`, `stop_hook_active`), `HookHandlerType` (`command` | `http` | `prompt` | `agent`), `HookDecision` (`block` | `allow` | `escalate` + reason + permission), `ExitCode`.
- **Domain Events:** `HookFired`, `HookBlocked`, `HookAllowed`, `HookEscalated`, `HookContextInjected`, `HookInputModified`, `LoopDetected`, `HookHandlerErrored`.
- **Repositories:** `HookEnvelopeFactory` (canonical builders per event type), `HookHandlerRegistry` (pluggable per agent — Claude Code, OpenCode, Cline, Continue).
- **ACL:**
  - To **Provider:** when running a `prompt` handler, an ACL packages the envelope into a chat call without leaking Hooks' internal types.
  - To **CodingAgent:** Hook events extracted from a JSONL Session are translated into Hooks' `HookEvent` objects via an ACL — CodingAgent owns the source schema, Hooks owns the analytic schema.
  - To **SubAgents:** the `SubagentStop` event is fired in Hooks but consumed in SubAgents — the boundary is a published-language `SubagentStopOccurred` event.

---

## 5. SubAgents Context

- **Purpose:** Test inter-agent delegation over A2A — discover AgentCards, submit Tasks, wait for completion, validate Artifacts, and verify delegation chains. §2.4, §5 Phase 2, §7.4.
- **Aggregates:** `A2ATask` — root owning the originating `AgentCard`, the lifecycle `TaskStatus`, the produced `Artifact` collection, and the observed `DelegationChain`.
- **Value Objects:** `AgentCard` (skills, auth, endpoints), `TaskStatus` (`submitted` | `working` | `input-required` | `completed` | `failed` | `canceled`), `Artifact` (typed payload), `DelegationChain` (ordered list of agent URLs/task IDs), `TaskMessage`.
- **Domain Events:** `AgentCardFetched`, `TaskSubmitted`, `TaskStatusChanged`, `TaskCompleted`, `TaskFailed`, `ArtifactProduced`, `DelegationChainObserved`, `SubagentStopObserved`.
- **Repositories:** `AgentCardRegistry` (URL → card), `A2ATaskStore` (active tasks).
- **ACL:**
  - To **MCP:** per §7.4, SubAgents uses MCP for vertical (tool) calls inside a delegated agent. An ACL re-emits MCP `ToolCalled` events as elements of a `DelegationChain` step rather than as opaque MCP events.
  - To **Hooks:** `SubagentStop` events flow in (published language) so SubAgents can correlate them with `TaskStatusChanged`.
  - To **CodingAgent:** trajectory comparison reuses the BFCL matcher, so the boundary surface to ToolCallCorrectness is a published `ActualCall` list.
  - To **framework-internal bridges (LangGraph, CrewAI, AutoGen, OpenAI Agents SDK):** each bridge is an ACL that converts framework state into our `A2ATask`/`DelegationChain` model.

---

## 6. CodingAgent Context

- **Purpose:** Drive coding-agent CLIs (Claude Code, Codex CLI, Aider, OpenCode, Cline, Continue, Copilot CLI), capture their JSONL transcripts, and normalize them into the canonical `Session` schema. §2.5, §7.2, §5 Phase 3.
- **Aggregates:** `CodingAgentSession` — root owning the `CLICommand` invocation, the captured `JSONLTranscript`, the parsed normalized `Session`, and the resulting `SessionUsage`.
- **Value Objects:** `CLICommand` (binary + args + env), `WorkingDirectory`, `JSONLTranscript` (path + raw lines), `NormalizedSession` (`messages`, `tool_calls`, `tool_responses`, `thinking_blocks`, `signature_lengths`, `interrupts`, `hook_events`, `usage`), `ExitStatus`.
- **Domain Events:** `SessionStarted`, `SessionEnded`, `TranscriptCaptured`, `TranscriptParsed`, `SessionUsageReported`, `InterruptObserved`.
- **Repositories:** `CodingAgentDriverRegistry` (one driver per CLI, each owning its JSONL parser), `SessionStore`.
- **ACL:**
  - **Owns the canonical `Session` schema** — every other downstream context (BehavioralMetrics, Hooks for hook-event extraction, ToolCallCorrectness for trajectory comparison) is a Conformist (see context map).
  - To **Provider:** optional LiteLLM Gateway proxying so token/cost data is captured uniformly even when the CLI talks directly to its own backend (§7.2).

---

## 7. Statistics Context

- **Purpose:** Provide non-determinism math: pass@k, TARr@N, Mann-Whitney U, Cliff's delta, Vargha-Delaney A, bootstrap CIs. §2.7, §3.4.
- **Aggregates:** `StatTestRun` — root owning two `Distribution`s (current vs baseline), the chosen test, the resulting `EffectSize`/`PValue`/`ConfidenceInterval`, and the verdict.
- **Value Objects:** `Distribution` (samples), `EffectSize` (Cliff's δ or Vargha-Delaney A), `PValue`, `ConfidenceInterval`, `PassAtK`, `TARScore` (raw vs parsed), `Baseline`.
- **Domain Events:** `RunsCollected`, `BaselineLoaded`, `StatTestComputed`, `RegressionDetected`, `ImprovementDetected`.
- **Repositories:** `BaselineStore` (path-addressable JSON baselines), `DistributionStore`.
- **ACL:** None inbound — Statistics is a Shared Kernel published to Judge, BehavioralMetrics, ToolCallCorrectness. Outbound to **Telemetry:** publishes only typed events; no scipy types leak.

---

## 8. Judge Context

- **Purpose:** Classification-based LLM-as-Judge — apply rubrics, score samples, and require calibration before being trusted. §2.7, §3.4, §8.1.
- **Aggregates:** `Judge` — root owning a configured judge `Model` (via Provider), a `Rubric`, a `CalibrationStatus`, and the produced `JudgmentResult`s.
- **Value Objects:** `Rubric` (criteria + classes), `JudgmentResult` (class + rationale), `CalibrationSample` (input + human label), `CalibrationScore` (Cohen's κ or Krippendorff's α), `JudgePromptTemplate`.
- **Domain Events:** `JudgeConfigured`, `JudgeCalibrated`, `JudgmentScored`, `CalibrationDrifted`, `JudgeRejected` (when calibration fails).
- **Repositories:** `RubricLibrary`, `CalibrationDatasetStore`.
- **ACL:**
  - To **Provider:** judge model calls go through Provider; a Judge-internal ACL ensures classification outputs (not free-form text) reach domain code.
  - To **Statistics:** Judge consumes the Shared Kernel for inter-rater agreement and CI on calibration scores.

---

## 9. Security Context

- **Purpose:** Define the security boundary protecting evaluation hosts: skill supply chain, sandbox enforcement, allowlists, prompt-injection / PII detection, tool approval. §8.2, §8.3, §8 (Tool Approval). The deeper threat model is owned by `security-architect`.
- **Aggregates:** `SecurityPolicy` — root with the active `Allowlist`, the configured `SandboxBackend`, signature verification settings, and audit log.
- **Value Objects:** `SkillSignature`, `SandboxBackend` (`docker` | `k8s` | `proxmox` | `none`), `Allowlist`, `DenyReason`, `PIIDetection`, `PromptInjectionVerdict`, `ToolApprovalDecision`.
- **Domain Events:** `SkillScanned`, `SkillDenied`, `SkillAllowed`, `SandboxStarted`, `SandboxExited`, `PromptInjectionDetected`, `PIIDetected`, `ToolApprovalRequested`, `ToolApprovalGranted`.
- **Repositories:** `AllowlistStore`, `SignatureStore`, `AuditLog`.
- **ACL:**
  - To **Skills:** a Customer/Supplier relationship — Security is the supplier and Skills must conform to its `evaluate(skill) -> Allowed | Denied(reason)` API.
  - To **CodingAgent:** code-execution agents must run inside a `SandboxBackend`; the boundary is a `RunInSandbox` capability surfaced to CodingAgent.
  - To **Provider / aidefence MCP tools:** PII and prompt-injection detection results enter through an ACL converting `aidefence_*` outputs into our `PIIDetection` / `PromptInjectionVerdict` value objects.

---

## 10. Telemetry Context

- **Purpose:** Subscribe to every other context's domain events and turn them into OTel spans, Robot Framework `log.html` snippets, JSON reports, and integrations with Allure/ReportPortal/Grafana. §4.5.
- **Aggregates:** `TraceSession` — root grouping all `Span`s and `Metric`s emitted during one Robot test/suite execution, plus the emitted `ReportArtifact`.
- **Value Objects:** `Span` (OTel-compatible), `Metric` (name + value + unit), `ReportArtifact` (HTML or JSON), `BaselineComparisonPanel`.
- **Domain Events:** `SpanEmitted`, `MetricRecorded`, `ReportGenerated`, `ListenerAttached`.
- **Repositories:** `OTelExporter`, `ReportSink` (HTML / JSON / Grafana / Allure / ReportPortal).
- **ACL:** Telemetry is the **Published Language** consumer — every other context emits typed events that Telemetry's subscribers translate into spans/metrics/report sections. Telemetry never calls back into any context.

---

## 11. BehavioralMetrics Context

- **Purpose:** Compute the issue-#42796 metric pack from a `Session`. §2.6, §3.3, §5 Phase 3.
- **Aggregates:** `BehavioralReport` — root owning the source `Session` reference, the computed metric values, the per-metric thresholds, and the breach verdicts.
- **Value Objects:** `ReadEditRatio`, `EditsWithoutPriorReadPercent`, `ReasoningLoopRate`, `UserInterruptRate`, `StopHookViolation`, `ConventionViolation`, `FirstRunTestPassRate`, `TokenEfficiencyRatio`, `SelfAdmittedErrorRate`, `WriteMutationRatio`, `RepeatedEditsPerFile`, `SimplestWordFrequency`, `MetricThreshold`.
- **Domain Events:** `MetricComputed`, `ThresholdBreached`, `BehavioralReportEmitted`, `BaselineDrifted`.
- **Repositories:** `MetricCalculatorRegistry` (one calculator per metric), `BaselineMetricStore`, `CLAUDEMdRulesRepository` (project-specific convention rules).
- **ACL:**
  - To **CodingAgent:** Conformist — BehavioralMetrics adapts to whatever `Session` schema CodingAgent publishes. If CodingAgent changes its schema, BehavioralMetrics changes; CodingAgent does not bend to BehavioralMetrics' needs.
  - To **Statistics:** Shared Kernel for baseline comparison.
  - To **Hooks:** `Stop-Hook Violation` count is computed from `hook_events` inside a Session — the value object is owned here, but the source events are owned by Hooks (published language).

---

## 12. ToolCallCorrectness Context

- **Purpose:** BFCL-style AST/trajectory matching of expected vs actual tool calls, used by MCP, Skills, and SubAgents. §2.2, §3.1, §5 Phase 1, §6.6.
- **Aggregates:** `BFCLEvaluation` — root owning the evaluation `Category` (`simple` | `parallel` | `multiple` | `multi-turn` | `decide-not-to-act`), the dataset of `Sample`s, the `ExpectedCall`/`ActualCall` pairs, and the resulting `BFCLScore`.
- **Value Objects:** `ExpectedCall`, `ActualCall`, `ASTMatchResult`, `TrajectoryMatchResult`, `BFCLScore`, `Sample`, `Category`.
- **Domain Events:** `EvaluationStarted`, `CallMatched`, `CallMismatched`, `TrajectoryMatched`, `TrajectoryMismatched`, `BFCLScoreComputed`.
- **Repositories:** `BFCLDatasetLoader`, `MatcherRegistry` (per-category matchers).
- **ACL:**
  - **Open Host Service** to MCP, Skills, SubAgents — exposes a stable matcher API (`match_call`, `match_trajectory`) so each consumer translates its native call shape into the published `ActualCall` value object.
  - To **Statistics:** Shared Kernel for pass@k / TAR / bootstrap CI on per-sample correctness.
