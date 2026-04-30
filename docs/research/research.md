# Robot Framework Library for Testing Agent Skills, Hooks, SubAgents, and MCP Servers

## A Research Report and Implementation Plan

---

## 1. Executive Summary

This report proposes the design and phased implementation of an open, technology-agnostic **Robot Framework library** (working name: `robotframework-AgentTestLibrary`, or `RFAgentTest`) for testing the four primary building blocks of modern agentic coding tools: **Agent Skills**, **Hooks**, **SubAgents**, and **MCP (Model Context Protocol) Servers**. The library targets Robot Framework's native keyword-driven syntax so that QA engineers — not just ML researchers — can express, run, and report on agent evaluations using the same suite/test/keyword model they already use for web, API, and RPA testing.

The recommendation is to build on adopted open standards (MCP from Anthropic, Agent Skills spec at agentskills.io, A2A from the Linux Foundation, OpenAI-compatible Chat Completions, and LiteLLM as the provider abstraction layer) rather than coupling to any single vendor. The library should integrate (not replace) the strongest existing harnesses — **Inspect AI** (UK AISI), **mcp-eval / pytest-mcp**, **MCP Inspector**, **Berkeley Function Calling Leaderboard (BFCL)** evaluation rules, and the metric catalog popularized by Stella Laurenzo's analysis in `anthropics/claude-code#42796` — exposing them as first-class Robot Framework keywords with deterministic and statistical assertions.

Phase 1 delivers Agent Skills and MCP Server testing (highest immediate demand, mature standards). Phase 2 adds Hooks and SubAgent testing. Phase 3 adds a coding-agent harness (Claude Code, Codex CLI, Aider, OpenCode, Cline, Continue) and full statistical-evaluation tooling.

---

## 2. Landscape Analysis of Existing Tools and Standards

### 2.1 MCP Server Testing

The Model Context Protocol ecosystem already has a layered testing stack:

- **MCP Inspector** (`modelcontextprotocol/inspector`) — the official browser-based debugger. It runs over `npx @modelcontextprotocol/inspector`, exposes a React UI on port 6274 plus a proxy on port 6277, and supports stdio, SSE, and streamable-HTTP transports. It also ships a **CLI mode** (`--cli`) that can list tools/resources/prompts and call tools with JSON arguments — the most natural surface for CI integration and protocol-compliance testing.
- **mcp-eval** (`lastmile-ai/mcp-eval`, also published as `pytest-mcp` on PyPI by Sarmad Qadri) — a pytest-style, async, task-based framework built on `mcp-agent`. It is currently the most complete OSS evaluation framework for MCP. It auto-collects metrics (latency, token usage, cost, tool calls), supports rich assertions (e.g. `plan_is_efficient` using an LLM judge), can auto-generate baseline test suites, and emits OpenTelemetry traces and JSON reports.
- **mcp-testing-framework** (Tosin Akinosho's fork of `mcp-client-cli`) — adds functional, security, performance, and CI-template tests; intended to be installed once and run via `mcp-test --test-mcp-servers`.
- **FastMCP in-memory testing** — pattern documented at gofastmcp.com: instantiate `FastMCP` in-process, bind a `Client(server)` directly, and run pytest with `pytest-asyncio` and `inline-snapshot`/`dirty-equals`. This is the deterministic baseline for any MCP server testing.
- **mcpx-eval** (mcp.run) — open-ended LLM-as-judge framework with a structured prompt template (`<settings>`, `<prompt>`, `<output>`, `<check>`, `<expected-tools>`).
- **MCPEval** and **MCP-RADAR** (research) — define automated task generation, ground-truth trajectory comparison, and a five-dimensional benchmark (answer accuracy, tool selection efficiency, computational resource efficiency, parameter construction accuracy, execution speed).
- **Arm Learning Path "Automate MCP server testing using Pytest and Testcontainers"** demonstrates JSON-RPC-over-stdio integration tests in containers — the canonical way to test MCP servers end-to-end in CI.

**Implication:** A Robot Framework library should not re-implement protocol parsing. It should sit on top of the MCP Python SDK / FastMCP client and expose Robot keywords that wrap (a) protocol-compliance probes, (b) tool/resource/prompt invocations, (c) trajectory capture, and (d) metric computation.

### 2.2 Agent Skill Testing

The **Agent Skills specification** (published by Anthropic on December 18, 2025 at `agentskills.io/specification`) defines a portable folder format: a `SKILL.md` with YAML frontmatter (`name`, `description`, optional `allowed-tools`) plus optional `scripts/`, `references/`, and `assets/` directories. Within ~90 days the spec was adopted by 32 tools, including Claude Code, OpenAI Codex CLI/ChatGPT, VS Code/GitHub Copilot, Google Gemini CLI, JetBrains Junie, AWS Kiro, Block Goose, Sourcegraph Amp, Cursor, Snowflake, Databricks, ByteDance TRAE, and Mistral. Different tools install skills in different paths (`.claude/skills/`, `.agents/skills/`, `~/.gemini/antigravity/skills/`), so any cross-vendor skill testing must abstract the discovery path.

Existing skill-evaluation work:

- **`manykarim/robotframework-agentskills`** itself ships an evaluation harness called **`rf-skill-eval`** (in `src/rf_skill_eval/` with an `eval/` directory). Its README documents `uv run rf-skill-eval doctor` and `bash scripts/eval-local.sh`, which grade each skill under controlled Claude Code sessions using a `CLAUDE_CODE_OAUTH_TOKEN` and produce a scorecard. The repo also contains a pytest test suite (`tests/test_keyword_builder.py`, `tests/test_testcase_builder.py`, `tests/test_resource_architect.py`, `tests/test_drift_detection.py`, `tests/test_libdoc_search.py`, `tests/test_marketplace_validation.py`). This is a useful precedent but is currently pytest- and Claude-Code-specific.
- **Inspect AI** (UK AISI, `inspect_ai`) — Python framework with the `Task → Solver → Scorer` triad, multi-provider model layer (OpenAI, Anthropic, Google, Groq, Mistral, xAI, Bedrock, Azure, Together, vLLM, Ollama, llama.cpp), built-in tools (`bash`, `python`, `text-edit`, `web_search`, `web_browser`, `computer`), MCP/Custom tool support, ReAct and multi-agent patterns, sandbox toolkit (Docker, K8s, Proxnox), Tool Approval, and `inspect-evals` with 200+ evals. It is the de-facto OSS standard for safety-grade evaluation and is used by METR, Apollo Research, and other AISIs.
- **OpenAI Evals**, **Anthropic Evals**, **LangSmith**, **Braintrust**, **Galileo**, **Langfuse**, **W&B Weave**, **Confident AI** — production observability+eval platforms that all converge on the same primitives: dataset, scorer (deterministic or LLM-as-judge), trace, leaderboard.
- **Berkeley Function Calling Leaderboard (BFCL)** — uses an Abstract Syntax Tree (AST) match against expected tool calls instead of executing them, scaling to thousands of functions and covering single-turn, parallel, multiple, multi-turn, and "decide-not-to-act" categories. This evaluation method has been ported into Inspect AI as a first-class evaluation.
- **AgentBench**, **GAIA**, **ToolBench**, **API-Bank**, **τ-Bench**, **ToolSandBox**, **StableToolBench** — academic benchmarks; many rely on LLM-simulated users which add noise.

### 2.3 Hook Testing

Claude Code's **Hooks reference** documents 12 lifecycle events: `UserPromptSubmit`, `UserPromptExpansion`, `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PostToolBatch`, `Notification`, `Stop`, `SubagentStop`, `PreCompact`, `SessionStart`, `ConfigChange`. Hooks are invoked via four handler types: `command` (shell), `http` (POST JSON; new Feb 2026), `prompt` (LLM-evaluated, used for Stop/SubagentStop), and `agent`. Communication is JSON-on-stdin / JSON-or-text-on-stdout, with **exit code 2 = block** semantics: a `PreToolUse` hook exiting 2 stops the tool; a `Stop` hook exiting 2 forces Claude to keep working. Decision objects include `{"decision": "block"|"allow"|"escalate", "reason": ...}` and `permissionDecision` for finer permission gating. The same hook semantics are surfaced by the Claude Agent SDK and partially mirrored by OpenCode (issue `anomalyco/opencode#12472` discusses native parity), GitHub Copilot extensions, Cline, and Continue.

There is, today, **no widely adopted automated test harness for hooks**. Most projects (e.g. `disler/claude-code-hooks-mastery`, GitButler's `but claude pre-tool` integration) ship hooks as Python/bash scripts and manually validate behavior. This is the largest gap in the ecosystem and one a Robot Framework library can fill cleanly: a hook is, after all, a deterministic JSON-in/JSON-out process with an exit code — exactly the kind of thing keyword-driven tests excel at.

### 2.4 SubAgent Testing

Multi-agent frameworks each have their own delegation primitive: CrewAI uses `Crew/Agent/Task` with role-based delegation; LangGraph uses graph nodes with explicit state transitions; AutoGen uses conversation-shaped agent topologies; OpenAI Agents SDK uses `Agents/Handoffs/Guardrails`. Claude Code surfaces sub-agent execution through the `SubagentStop` hook event, the `area:subagents` issue label, and skill/agent frontmatter (`name:`, `hooks:`). At the protocol level, **A2A (Agent2Agent)** — open-sourced by Google in April 2025, donated to the Linux Foundation, and reaching 1.0 in 2026 — provides a vendor-neutral way for one agent to discover (`AgentCard`), authenticate against, and delegate work to another via JSON-RPC and Server-Sent Events, with a `task` lifecycle and `artifacts` as outputs. LiteLLM has added an `A2AClient` and an A2A Gateway, including bridges for LangGraph, Vertex AI Agent Engine, Azure AI Foundry, Bedrock AgentCore, and Pydantic AI.

Today, sub-agent testing is largely framework-internal (LangGraph time-travel, CrewAI replay, AutoGen state introspection). A standardized, framework-agnostic test harness over the A2A protocol — capturing AgentCards, asserting on task lifecycles, validating artifacts, and verifying delegation chains — does not yet exist as a Robot Framework library and is a clear opportunity.

### 2.5 Coding Agent Evaluation

Established benchmarks: **HumanEval**, **MBPP**, **LiveCodeBench**, **SWE-bench**, **SWE-bench Lite**, **SWE-bench Verified** (the human-validated 500-problem subset), and the **Aider benchmark**. Reported numbers are typically **pass@1** (single-attempt resolved rate), sometimes **pass@3** or **pass@N**. Independent research (Yang et al., *SWE-Bench+*) has shown that ~33% of "successful" SWE-bench patches in the original set involved solution leakage, dropping SWE-Agent+GPT-4's effective resolution rate from 12.47% to 3.97%, which is why SWE-bench Verified now dominates and why **first-run test pass rate on the project's own pre-existing test suite** (Aider's "plausible solution" criterion) is increasingly the most defensible metric.

### 2.6 The Metric Catalog from `anthropics/claude-code#42796`

Stella Laurenzo's analysis (April 2026), corroborated by Ben Vanik with a Pearson r=0.971 correlation between thinking-block signature length and thinking content length over 7,146 paired samples, introduced a **machine-readable behavioral metric set** that is rapidly being treated as a de-facto industry standard for coding-agent regression testing. The full set, with the values measured between Jan 30 and April 1, 2026 across 6,852 sessions and 234,760 tool calls:

| Metric | Definition | "Good" baseline | "Degraded" |
|---|---|---|---|
| **Read:Edit ratio** | File reads divided by file edits | 6.6 | 2.0 |
| **Edits without prior Read** | % of edits to files not in recent read history | 6.2% | 33.7% |
| **Reasoning loops per 1K tool calls** | Self-corrections ("oh wait", "actually", "let me reconsider") | 8.2 | 26.6 |
| **User interrupts per 1K tool calls** | Escape-key / `[Request interrupted by user]` events | 0.9 | 11.4 |
| **Stop-hook violations** | Triggers of a `stop-phrase-guard.sh` matching ownership-dodging, premature-stopping, permission-seeking, known-limitation labeling, session-length excuses | 0 in baseline; 173 in 17 degraded days (≈10/day) | 173 |
| **Convention violation rate** | Edits that violate the project CLAUDE.md (abbreviated names, wrong cleanup pattern, banned temporal phrasing) | low | rising |
| **First-run test pass rate** | `pass@1` on the project's own pre-existing test suite | reference | reference |
| **Token usage efficiency** | Output tokens or API requests per user prompt of equivalent work | reference | 64× output, 80× requests |
| **Self-admitted errors per 1K tool calls** | Unprompted "you're right, that was lazy/wrong/sloppy" admissions | 0.1 | 0.5 |
| **Write-vs-Edit ratio** | % of mutations done as full-file `Write` rather than surgical `Edit` | 4.9% | 11.1% |
| **Repeated edits per file** | Edits to the same file 3+ times in rapid succession | low | high |
| **"Simplest" word frequency** | Per 1K tool calls — proxy for cheap-action shortcuts | 2.7 | 6.3 |

These metrics are computable from session JSONL files alone, making them usable in CI without any vendor cooperation, and they are exactly the metrics the proposed library should expose as Robot Framework keywords.

### 2.7 Non-Deterministic Testing — State of the Art

Multiple peer-reviewed papers (Atil et al. *Non-Determinism of "Deterministic" LLM Settings*; Song et al. *The Good, The Bad, and The Greedy*; *Beyond Reproducibility: Token Probabilities Expose Large Language Model Nondeterminism*) confirm that even with `temperature=0` and fixed seeds, LLMs vary by up to 15% across runs and 70% best-vs-worst due to floating-point rounding in fused attention/normalization kernels and to shared-batch effects on cloud providers. The accepted statistical machinery for evaluating differences between two non-deterministic agents/runs:

- **Mann-Whitney U / Wilcoxon** (non-parametric, no median or distribution assumption) — tests stochastic dominance.
- **Cliff's delta** and **Vargha-Delaney's A** — effect-size measures bounded in [-1, 1] / [0, 1].
- **Bootstrap confidence intervals** for any pass-rate or mean metric.
- **Total Agreement Rate** (`TARr@N` for raw output, `TARa@N` for parsed answers) — proposed by Atil et al. as a determinism-quantifying metric.
- **pass@k** — standard for code generation.
- **LLM-as-Judge** — Braintrust, LangSmith, mcpx-eval all use chain-of-thought-prompted classification (more reliable than numeric ratings), with rubrics, pairwise comparison, single-point scoring, and reference-based grading. Best practice (Hamel Husain, Braintrust): keep the judge classification-based, validate it against human labels first, and combine with deterministic checks rather than replacing them.

---

## 3. Proposed Metrics Framework

The library will expose a **canonical metric catalog** organized into four orthogonal axes. Each metric has a Robot Framework keyword, a precise definition, a unit, and a recommended assertion strategy (deterministic vs. statistical).

### 3.1 Tool-Call Correctness Metrics (BFCL-derived, AST-based)

| Metric | Keyword | Strategy |
|---|---|---|
| Tool name match | `Tool Call Should Match Name` | Exact string |
| Tool argument AST match | `Tool Call Arguments Should Match` | AST equality, ignores whitespace/order |
| Required parameters present | `Required Parameters Should Be Present` | Schema validation against the MCP/OpenAI tool schema |
| Parallel tool calls correct | `Parallel Tool Calls Should Match` | Multiset equality of tool calls in one turn |
| Tool sequence (trajectory) match | `Tool Sequence Should Match` | Ordered subsequence match, with optional wildcards |
| Decide-not-to-act correctness | `Should Not Call Any Tool` | Asserts no tool was invoked when ground truth says none |

### 3.2 Tool-Execution and Outcome Metrics

| Metric | Keyword | Strategy |
|---|---|---|
| Tool execution success rate | `Tool Execution Success Rate Should Be Above` | Deterministic threshold |
| Output schema validity | `Tool Output Should Match Schema` | JSON Schema |
| Output semantic equivalence | `Tool Output Should Be Semantically Equal` | LLM-as-Judge with rubric |
| Latency (p50/p95) | `Tool Latency Should Be Below` | OpenTelemetry-backed |
| Token cost / 1K calls | `Token Cost Should Be Below` | LiteLLM cost tracker |

### 3.3 Behavioral Metrics (issue #42796 catalog)

All measured over a session JSONL transcript. The library will ship a `Session.parse_jsonl` keyword and per-metric calculators.

| Metric | Keyword | Default threshold |
|---|---|---|
| Read:Edit ratio | `Read Edit Ratio Should Be Above` | ≥ 4.0 |
| Edits without prior Read | `Edits Without Prior Read Percent Should Be Below` | ≤ 10% |
| Reasoning loops per 1K | `Reasoning Loops Per 1K Tool Calls Should Be Below` | ≤ 12 |
| User interrupts per 1K | `User Interrupts Per 1K Should Be Below` | ≤ 2 |
| Stop-hook violations | `Stop Hook Violations Should Be Zero` | 0 |
| Convention violations | `Convention Violation Rate Should Be Below` | project-defined |
| First-run test pass rate | `First Run Test Pass Rate Should Be Above` | ≥ 0.9 |
| Token efficiency | `Token Usage Per Prompt Should Be Below` | baseline × 1.5 |
| Self-admitted errors per 1K | `Self Admitted Errors Per 1K Should Be Below` | ≤ 0.2 |
| Write-vs-Edit ratio | `Write Mutation Ratio Should Be Below` | ≤ 6% |

### 3.4 Statistical / Non-Deterministic Metrics

Designed to be the natural assertion API for any of the above when they are computed across N runs.

| Keyword | Behavior |
|---|---|
| `Run N Times` | Iteration helper that captures all metric values |
| `Pass At K Should Be Above` | pass@k computation per HumanEval convention |
| `Total Agreement Rate Should Be Above` | TARr@N or TARa@N |
| `Mann Whitney U Should Show Improvement` | Two-sample test against a baseline run |
| `Cliffs Delta Should Be At Least` | Effect-size assertion |
| `Bootstrap Confidence Interval Should Contain` | CI assertion for mean/proportion |
| `LLM Judge Should Score At Least` | Classification-based LLM-as-Judge with rubric and judge model selectable via LiteLLM |

---

## 4. Library Architecture

### 4.1 Design Principles

1. **Provider-agnostic by default.** All LLM access flows through a `LLMProviderAdapter` that defaults to **LiteLLM** (100+ providers, OpenAI-compatible interface, mapped exception types, MLflow/Langfuse/Helicone callbacks). Direct adapters for Anthropic, OpenAI, Google, Mistral, Cohere, Ollama, vLLM, llama.cpp, and LM Studio are provided when special features (extended thinking, structured outputs, grounding) leak through the abstraction.
2. **Standards-first.** The library speaks MCP, A2A, OpenAI Chat Completions, and the Agent Skills `SKILL.md` format directly. It does not invent new file formats.
3. **Robot Framework-native.** Each capability is exposed as one or more keywords that are usable from `.robot` files. State is held in a Robot Framework Library class (`PythonLibCore`-based, library scope `TEST` or `SUITE`).
4. **Composable.** Sub-libraries (`MCP`, `Skills`, `Hooks`, `SubAgents`, `Agent`, `Stats`) can be imported individually so a team only loads what it needs.
5. **Deterministic where possible, statistical where needed.** In-memory MCP transport and AST-based BFCL matching for unit-style determinism; bootstrap/Mann-Whitney/LLM-judge for end-to-end behavioral tests.
6. **Trace-first.** OpenTelemetry traces are emitted by default (compatible with mcp-eval) and rendered into the Robot Framework `log.html` via a custom listener.

### 4.2 Package Layout

```
robotframework-agenttest/
├── src/AgentTest/
│   ├── __init__.py            # Top-level Library entry point
│   ├── mcp/                   # MCP server testing
│   │   ├── MCPLibrary.py      # Connect, list tools, call tool, validate transport
│   │   ├── transports.py      # stdio / SSE / streamable-http / in-memory
│   │   └── inspector_cli.py   # Wrap @modelcontextprotocol/inspector --cli
│   ├── skills/                # Agent Skills testing
│   │   ├── SkillsLibrary.py   # Load SKILL.md, validate frontmatter, run grader
│   │   └── grader.py          # Wraps Inspect AI Tasks/Solvers/Scorers
│   ├── hooks/                 # Hook testing (Phase 2)
│   │   └── HooksLibrary.py    # Synthesize stdin JSON, capture exit code+stdout
│   ├── subagents/             # SubAgent testing (Phase 2)
│   │   └── A2ALibrary.py      # AgentCard, task lifecycle, artifact assertions
│   ├── agent/                 # Coding-agent harness (Phase 3)
│   │   ├── AgentLibrary.py    # CLI driver for Claude Code, Codex, Aider, etc.
│   │   └── session.py         # JSONL parser + #42796 metric calculators
│   ├── providers/             # LLM provider adapters
│   │   ├── litellm_adapter.py
│   │   ├── ollama_adapter.py
│   │   └── ...
│   ├── stats/                 # Non-determinism utilities
│   │   ├── StatsLibrary.py    # Mann-Whitney, Cliff's delta, bootstrap, pass@k, TAR
│   │   └── judge.py           # LLM-as-Judge with rubrics
│   ├── listeners/
│   │   └── OTelListener.py    # Robot listener that injects OTel traces into log
│   └── resources/
│       ├── AgentTest.resource # Canonical resource file for users
│       └── schemas/           # JSON schemas (MCP, Agent Skills, A2A AgentCard)
├── atest/                     # Acceptance tests for the library itself
│   ├── mcp/
│   ├── skills/
│   └── stats/
├── tests/                     # pytest unit tests
└── docs/
```

### 4.3 Core Library Class Design

```python
from robot.api.deco import keyword, library
from robotlibcore import DynamicCore

@library(scope="SUITE", auto_keywords=False, version="0.1.0")
class AgentTest(DynamicCore):
    """Top-level Robot Framework library for agent testing."""

    def __init__(self,
                 provider="litellm",       # "litellm" | "anthropic" | "openai" | "ollama" | ...
                 model="anthropic/claude-sonnet-4-5",
                 transport="auto",         # for MCP: "stdio" | "sse" | "http" | "memory" | "auto"
                 telemetry=True,
                 judge_model=None,
                 baseline_path=None):
        self.provider = build_provider(provider, model)
        self.judge = build_judge(judge_model or model)
        libraries = [
            MCPKeywords(self.provider),
            SkillsKeywords(self.provider, self.judge),
            HooksKeywords(),
            SubAgentKeywords(self.provider),
            AgentKeywords(self.provider),
            StatsKeywords(),
        ]
        DynamicCore.__init__(self, libraries)
```

### 4.4 Provider Abstraction

```python
class LLMProviderAdapter(Protocol):
    def chat(self, messages, tools=None, **kwargs) -> ChatResponse: ...
    def stream(self, messages, **kwargs) -> Iterator[Chunk]: ...
    def cost(self, response) -> Decimal: ...
    def supports(self, capability: str) -> bool: ...
```

LiteLLM is the default implementation; specific providers receive thin subclasses that surface vendor-specific knobs (Anthropic extended thinking, OpenAI structured outputs, Gemini grounding, Bedrock cross-region inference). Coding agents (Claude Code CLI, Codex CLI, Aider, OpenCode, Cline, Continue, GitHub Copilot CLI) are wrapped via a `CodingAgentDriver` that subprocesses the CLI, captures the JSONL session log, and parses it into the canonical session schema used by the #42796 metric calculators.

### 4.5 Listener and Reporting

A custom Robot Framework listener (`OTelListener`) tails the OpenTelemetry exporter (mcp-eval-compatible spans) and embeds key metrics, tool calls, and judge rationales as `log.html` HTML snippets. Final HTML reports include a per-test scorecard, per-suite metric trends, and a baseline comparison panel that runs Mann-Whitney/Cliff's-delta against any previous run stored at `baseline_path`. Output is also written as JSON to integrate with Allure, ReportPortal, Grafana (the existing `manykarim/robot-framework-reporting` stack with PostgreSQL/InfluxDB/Grafana fits naturally), and CI dashboards.

---

## 5. Implementation Plan and Phasing

### Phase 1 — Agent Skills + MCP Server testing (≈ 3 months)

**Goal:** Ship a usable 0.x release covering the two highest-priority surfaces.

1. **Bootstrapping (week 1–2).** Repo, pyproject, CI, RF 7.x compatibility (RETURN, IF/ELSE, TRY/EXCEPT), `PythonLibCore`-based library skeleton, OTel listener stub.
2. **MCP module (week 3–8).**
   - Wrap FastMCP `Client` for stdio/SSE/streamable-HTTP/in-memory transports.
   - Wrap MCP Inspector CLI (`npx @modelcontextprotocol/inspector --cli`) for protocol-compliance assertions in CI.
   - Implement `MCP Inspector Should Connect`, `List MCP Tools`, `Call MCP Tool`, `MCP Tool Output Should Match Schema`, `MCP Server Should Implement Capabilities`.
   - Re-use `mcp-eval` task primitives where possible — the library imports `mcp_eval` and exposes its `Test`/`Assertion` decorators behind Robot Framework keywords. Where `mcp-eval` requires Python decorators, the library generates equivalent `.robot` keywords from registered task definitions.
   - Implement BFCL-style AST matching for tool calls (port the rules from `inspect_evals/bfcl`).
3. **Agent Skills module (week 6–12).**
   - `SKILL.md` parser, frontmatter validator (`name`, `description`, optional `allowed-tools`).
   - Discovery across the four most common install paths (`.claude/skills/`, `.agents/skills/`, `~/.gemini/.../skills/`, `~/.codex/skills/`).
   - Skill grader keyword that runs an Inspect AI `Task` against each skill: load skill, ask the model a representative prompt set, capture trajectory, score with rubric + LLM-as-Judge.
   - Mirror the scorecard format already used by `manykarim/robotframework-agentskills`'s `rf-skill-eval`.
   - Convention-violation scorer (regex/AST checks against project CLAUDE.md rules).
4. **Stats module (week 10–12).** scipy-backed Mann-Whitney/Wilcoxon, Cliff's delta, Vargha-Delaney A, bootstrap CIs, pass@k, TARr@N/TARa@N, classification-based LLM-as-Judge with model selectable via LiteLLM.

**Phase 1 deliverables:** PyPI release `robotframework-agenttest 0.1`, ten reference `.robot` suites, integration with the Grafana reporting stack, GitHub Actions template.

### Phase 2 — Hooks + SubAgents (≈ 2 months)

1. **Hooks module.**
   - `Synthesize Hook Input` keyword that builds the canonical Claude Code JSON envelope (`tool_name`, `tool_input`, `tool_response`, `transcript_path`, `cwd`, `session_id`, `stop_hook_active`) for each event type.
   - `Run Hook Command`, `Run Hook HTTP`, `Run Hook Prompt`, `Run Hook Agent` — drive the four handler types and capture exit code, stdout JSON, stderr.
   - Decision assertions: `Hook Should Block`, `Hook Should Allow`, `Hook Should Inject Context`, `Hook Decision Should Be`, `Hook Should Modify Tool Input To`.
   - Loop-safety: detect `stop_hook_active` and infinite-Stop-loop antipatterns.
   - Cross-tool compatibility shim: same keywords work against Claude Code hooks, OpenCode plugin hooks, GitHub Copilot extension hooks, Cline lifecycle hooks.
2. **SubAgents module.**
   - A2A protocol adapter: `Get Agent Card`, `Send Task`, `Wait For Task Completion`, `Get Task Artifact`, `Task Should Have Status`.
   - Bridges to LangGraph (`langgraph` checkpointer state assertions), CrewAI (replay), AutoGen (state introspection), OpenAI Agents SDK (handoff trace).
   - `SubagentStop` hook handling delegated to the Hooks module.
   - Trajectory comparison — assert that a delegated sub-agent followed an expected tool sequence (re-uses the BFCL AST matcher from Phase 1).

### Phase 3 — Full Coding-Agent Harness (≈ 2 months)

1. **`CodingAgentDriver`** wrapping CLIs for Claude Code, OpenAI Codex CLI, GitHub Copilot CLI, Aider, OpenCode, Cline, Continue. Each driver standardizes:
   - prompt submission;
   - session log capture (JSONL);
   - cost/token accounting;
   - exit codes.
2. **#42796 metric pack** as Robot Framework keywords, each computed from a session JSONL: `Read Edit Ratio`, `Edits Without Prior Read Percent`, `Reasoning Loops Per 1K Tool Calls`, `User Interrupts Per 1K Tool Calls`, `Stop Hook Violation Count`, `Convention Violation Rate`, `First Run Test Pass Rate`, `Token Usage Per Prompt`, `Self Admitted Errors Per 1K`, `Write Mutation Ratio`, `Simplest Word Frequency`. Each keyword has a `... Should Be ...` assertion variant.
3. **Benchmark integration**: SWE-bench Verified runner, Aider benchmark runner, LiveCodeBench runner, HumanEval/MBPP runners — each producing pass@1/pass@3 numbers as Robot keywords.
4. **Replay/time-travel** for LangGraph and CrewAI integrations.

### Phase 4 (stretch) — Open-source ecosystem hardening

- Skill/marketplace security scanner (the *ToxicSkills* study found 36% of community skills had security flaws and identified the *ClawHavoc* coordinated campaign delivering AMOS infostealers — the library should ship a vetting keyword `Skill Should Pass Security Scan`).
- Tool Approval / human-in-the-loop hook (mirrors Inspect AI's policy gating).
- Sandbox toolkit integration (Docker/K8s/Proxmox via Inspect's sandbox plugins) for safely running coding agents that may execute arbitrary code.

---

## 6. Example Test Cases (Robot Framework Syntax)

### 6.1 MCP Server — protocol compliance + tool call

```robotframework
*** Settings ***
Library    AgentTest    provider=litellm    model=anthropic/claude-sonnet-4-5
Suite Setup    Start MCP Server    command=uv run my-mcp-server    transport=stdio

*** Test Cases ***
MCP Server Implements Required Capabilities
    [Tags]    mcp    smoke
    ${caps}=    Get MCP Capabilities
    Should Contain    ${caps}    tools
    Should Contain    ${caps}    resources

Add Tool Returns Correct Sum
    [Tags]    mcp    deterministic
    ${result}=    Call MCP Tool    name=add    arguments={"x": 5, "y": 3}
    Tool Output Should Match Schema    ${result}    schema=add_result.schema.json
    Should Be Equal As Integers    ${result.data}    8

Search Tool Latency Stays Within Budget
    [Tags]    mcp    perf
    ${latency}=    Measure MCP Tool Latency    name=search    runs=50
    Should Be True    ${latency.p95} < 800     # ms
```

### 6.2 Agent Skill — quality grading with LLM-as-Judge + statistics

```robotframework
*** Settings ***
Library    AgentTest
...        provider=litellm
...        model=anthropic/claude-sonnet-4-5
...        judge_model=openai/gpt-4o

*** Test Cases ***
Browser Skill Produces Valid Robot Framework Code
    [Tags]    skill    browser
    Load Skill    skills/robotframework-browser-skill
    @{prompts}=    Read Lines    eval/browser_prompts.txt
    Run N Times    runs=10
    ...    Skill Output For Prompts    ${prompts}    store=responses
    Pass At K Should Be Above    metric=valid_rf_syntax    k=1    threshold=0.9
    LLM Judge Should Score At Least
    ...    rubric=eval/browser_rubric.md
    ...    threshold=0.85
    Convention Violation Rate Should Be Below    threshold=0.05

Skill Improves Over Previous Baseline
    [Tags]    skill    regression
    ${current}=    Run Skill Eval    skill=robotframework-browser-skill    runs=30
    ${baseline}=   Load Baseline    path=baselines/browser-v1.0.json
    Mann Whitney U Should Show Improvement    ${current}    ${baseline}    alpha=0.05
    Cliffs Delta Should Be At Least    ${current}    ${baseline}    delta=0.2
```

### 6.3 Hook — block dangerous bash, force test-suite Stop policy

```robotframework
*** Settings ***
Library    AgentTest

*** Test Cases ***
PreToolUse Hook Blocks Destructive Bash
    [Tags]    hook    security
    ${input}=    Synthesize Hook Input
    ...    event=PreToolUse    tool_name=Bash
    ...    tool_input={"command": "rm -rf /"}
    ${result}=    Run Hook Command
    ...    handler=./hooks/security-check.sh    stdin=${input}
    Hook Should Block    ${result}
    Should Contain    ${result.stderr}    destructive command

Stop Hook Forces Test Pass Before Stopping
    [Tags]    hook    stop
    ${input}=    Synthesize Hook Input    event=Stop    stop_hook_active=${False}
    ${result}=    Run Hook Command
    ...    handler=./hooks/require-tests.sh    stdin=${input}
    Hook Decision Should Be    ${result}    block
    Should Contain    ${result.reason}    Test suite must pass

HTTP Hook Returns Permission Decision
    [Tags]    hook    http
    ${input}=    Synthesize Hook Input    event=PreToolUse    tool_name=Edit
    ...    tool_input={"file_path": "/etc/passwd", "new_string": "..."}
    ${result}=    Run Hook HTTP
    ...    url=http://localhost:8080/hooks/pre-tool-use    body=${input}
    Hook Should Inject Context    ${result}    contains=read-only system path
```

### 6.4 SubAgent — A2A delegation lifecycle

```robotframework
*** Settings ***
Library    AgentTest    provider=litellm

*** Test Cases ***
Travel Planner Delegates Weather Lookup To Sub-Agent
    [Tags]    a2a    subagent
    ${card}=    Get Agent Card    url=http://localhost:7001/.well-known/agent.json
    Should Contain    ${card.skills}    weather.lookup
    ${task}=    Send Task
    ...    agent_url=http://localhost:7000
    ...    message=Plan a 3-day trip to Lisbon next week
    Wait For Task Completion    ${task}    timeout=120s
    Task Should Have Status    ${task}    completed
    ${trajectory}=    Get Task Trajectory    ${task}
    Tool Sequence Should Match
    ...    ${trajectory}
    ...    expected=["weather.lookup", "places.search", "summary.compose"]
    ${artifact}=    Get Task Artifact    ${task}    type=application/json
    Validate JSON Schema    ${artifact}    schemas/itinerary.schema.json
```

### 6.5 Coding Agent — #42796 behavioral regression test

```robotframework
*** Settings ***
Library    AgentTest

*** Test Cases ***
Claude Code Maintains Healthy Read-Edit Discipline
    [Tags]    coding-agent    behavioral
    ${session}=    Run Coding Agent
    ...    driver=claude-code
    ...    prompt_file=eval/refactor_task.md
    ...    repo=fixtures/sample_repo
    Read Edit Ratio Should Be Above    session=${session}    threshold=4.0
    Edits Without Prior Read Percent Should Be Below    ${session}    10
    Reasoning Loops Per 1K Tool Calls Should Be Below    ${session}    12
    User Interrupts Per 1K Should Be Below    ${session}    2
    Stop Hook Violations Should Be Zero    ${session}
    First Run Test Pass Rate Should Be Above    ${session}    0.9
    Token Usage Per Prompt Should Be Below    ${session}    baseline=baselines/jan2026.json    multiplier=1.5
```

### 6.6 BFCL-style tool selection accuracy

```robotframework
*** Test Cases ***
Model Selects Correct Tool With Correct Args
    [Tags]    bfcl    tool-call
    @{cases}=    Load BFCL Dataset    category=simple
    FOR    ${case}    IN    @{cases}
        ${call}=    Generate Tool Call    prompt=${case.prompt}    tools=${case.tools}
        Tool Call Should Match Name    ${call}    ${case.expected.name}
        Tool Call Arguments Should Match    ${call}    ${case.expected.arguments}    mode=ast
    END
    BFCL Score Should Be Above    threshold=0.85
```

---

## 7. Integration Patterns for LLM Providers and Coding Agents

### 7.1 Cloud and Local LLMs

The `provider=litellm` default is the recommended path for the vast majority of users — one OpenAI-compatible interface to Anthropic, OpenAI, Gemini, Mistral, Cohere, AWS Bedrock, Azure OpenAI, Vertex AI, Together, Fireworks, DeepSeek, xAI, Groq, OpenRouter, plus local Ollama/vLLM/llama.cpp/LM Studio. Errors map to OpenAI exception types so a single Robot keyword `LLM Call Should Not Fail With Rate Limit` is portable. Provider-specific advanced features (Anthropic extended thinking with `effort=high|max`, OpenAI Responses API, Gemini grounding, Bedrock prompt caching) are surfaced as optional kwargs in the `Generate Tool Call` keyword and gated by `Provider Supports`.

### 7.2 Coding Agent CLIs

Each coding agent is wrapped in a `CodingAgentDriver` that:

1. Spawns the CLI as a subprocess in a configurable working directory.
2. Pipes the prompt (or attaches a `--prompt-file`).
3. Captures the JSONL session log path. For Claude Code that is `~/.claude/projects/<project>/<session>.jsonl`; for Codex CLI it is `~/.codex/sessions/`; for Aider it is `.aider.chat.history.md` plus `.aider.input.history`; for OpenCode it is `~/.opencode/sessions/`; for Cline and Continue it is the workspace `.cline/` or `.continue/` directories.
4. Normalizes the JSONL into a `Session` schema that includes `messages`, `tool_calls`, `tool_responses`, `thinking_blocks`, `signature_lengths`, `interrupts`, `hook_events`, and `usage`. This normalized schema is what every #42796 metric keyword consumes, so adding a new agent only requires writing a parser.
5. Optionally proxies via LiteLLM Gateway so that token usage and cost are captured uniformly even when the agent talks to its own backend.

### 7.3 MCP Transport Selection

`transport=auto` follows the FastMCP convention — infer from the connection target. The library prefers in-memory transport for unit tests (deterministic, no network), stdio for CLI-style integration tests, and streamable-HTTP for deployment validation. SSE is supported but flagged deprecated.

### 7.4 A2A and MCP Together

A common architecture (per Google's "Build with ADK, equip with MCP, communicate with A2A" guidance and the *Glue-Code to Protocols* analysis on arXiv 2505.03864) is to use MCP for the vertical (agent ↔ tool) axis and A2A for the horizontal (agent ↔ agent) axis. The library mirrors this split: the `MCP` module covers vertical testing, the `SubAgents` module covers horizontal testing, and trajectories from both are unified into the same `Session` schema for behavioral analysis.

---

## 8. Risks, Open Questions, and Recommendations

1. **LLM-as-Judge calibration drift.** Hamel Husain and Braintrust both stress that judges must be validated against human labels and prefer classification over numeric scoring. The library should ship a `Calibrate Judge` keyword that runs the configured judge against a small human-labeled set and emits an inter-rater agreement score (Cohen's κ or Krippendorff's α) before the judge is allowed to score real test runs.
2. **Sandboxing for arbitrary-code coding agents.** Coding agents will execute generated code; the library must integrate with Inspect AI's sandboxing toolkit (Docker / K8s pods per sample / Proxmox) and require an explicit `--allow-code-execution` flag, mirroring AISI guidance.
3. **Skill marketplace supply chain.** The Snyk *ToxicSkills* finding (36% flawed, 76 confirmed malicious, ClawHavoc campaign) means a skill-discovery keyword must default to **deny** for unsigned third-party skills and require an explicit allowlist.
4. **Determinism vs. reproducibility.** The arxiv literature is unambiguous that `temperature=0` does not yield reproducible runs. The library must therefore make N≥10 runs the default for any LLM-mediated assertion, and produce a "non-deterministic test report" header on every Robot HTML log indicating the actual variance observed.
5. **Standards velocity.** A2A only reached 1.0 in early 2026 and the Agent Skills spec is still under-specified for installation paths and the `allowed-tools` mechanism (per Simon Willison). The library should pin to spec versions in the Library `version=` parameter and emit deprecation warnings when a newer spec is released.
6. **Vendor-specific behaviors.** Reports such as Fortune's coverage of the April 23, 2026 Anthropic postmortem and the Claude Code performance regression described in `#42796` show that vendor-side changes can silently move metric distributions. The recommendation is to ship a **canary suite** that re-runs the same prompts against the same model nightly, compares to a stored baseline, and uses Mann-Whitney + Cliff's delta to flag regressions before users notice — exactly the pattern Stella Laurenzo's `stop-phrase-guard.sh` informally pioneered.

---

## 9. Conclusion

The MCP, Agent Skills, and A2A standards are stable enough — and the metric catalog from `anthropics/claude-code#42796` is precise enough — that a Robot Framework library covering Agent Skills, Hooks, SubAgents, and MCP Servers is now both feasible and overdue. The proposed architecture uses **LiteLLM** as the provider abstraction, **Inspect AI** as the evaluation engine, **mcp-eval / FastMCP / MCP Inspector** as the MCP protocol layer, **BFCL AST matching** for tool-call correctness, and **scipy-backed Mann-Whitney/Cliff's-delta/bootstrap/pass@k/TAR** statistics for non-determinism. By exposing each of these as Robot Framework keywords and shipping a session-JSONL parser that computes the eleven #42796 behavioral metrics, the library meets QA teams in the testing language they already use while remaining strictly aligned with the open standards now adopted across the industry.

Phase 1 (Agent Skills + MCP testing) is the right minimum viable release. Phase 2 fills the most-glaring gap in the ecosystem (hook testing) and adds A2A sub-agent coverage. Phase 3 closes the loop with a full coding-agent harness and the canonical SWE-bench/Aider/HumanEval benchmark drivers. The result is a single Robot Framework library that lets a team write — in plain `.robot` syntax — an end-to-end agentic-product test suite that travels intact across Claude, GPT, Gemini, Mistral, local Ollama, and any future provider that joins the MCP/A2A ecosystem.