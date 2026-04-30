# Phase 3 — Implementation Report

**Date**: 2026-04-30
**Status**: Implementation in progress, benchmarks + examples + docs complete.
**Scope**: CodingAgent context — driver harness (ADR-009), Session JSONL parser
+ #42796 metric pack (ADR-010), benchmark integration (HumanEval, MBPP,
SWE-bench Verified, Aider, LiveCodeBench).

This report mirrors the structure of [`PHASE-2-COMPLETE.md`](PHASE-2-COMPLETE.md).

## What landed

| Track | Status | Evidence |
|---|---|---|
| Foundation — `library.py` extension, deps verified, README | done | `src/AgentGuard/library.py` (`_SUB_LIBRARIES` includes `CodingAgentKeywords`); `pyproject.toml` (`jsonlines>=4.0`, `datasets>=3.0`); README Phase 3 section |
| Session module (ADR-010) | done | `src/AgentGuard/coding_agent/session/{parser,claude_code,codex,aider,opencode,types,normalise,_helpers,exceptions}.py` — `parse(path, format=...)` auto-detects across 4 vendor formats |
| Drivers module (ADR-009) | done | `src/AgentGuard/coding_agent/drivers/{base,registry,local,claude_code,codex,aider,opencode,cline,continue_,copilot,_subprocess,exceptions}.py` — protocol + 8 drivers + LocalDriver always-runnable |
| Metrics module (ADR-010, #42796 pack) | done | `src/AgentGuard/coding_agent/metrics/{pack,registry,types,_session_proto}.py` plus 12 calculator modules (read_edit, edits_without_read, reasoning_loops, interrupts, stop_hook, convention, first_run_test, token_efficiency, self_admitted, write_ratio, repeated_edits, simplest_word) |
| CodingAgent library facade | done | `src/AgentGuard/coding_agent/library.py` — 30 keywords (3 driver + 4 parser + 12×2 metric + 3 aggregate) |
| Benchmarks module (5 loaders) | done | `src/AgentGuard/coding_agent/benchmarks/{base,registry,scorer,humaneval,mbpp,livecodebench,swe_bench,aider_bench,library}.py` — datasets-loader with mini-fixture fallback |
| Tests — unit + integration + acceptance | landing | tester-p3 owns `tests/{unit,integration,acceptance}/coding_agent/` |
| Benchmarks — pytest-benchmark | done | 4 new modules (`test_coding_agent_*.py`); 3 offline budgets validated locally + 1 live-gated |
| Examples (real impl, mirror research §6.5) | done | `examples/05_coding_agent_metrics.robot`, `examples/08_swe_bench.robot`, `examples/09_humaneval_live.robot` |
| API docs | done | `docs/api/AgentGuard.html` regenerated (117 keywords); new `docs/api/AgentGuard.CodingAgent.html` |

## Top-level Library surface (now 9 components, 117 keywords)

`Library    AgentGuard    provider=litellm    model=openrouter/anthropic/claude-sonnet-4-5`

Composed via `robotlibcore.DynamicCore` from 9 sub-libraries (lazy-imported):

```python
{'MCPKeywords', 'SkillsKeywords', 'ToolCallKeywords',
 'StatsKeywords', 'JudgeKeywords', 'SecurityKeywords',
 'HooksKeywords', 'SubAgentsKeywords', 'CodingAgentKeywords'}
```

End-to-end count from a fresh `from AgentGuard import AgentGuard; AgentGuard()`:

```
components:       9
total keywords:   117   (Phase-2 was 80; +37 Phase-3 keywords on the
                       top-level library; benchmark suite keywords add
                       another 15 via `Library AgentGuard.coding_agent
                       .benchmarks.library.CodingBenchmarkKeywords`)
```

### Phase 3 keyword surface (per ADR-009 / ADR-010)

**CodingAgent — driver** (3 keywords):
- `Run Coding Agent` (driver=local|claude-code|codex|aider|opencode|cline|continue|copilot)
- `Run Coding Agent And Save Session`
- `Get Last Coding Agent Session`

**CodingAgent — parser** (4 keywords):
- `Parse Session JSONL` (auto-detect format; explicit `format=` for claude-code/codex/aider/opencode)
- `Save Session Snapshot` / `Load Session Snapshot`
- `Validate Session Schema`

**CodingAgent — #42796 metric pack** (24 keywords = 12 calculators × {Get, Should}):
- `Read Edit Ratio` / `Read Edit Ratio Should Be Above`
- `Edits Without Prior Read Percent` / `... Should Be Below`
- `Reasoning Loops Per 1K Tool Calls` / `... Should Be Below`
- `User Interrupts Per 1K Tool Calls` / `User Interrupts Per 1K Should Be Below`
- `Stop Hook Violation Count` / `Stop Hook Violations Should Be Zero`
- `Convention Violation Rate For Session` / `... Should Be Below`
- `First Run Test Pass Rate` / `... Should Be Above`
- `Token Usage Per Prompt` / `Token Usage Per Prompt Should Be Below` (baseline-aware)
- `Self Admitted Errors Per 1K` / `... Should Be Below`
- `Write Mutation Ratio` / `... Should Be Below`
- `Repeated Edits Per File Count` / `... Should Be Below`
- `Simplest Word Frequency Per 1K` / `... Should Be Below`

**CodingAgent — aggregate** (3 keywords):
- `Compute 42796 Metric Pack` — one-shot returns `BehavioralReport` dataclass
- `Behavioral Report Should Match Baseline` — Mann-Whitney U vs baseline
- `Get Session Health` — coarse `healthy` / `degraded` / `unknown`

**Benchmarks** (15 keywords; addressable as a separate library —
foundation-p3 owns the optional top-level wiring):
- `Load SWE Bench Dataset` / `Run SWE Bench Task` / `SWE Bench Pass At K Should Be Above`
- `Load Aider Benchmark Dataset` / `Run Aider Benchmark Task` / `Aider Benchmark Pass Rate Should Be Above`
- `Load HumanEval Dataset` / `Run HumanEval Task` / `HumanEval Pass At K Should Be Above`
- `Load MBPP Dataset` / `Run MBPP Task` / `MBPP Pass At K Should Be Above`
- `Load LiveCodeBench Dataset` / `Run LiveCodeBench Task`
- `Run Benchmark Suite` (uniform dispatcher across the 5 above)

## Live OpenRouter integration (still wired)

`.env`-driven via `python-dotenv`. `OPENROUTER_API_KEY` is loaded by
`AgentGuard.config.load_env()` and never logged. The `LocalDriver` reuses the
suite-level provider (or builds one via `build_provider("litellm", ...)`) so
`driver=local` routes to OpenRouter the same way Skills / Judge / Hooks do
— no per-module re-auth. Live tests gate on `OPENROUTER_API_KEY` and the
`live` Robot tag (`@pytest.mark.live` for benchmarks).

## Benchmarks (Phase 3 budgets validated locally)

Measured on this dev host with `uv run pytest benchmarks/test_coding_agent_*.py
--benchmark-only`. All three offline budgets pass with substantial headroom;
the live HumanEval budget is exercised against `openrouter/openai/gpt-4o-mini`.

| Test | Budget | Measured | Verdict |
|---|---|---|---|
| Session JSONL parse — synthetic 200-line claude-code (mean) | ≤ 50 ms | **3.13 ms** | PASS (16× headroom) |
| #42796 metric pack — 12 calculators on 100-msg session (mean) | ≤ 5 ms | **1.52 ms** | PASS (3.3× headroom) |
| LocalDriver mock-provider 5-turn run + parse (mean) | ≤ 1 s | **3.30 ms** | PASS (300× headroom) |
| HumanEval 1-task live (`openrouter/openai/gpt-4o-mini`, total / cost) | ≤ 30 s, ≤ $0.005 | live-validated end-to-end via `examples/09_humaneval_live.robot` (Robot suite passed in ≈ 6 s) | PASS warm |

Notes:
- The session-parser headroom matters: per `docs/performance/budgets.md`
  Tier-1 is `<1 ms` for individual calculators; the parse budget is more
  generous because it walks I/O.
- The LocalDriver bench measures the **mock-provider** loop (no network) —
  exactly the path `examples/09_humaneval_live.robot` exercises with the
  live key. It is intentionally cheap so `examples/` stay snappy in CI.
- The HumanEval live bench is gated by `@pytest.mark.live` and skips
  cleanly when `OPENROUTER_API_KEY` is unset.

Run locally:
```bash
uv run pytest benchmarks/test_coding_agent_*.py --benchmark-only \
              --benchmark-columns=mean,median,min,max
# include the live HumanEval smoke (needs OPENROUTER_API_KEY):
uv run pytest benchmarks/test_coding_agent_humaneval_local.py -m live --benchmark-only
```

## Example suites (real impl, mirror research §6.5)

| Suite | Tests | Status | Mode |
|---|---|---|---|
| `examples/05_coding_agent_metrics.robot` | 2 | All PASS | offline (synthetic Claude Code JSONL fixture) |
| `examples/08_swe_bench.robot` | 1 | PASS | offline (mini-fixture fallback when `datasets` absent) |
| `examples/09_humaneval_live.robot` | 1 | PASS (live, OpenRouter) | `live`-tagged; suite-level `Skip If Live Disabled` |

All three runnable via `PYTHONPATH=. uv run robot examples/<file>.robot`.
Live HumanEval validated end-to-end against `openrouter/openai/gpt-4o-mini`
on this host (~6 s wall-clock, well under the 30 s benchmark budget).

## Architectural pivots applied

1. **Parser dispatcher is the single entry point.** Per exp_07 / ADR-010 the
   canonical `tool_calls / tool_responses / interrupts / hook_events / usage`
   fields do not live at the top level of real Claude Code JSONL — they are
   derived by walking `assistant.message.content[]` and pairing
   `toolUseResult` records via `parentUuid`. The dispatcher in
   `coding_agent/session/parser.py` resolves the format via filename + first-
   record sniff so callers (`Parse Session JSONL`, `LocalDriver._try_parse`,
   benchmark loaders) all funnel through one place.
2. **LocalDriver mocks tools, talks to a real provider.** The driver's tool
   schema is real (read/write/edit/bash/grep) but the implementations are
   canned strings — we never let the LLM touch the host filesystem. This
   keeps the `09_humaneval_live.robot` path safe to run in CI even when the
   model wants to run shell commands; the candidate code is extracted from
   the model's `text` content, not from any tool side-effect.
3. **Benchmark loaders fall back to bundled mini-fixtures.** Each of the 5
   benchmark modules detects `datasets` lazily and degrades to a JSON mini-
   fixture (`tests/fixtures/coding_agent/benchmarks/{humaneval,mbpp}_mini.json`)
   when the optional extra is missing. This keeps `Load X Dataset` keywords
   honest on stripped-down CI runners.
4. **Live tests are *example*, not pytest, in the Robot surface.** The
   research §6.5 example uses `Library AgentGuard` only — bench keywords
   are addressable separately as
   `Library AgentGuard.coding_agent.benchmarks.library.CodingBenchmarkKeywords`
   (foundation-p3 owns the optional top-level wiring decision). Examples
   `08` and `09` use `WITH NAME Bench` to keep call sites concise.

## What's NOT in this phase (Phase 4)

- **Real SWE-bench eval loop**: `Run SWE Bench Task` returns a *plausibility*
  signal today (the agent emitted a unified diff). Apply-patch + run-the-
  instance's-`test_cmd`-inside-Docker is Phase 4 (per ADR-013 sandbox + the
  Phase 4 SWE-bench harness work).
- **Top-level wiring of `CodingBenchmarkKeywords`**: the benchmark suite
  keywords are not in `_SUB_LIBRARIES` yet — examples instantiate the class
  directly via `Library AgentGuard.coding_agent.benchmarks.library
  .CodingBenchmarkKeywords`. Two-line foundation-p3 follow-up.
- **LangGraph / CrewAI replay() bridges**: the `replay()` extension to
  `subagents/bridges/{langgraph,crewai}_bridge.py` is owned by foundation-p3;
  `bench-cicd-docs-p3` reads-only.
- **HNSW knowledge graph** (Phase 4 per ADR-016).
- **RuFlo SONA self-learning** (Phase 4 per ADR-015).
- **AIDefence over MCP** (Phase 4 per ADR-020 / exp_10).
- **Cosign signature verification for sandbox images** (Phase 4 per ADR-013).

## File counts

```
src/AgentGuard/                 ~151 Python files (Phase 2 was ~93 — CodingAgent
                                added 57 modules: 8 session + 12 drivers
                                + 14 metrics + 9 benchmarks + library + types
                                + exceptions + __init__s)
src/AgentGuard/coding_agent/    57 Python files
tests/                           ~114 test+robot files
benchmarks/                      16 benchmark modules (Phase 2: 12; +4 Phase 3:
                                 session_parse, metric_pack, local_driver,
                                 humaneval_local)
examples/                        9 .robot files (Phase 2: 7; +2 Phase 3:
                                 swe_bench, humaneval_live; 05 upgraded from
                                 placeholder to real impl)
docs/api/                        10 libdoc HTML artifacts (was 9; +AgentGuard
                                 .CodingAgent.html)
```

## Coordination memory keys (RuFlo `agentguard/phase3` namespace)

- `phase3/foundation_status` — set by foundation-p3 (`library.py` + deps + README)
- `phase3/session_parser_status` — set by session-parser
- `phase3/drivers_status` — set by drivers
- `phase3/metrics_status` — set by metrics
- `phase3/library_keywords_status` — set by library-keywords
- `phase3/benchmarks_status` — set by benchmarks
- `phase3/tester_status` — set by tester-p3
- `phase3/bench_cicd_status` — set by this agent (benches + examples + docs)

## Known issues / follow-ups

- **`CodingBenchmarkKeywords` not on top-level Library**: the 15 benchmark
  keywords work via `Library AgentGuard.coding_agent.benchmarks.library
  .CodingBenchmarkKeywords` but are not yet composed into the `AgentGuard`
  facade. Foundation-p3 follow-up.
- **HumanEval mini-fixture**: when `datasets` is installed, the loader hits
  Hugging Face Hub unauthenticated and warns about rate limits. CI workers
  should set `HF_TOKEN` to avoid throttling, or pin to the bundled mini-
  fixture by uninstalling `datasets` in the offline test job.
- **LocalDriver tool implementations are canned**: this is by design (see
  pivot #2) — but it does mean a HumanEval pass@k from `Run HumanEval Task`
  measures the model's zero-shot code-gen quality, not its tool-using
  ability. For tool-using evals use `driver=claude-code` once Phase 4 wires
  the secure-by-default subprocess host.
- **SWE-bench plausibility signal only**: `Run SWE Bench Task` currently
  returns `passed=True` when the agent produced a non-empty diff. Real
  resolution requires the Phase-4 apply-patch + test-under-Docker loop.
