# Context Map — robotframework-agentguard

The diagram below shows the integration patterns between the 12 bounded contexts. Pattern names follow Eric Evans / Vaughn Vernon vocabulary:

- **SK** — Shared Kernel
- **CS** — Customer / Supplier (downstream depends on upstream's roadmap)
- **CF** — Conformist (downstream adopts upstream's model unchanged)
- **OHS** — Open Host Service (upstream publishes a stable API for many downstreams)
- **PL** — Published Language (typed events both sides agree on)
- **ACL** — Anti-Corruption Layer (translation at the boundary)

Citations point to `docs/research/research.md`.

## Mermaid Map

```mermaid
flowchart LR
    PR[Provider]
    MC[MCP]
    SK_C[Skills]
    HK[Hooks]
    SA[SubAgents]
    CA[CodingAgent]
    ST[Statistics]
    JD[Judge]
    SE[Security]
    TL[Telemetry]
    BM[BehavioralMetrics]
    TC[ToolCallCorrectness]

    %% Provider as Shared Kernel
    PR ===|SK| MC
    PR ===|SK| SK_C
    PR ===|SK| JD
    PR ===|SK| CA
    PR ===|SK| SA

    %% Statistics as Shared Kernel
    ST ===|SK| JD
    ST ===|SK| BM
    ST ===|SK| TC

    %% Security gates Skills
    SE -->|CS supplier| SK_C
    SE -->|CS supplier| CA

    %% CodingAgent feeds BehavioralMetrics — conformist
    CA -->|CF: Session schema owner| BM

    %% ToolCallCorrectness as Open Host Service
    TC -->|OHS| MC
    TC -->|OHS| SK_C
    TC -->|OHS| SA

    %% SubAgents uses MCP vertical, A2A horizontal §7.4
    MC -->|ACL: tool axis| SA

    %% Hooks <-> SubAgents via published language
    HK -.->|PL: SubagentStop| SA
    SA -.->|PL: TaskStatus| HK

    %% Hooks <-> CodingAgent via published language
    CA -.->|PL: hook_events in Session| HK

    %% Telemetry as Published Language consumer (one-way)
    SK_C -.->|PL events| TL
    HK -.->|PL events| TL
    SA -.->|PL events| TL
    CA -.->|PL events| TL
    MC -.->|PL events| TL
    BM -.->|PL events| TL
    TC -.->|PL events| TL
    JD -.->|PL events| TL
    SE -.->|PL events| TL
    PR -.->|PL events| TL
    ST -.->|PL events| TL

    %% Phase 4-A/B/C — TestHarness / MCPScenario (proposed by ADR-021).
    TH[TestHarness / MCPScenario]
    MC -->|CS supplier: ServerHandle, Call MCP Tool| TH
    CA -->|CS supplier: Driver, Session| TH
    SK_C -.->|CS supplier (extension): Skill body as system msg| TH
    TC -.->|OHS: optional per-call AST validation| TH
    SE -->|CS supplier: Generated Robot suite scan| TH
    JD -.->|OHS: validates expected_outcome| TH
    ST -->|SK: Mann-Whitney + Cliff δ + pass@k| TH
    TH -.->|PL events: ScenarioStarted, ToolCallRecorded, ScenarioCompleted| TL
```

## Pattern Catalogue

### Shared Kernels

- **Provider ↔ {MCP, Skills, Judge, CodingAgent, SubAgents}** — every context that needs an LLM agrees on Provider's `Model`, `ChatMessage`, `ToolDefinition`, `ChatResponse`, `Cost`, `ProviderCapability`. Changes to these types require coordination across all five. Provider is intentionally generic (default LiteLLM, §4.1, §4.4) so the kernel surface stays small.
- **Statistics ↔ {Judge, BehavioralMetrics, ToolCallCorrectness}** — `Distribution`, `EffectSize`, `ConfidenceInterval`, `PassAtK`, `TARScore`, `Baseline` are shared types. Statistics has no scipy types in its public surface so the kernel is pure.

### Customer / Supplier — Security gates Skills (and CodingAgent)

- **Security → Skills:** Skills is the customer; Security is the supplier. Skills must call `SecurityPolicy.evaluate(skill)` before any `SkillLoaded` event is allowed to fire. Per §8.3 (Snyk *ToxicSkills*, *ClawHavoc*), unsigned third-party skills default to **deny**. Security publishes the rules; Skills bends to fit them.
- **Security → CodingAgent:** code-execution agents must run inside a `SandboxBackend` (§8.2 — Inspect AI sandbox toolkit). CodingAgent calls `RunInSandbox` and refuses to run a coding-agent CLI when `SandboxBackend == none` and `--allow-code-execution` is not set.

### Conformist — CodingAgent owns the Session schema

- **CodingAgent → BehavioralMetrics:** CodingAgent owns the canonical `NormalizedSession` schema (`messages`, `tool_calls`, `tool_responses`, `thinking_blocks`, `signature_lengths`, `interrupts`, `hook_events`, `usage` — §7.2). BehavioralMetrics is a **Conformist**: when CodingAgent adds a new CLI driver and the schema gains a new field, BehavioralMetrics adapts. The reverse never happens — BehavioralMetrics never asks CodingAgent to add a field. This keeps the JSONL parser logic single-sourced inside per-CLI drivers.

### Open Host Service — ToolCallCorrectness exposes BFCL matchers to many

- **ToolCallCorrectness → {MCP, Skills, SubAgents}:** the BFCL AST matcher and trajectory matcher are surfaced through a stable API (`match_call`, `match_trajectory`, `score_dataset`) that takes published `ActualCall` / `ExpectedCall` value objects (§3.1, §6.6). MCP, Skills, and SubAgents each translate their native call shape into `ActualCall`. ToolCallCorrectness does not need to know whether the call came from a tool invocation, a graded skill prompt, or an A2A delegated trajectory — only that the published shape is satisfied.
- **TestHarness ↔ ToolCallCorrectness (ADR-021):** TestHarness's per-call `ExpectedToolCall(name, min_calls, max_calls, required_params)` is *aggregate semantics*; ToolCallCorrectness's `ExpectedCall` is *per-call AST equality*. Both coexist — users reach for the aggregate shape when they only know multiplicity bounds, and the per-call shape when they can name the exact call to expect. TestHarness optionally calls into ToolCallCorrectness to upgrade the looser hit-rate gate to strict per-call AST equality (e.g., for replays of a known-good run).

### TestHarness / MCPScenario as workflow orchestrator (ADR-021, proposed)

- **MCP → TestHarness (Customer/Supplier):** MCP is the supplier; TestHarness is the customer. TestHarness wraps MCP's `ServerHandle` with a recording overlay so every `Call MCP Tool` invoked during a `Run MCP Scenario` emits a `ToolCallRecorded` event into the per-suite collector. MCP keeps its narrow protocol responsibility; TestHarness owns the recording-and-aggregation layer. Tracked recording is opt-in: callers who don't `Start Tracked MCP Session` keep the existing behaviour.
- **CodingAgent → TestHarness (Customer/Supplier):** TestHarness uses any `CodingAgentDriver` (LocalDriver, ClaudeCodeDriver, …) as the autonomous-agent loop that drives the scenario prompt. The `Session` returned by a driver is mapped into a `ScenarioResult` via a tiny ACL — fields drop, `success` is derived from `tool_response.is_error`, the rest carries through.
- **Security → TestHarness (Customer/Supplier):** when TestHarness's `Generated Robot Suite Should Pass` keyword is invoked, Security's scanner pre-flights the agent-emitted suite per ADR-006 and the sandbox per ADR-013 gates any actual execution. Default mode is `--dryrun` (no execution).
- **Stats → TestHarness (Shared Kernel):** the cross-scenario comparison keywords (`Tool Hit Rate Distribution Should Stochastically Dominate`, `Compare Scenarios Pass Rate`) reach into Statistics for `mann_whitney_u`, `cliffs_delta`, `pass_at_k`. No new statistics math.
- **TestHarness → Telemetry (Published Language):** every domain event (`ScenarioStarted`, `ToolCallRecorded`, `ScenarioCompleted`, `ArtifactProduced`, `ScenarioBaselineDrifted`) is an OTel span tagged with `scenario.id` so traces from multiple runs aggregate cleanly in Grafana / Jaeger / Honeycomb.
- **TestHarness ⇄ Skills (extension, Phase 4-B):** when a scenario is run with `skill=<Skill>`, the skill's body is injected as the system message in the driver's prompt. Skills' invariants (frontmatter validation, security scan) still apply. The hit-rate then measures "given this skill is loaded, did the agent invoke the right MCP tools?" — a useful generalization unique to the unified-harness vision.

### Vertical (MCP) and Horizontal (A2A) Split

- **MCP → SubAgents:** per §7.4 ("Build with ADK, equip with MCP, communicate with A2A"), MCP is the **vertical** axis (agent ↔ tool) and A2A is the **horizontal** axis (agent ↔ agent). The MCP context exposes its `ToolCalled` events through an ACL into SubAgents, where they become steps inside a `DelegationChain`. SubAgents itself owns the A2A protocol semantics (`AgentCard`, `A2ATask`, `Artifact`) and never reaches into MCP transport details.

### Published Language — Hook ↔ SubAgent ↔ CodingAgent

- **Hooks ↔ SubAgents:** the `SubagentStop` hook event is the contract. Hooks publishes `SubagentStopOccurred`; SubAgents subscribes to correlate it with `TaskStatusChanged`.
- **CodingAgent ↔ Hooks:** the `hook_events` field of a `NormalizedSession` is the contract. Hooks defines the `HookEvent` value object; CodingAgent emits them inside Session events without hard-coupling to Hooks' analytic types — the boundary translation happens via a small ACL inside Hooks.

### Published Language — every context emits to Telemetry

- All eleven non-Telemetry contexts emit typed domain events that Telemetry consumes (§4.5). Telemetry never calls back. New contexts get observability for free by emitting events conformant to a minimal `DomainEvent` envelope (`type`, `timestamp`, `payload`, `context_name`).

## Summary of the Three Most Important Relationships

1. **Provider as Shared Kernel for five core consumers.** Anything that needs an LLM goes through Provider. This is the single most important integration choice — it makes the library provider-agnostic by construction (§4.1) and lets us swap LiteLLM for direct adapters without disturbing downstream code.
2. **CodingAgent is the conformist source for BehavioralMetrics, the gatekeeper for the #42796 metric pack.** Locking the canonical `Session` schema inside CodingAgent ensures one parser per CLI and one consumer of that parser — the metric pack. Adding Codex CLI or Aider becomes a driver change, not a metric change (§7.2, §2.6).
3. **Security is a hard Customer/Supplier upstream of Skills (and CodingAgent), enforcing default-deny for unsigned skills and required sandboxing for code execution** (§8.2, §8.3). This is non-negotiable per the *ToxicSkills* and *ClawHavoc* findings, and the context-map encodes it as a directed dependency rather than an optional feature.
