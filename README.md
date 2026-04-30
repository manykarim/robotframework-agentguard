# robotframework-agentguard

[![PyPI version](https://img.shields.io/pypi/v/robotframework-agentguard.svg)](https://pypi.org/project/robotframework-agentguard/)
[![Python](https://img.shields.io/pypi/pyversions/robotframework-agentguard.svg)](https://pypi.org/project/robotframework-agentguard/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/manykarim/robotframework-agentguard/ci.yml?branch=main)](https://github.com/manykarim/robotframework-agentguard/actions)

> Robot Framework library for testing **MCP servers, Agent Skills, Hooks, SubAgents, and coding-agent CLIs** — provider-agnostic via LiteLLM, BFCL-grade tool-call matching, statistical N≥10 by default. Phase 1 shipped **55 keywords** across 6 sub-libraries; Phase 2 added Hooks + SubAgents + sandbox for **83 keywords** across 8 sub-libraries; Phase 3 (in progress) extends the surface to **~110+ keywords** with the CodingAgent harness, the #42796 behavioral metric pack, and SWE-Bench / Aider / HumanEval / MBPP / LiveCodeBench benchmarks (see [phased delivery](#phased-delivery)).

## 60-second quickstart

```robot
*** Settings ***
Library    AgentGuard    provider=litellm    model=openrouter/anthropic/claude-sonnet-4-5

*** Test Cases ***
AgentGuard Should Be Loaded
    ${info}=    Get AgentGuard Info
    Log    ${info}
```

## Installation

```bash
uv add robotframework-agentguard
# or
pip install robotframework-agentguard
```

Create `.env` in your project root:

```bash
OPENROUTER_API_KEY=sk-or-...
# optional overrides
AGENTGUARD_DEFAULT_MODEL=openrouter/anthropic/claude-sonnet-4-5
AGENTGUARD_JUDGE_MODEL=openrouter/openai/gpt-4o-mini
```

Verify the install:

```bash
uv run agentguard doctor
uv run agentguard version
```

## Why AgentGuard?

- **Provider-agnostic** — one OpenAI-shaped surface across 100+ LLMs via LiteLLM (Anthropic, OpenAI, Gemini, Bedrock, OpenRouter, Ollama, vLLM, …).
- **BFCL-grade tool-call matching** — AST equality + trajectory comparison ported from `inspect_evals.bfcl`, so a passing test means a structurally correct call, not a string-similar one.
- **Statistical by default** — N≥10 runs, Mann-Whitney U / Cliff's δ / bootstrap CIs (scipy), pass@k and TARr@N — non-determinism is treated as a first-class concern, not glossed over.

## Architecture (12 bounded contexts)

| Context | Purpose |
|---|---|
| **Provider** | LiteLLM-backed `LLMProviderAdapter` + thin vendor adapters |
| **MCP** | FastMCP client wrapper for stdio / SSE / streamable-http / in-memory |
| **Skills** | `SKILL.md` discovery, frontmatter validation, Inspect-AI grading |
| **Hooks** | Synthesise the 12 Claude Code hook events; assert handler decisions |
| **SubAgents** | A2A 1.0 task lifecycle + delegation-chain assertions |
| **CodingAgent** | Drive Claude Code, Codex CLI, Aider, OpenCode, Cline, Continue; normalise JSONL |
| **Statistics** | scipy-backed Mann-Whitney, Cliff's δ, bootstrap CI, pass@k, TARr@N |
| **Judge** | Classification-based LLM-as-Judge with calibration gating (Cohen's κ ≥ 0.7) |
| **Security** | Default-deny skill scanner, redactor, sandbox policy, AIDefence integration |
| **Telemetry** | OTel spans + Robot Framework listener embedding scorecards in `log.html` |
| **BehavioralMetrics** | The 11 calculators from anthropic/claude-code#42796 |
| **ToolCallCorrectness** | BFCL AST/trajectory matcher used by MCP, Skills, SubAgents |

See [`docs/ddd/bounded-contexts.md`](docs/ddd/bounded-contexts.md) for aggregates, value objects, and ACLs.

## Phased delivery

| Phase | Scope | Status |
|---|---|---|
| 0 | Research, ADRs, DDD, experiments | Done |
| 1 | MCP + Skills + Stats + Judge + Security baseline | Done |
| 2 | Hooks + SubAgents + Sandbox | Done |
| 3 | Coding-agent harness + #42796 metrics + benchmarks | In progress |
| 4 | OSS hardening + RuFlo SONA / HNSW / hive-mind integration | Planned |

### Phase 2 keywords (in progress)

Per ADR-007 (Hooks), ADR-008 (SubAgents) and ADR-013 (Sandbox). Sub-libraries
are composed via lazy import on the top-level `AgentGuard` Library, so partial
Phase 2 installs do not break the import.

**Hooks** (`AgentGuard.Hooks`):
- `Synthesize Hook Input` — 12 event types (`UserPromptSubmit`, `UserPromptExpansion`, `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PostToolBatch`, `Notification`, `Stop`, `SubagentStop`, `PreCompact`, `SessionStart`, `ConfigChange`).
- `Run Hook Command`, `Run Hook HTTP`, `Run Hook Prompt`, `Run Hook Agent` — the 4 handler types.
- `Hook Should Block`, `Hook Should Allow`, `Hook Decision Should Be`, `Hook Should Inject Context`, `Hook Should Modify Tool Input To` — decision assertions.
- `Detect Stop Hook Loop` — loop-safety guard.

**SubAgents** (`AgentGuard.SubAgents`, A2A SDK 1.0.x):
- `Get Agent Card`, `Send Task`, `Wait For Task Completion`, `Get Task Artifact`, `Task Should Have Status`.
- `Task Trajectory Should Match` — reuses the BFCL trajectory matcher from Phase 1.
- `Bridge Connect LangGraph` / `CrewAI` / `AutoGen` / `OpenAI Agents` — opt-in via the `[bridges]` extra.

**Sandbox** (`AgentGuard.Security`, additions):
- `Run In Sandbox` — Docker backend, default-deny policy (`--network=none`, read-only fs, dropped caps, no docker-socket mount); `--allow-code-execution` gate.
- `Sandbox Output Should Contain`, `Sandbox Exit Code Should Be`.

### Phase 3 keywords (in progress)

Per `docs/PLAN.md` §8 Phase 3 — the **CodingAgent** bounded context wraps a
driver harness, a JSONL session parser, the 12 #42796 behavioral metric
calculators, and the public coding-agent benchmarks. Composed lazily on the
top-level `AgentGuard` Library; partial Phase-3 installs do not break import.

**CodingAgent — driver** (`AgentGuard.CodingAgent`):
- `Run Coding Agent` (`driver=local|claude-code|codex|aider|opencode|cline|continue|copilot`).
- `Run Coding Agent And Save Session`, `Get Last Coding Agent Session`.

**CodingAgent — JSONL parser**:
- `Parse Session JSONL` (auto-detect; explicit `format=` for claude-code / codex / aider / opencode).
- `Save Session Snapshot`, `Load Session Snapshot`, `Validate Session Schema`.

**CodingAgent — #42796 metric pack** (12 calculators × `Get` / `Should` ≈ 24 keywords):
- `Read Edit Ratio` / `... Should Be Above`.
- `Edits Without Prior Read Percent` / `... Should Be Below`.
- `Reasoning Loops Per 1K Tool Calls` / `... Should Be Below`.
- `User Interrupts Per 1K Tool Calls` / `... Should Be Below`.
- `Stop Hook Violation Count` / `Stop Hook Violations Should Be Zero`.
- `Convention Violation Rate` / `... Should Be Below` (re-export from Skills).
- `First Run Test Pass Rate` / `... Should Be Above`.
- `Token Usage Per Prompt` / `... Should Be Below`.
- `Self Admitted Errors Per 1K` / `... Should Be Below`.
- `Write Mutation Ratio` / `... Should Be Below`.
- `Repeated Edits Per File` / `... Should Be Below`.
- `Simplest Word Frequency Per 1K` / `... Should Be Below`.
- `Compute 42796 Metric Pack` (one-shot dict of all 12).
- `Behavioral Report Should Match Baseline` (Mann-Whitney U via `AgentGuard.Stats`).

**CodingAgent — benchmarks** (opt-in via the `[benchmarks]` extra — `pip install 'robotframework-agentguard[benchmarks]'`):
- `Load SWE Bench Dataset`, `Run SWE Bench Task`, `SWE Bench Pass At K Should Be Above`.
- `Load Aider Benchmark Dataset`, `Run Aider Benchmark Task`, `Aider Benchmark Pass Rate Should Be Above`.
- `Load HumanEval Dataset`, `Run HumanEval Task`, `HumanEval Pass At K Should Be Above`.
- `Load MBPP Dataset`, `Run MBPP Task`, `MBPP Pass At K Should Be Above`.
- `Load LiveCodeBench Dataset`, `Run LiveCodeBench Task`.

**Bridges — real `replay()` (Phase 2 extension, landing with Phase 3)**:
- `LangGraph` — walks the compiled graph's checkpointer history; returns per-step Session-shaped frames so any LangGraph run feeds the same #42796 calculators as a Claude Code JSONL.
- `CrewAI` — uses `Crew.replay(task_id=...)`; returns per-task Session-shaped frames with `task_id` / `agent` / `raw` / `tool_calls`.
- `AutoGen` and `OpenAI Agents` deliberately remain `NotImplementedError` (no upstream replay primitive — see each bridge's docstring for the framework-native introspection path).

## Performance

Hard ceilings — every Phase-1 release MUST meet these. CI fails if any
benchmark in `benchmarks/` exceeds the matching budget by more than 20%.

| Surface                              | Budget           | Where           |
|--------------------------------------|------------------|-----------------|
| MCP in-memory roundtrip (p50 / p95)  | ≤ 5 / 10 ms      | `budgets.md §2` |
| MCP stdio roundtrip (p50)            | ≤ 50 ms          | `budgets.md §2` |
| BFCL AST match (mean per call)       | ≤ 1 ms           | `budgets.md §1` |
| `mannwhitneyu` n=30/30 (mean)        | ≤ 5 ms           | `budgets.md §1` |
| `bootstrap` n=30 / 1000 resamples    | ≤ 100 ms         | `budgets.md §1` |
| Library import + Suite Setup (cold)  | ≤ 2 s            | `budgets.md §5` |
| Skill grade offline N=10 (mock)      | ≤ 1 s total      | `budgets.md §3` |
| Judge keyword overhead (mock)        | ≤ 100 ms mean    | `budgets.md §1` |

Run the suite locally:

```bash
uv run pytest benchmarks/ --benchmark-only \
    --benchmark-json=benchmarks/results.json
```

Budgets, the cost model, and the tier-routing decision table live under
[`docs/performance/`](docs/performance/). The 13 Phase-1 GA validation
experiments are in [`docs/performance/benchmarks-plan.md`](docs/performance/benchmarks-plan.md).

## Documentation

- Plan: [`docs/PLAN.md`](docs/PLAN.md)
- Architecture Decision Records: [`docs/adr/`](docs/adr/)
- Domain model: [`docs/ddd/`](docs/ddd/)
- Performance budgets: [`docs/performance/`](docs/performance/)
- Research dossier: [`docs/research/research.md`](docs/research/research.md)
- Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Security: [`SECURITY.md`](SECURITY.md)

## License

Apache-2.0 — see [LICENSE](LICENSE).
