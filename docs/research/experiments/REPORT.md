# AgentGuard Experiment Report — Phase 0 Validation

**Status**: 9 PASS / 1 PARTIAL / 0 FAIL (10 experiments)
**Python**: 3.11.7 via uv-managed venv (pinned in `.python-version`)
**Date**: 2026-04-29

Experiments validate the load-bearing technical assumptions in `docs/research/research.md` before any production code is written. Each script is `tests/experiments/exp_NN_*.py`, each captured stdout is `docs/research/experiments/exp_NN_*.log`. Findings are mirrored into RuFlo memory namespace `agentguard/experiments`.

## Toolchain confirmed (via `uv add --group experiments`)

| Package | Version | Purpose |
|---|---|---|
| fastmcp | 3.2.4 | MCP server + in-memory client |
| mcp | 1.27.0 | Protocol primitives |
| litellm | 1.83.0 | Provider abstraction |
| inspect-ai | 0.3.213 | Task/Solver/Scorer triad |
| inspect-evals | (latest) | BFCL AST matchers |
| scipy | 1.17.1 | Mann-Whitney, bootstrap, Cliff's δ |
| robotframework | 7.4.2 | Test surface |
| robotframework-pythonlibcore | 4.5.0 | DynamicCore composition |
| pytest-mcp | (installed) | Phase-1 fallback for mcp-eval |
| opentelemetry-{api,sdk} | 1.41.1 | Telemetry |
| httpx, pytest, pytest-asyncio | — | Test infra |

`mcp-eval 0.0.1` was **declined**: requires Python ≥3.12 (see Refuted Assumption #1).

## Per-experiment results

### exp_01 — FastMCP in-memory transport — PASS
- `Client(server)` over in-process FastMCP listed `['add']`, returned `add(2,3)=5`.
- 100 calls in 222 ms ≈ **2.22 ms/call**.
- **Implication**: `transport="memory"` is safe as the unit-test default; well below the Tier-1 latency budget. Confirms ADR-002.

### exp_02 — MCP Inspector CLI — PASS
- `npx @modelcontextprotocol/inspector --cli --help` exit 0; documented options `--cli/--transport/--server-url/--header/--config/--server`.
- Bonus: `--cli --method tools/list -- uv run python <fastmcp-stdio>` returned a valid JSON `tools` list.
- **Caveat**: `--method` works but is not in `--help` — pin a known-good Inspector version and document the flag in our wrapper.
- **Implication**: The CI compliance gate keyword can wrap `inspector --cli --method` directly.

### exp_03 — LiteLLM offline shape — PASS
- v1.83.0 imports cleanly; `RateLimitError`/`AuthenticationError`/`APIError` importable.
- `litellm.completion(..., mock_response="hi")` returns `"hi"` with **no API key**.
- **Refutation**: `litellm.__version__` does not exist — must use `importlib.metadata.version("litellm")`.
- **Implication**: LiteLLM is the right `LLMProviderAdapter` default (ADR-001); `mock_response=` is the unit-test primitive.

### exp_04 — Inspect AI Task/Solver/Scorer — PASS
- Built `Task(dataset=[Sample(input,target)], solver=generate(), scorer=match())`.
- Ran with `mockllm/model` (no key). Result: `samples[0].scores == {'match': Score(value='I', answer=..., explanation=..., metadata=None, history=[])}`.
- **Implication**: The skill-grader keyword wraps a single Inspect Task; `mockllm/model` is the offline fixture for our own acceptance tests. Confirms ADR-003.

### exp_05 — `robotlibcore.DynamicCore` composition — PASS
- `MiniLib(DynamicCore)` composed `MathKw + EchoKw`; 3-test `.robot` suite passed cleanly (`output.xml`: 11 PASS / 0 FAIL); `robot` exit 0.
- **Implication**: §4.3 architecture is realisable as written. Sub-libraries are plain classes merged via `DynamicCore.__init__(self, [...])`. Confirms ADR-003.

### exp_06 — scipy stats surface — PASS
- v1.17.1: `mannwhitneyu` returns `stat=541.0 p=0.0535`; manual `cliffs_delta = +0.249`; `bootstrap` returns `ConfidenceInterval(low=0.140, high=0.712)`.
- **Implication**: No extra deps beyond scipy. p=0.054 at n=30 / 0.3σ confirms the research's case for **N≥30 as default** when small effects must be detected. Confirms ADR-005.

### exp_07 — Claude Code session JSONL — PASS (with critical caveat)
- Parsed 200 lines of a live 3.6 MB session: `~/.claude/projects/.../305bb063-….jsonl`.
- Per-line `type` distribution: `assistant=93, user=72, permission-mode=14, last-prompt=13, attachment=5, system=2, file-history-snapshot=2`.
- Top-level keys observed (stable): `type/uuid/parentUuid/sessionId/message/timestamp/cwd/gitBranch/version/permissionMode/promptId/requestId/durationMs/toolUseResult/sourceToolAssistantUUID/lastPrompt/leafUuid/messageCount/messageId/snapshot/subtype/isMeta/isSidechain/isSnapshotUpdate/userType/entrypoint/attachment/content`.
- **Critical caveat**: The canonical `tool_calls / tool_responses / thinking_blocks / interrupts / hook_events / usage` fields are **NOT** at the top level. They must be derived by walking `assistant.message.content[].type=="tool_use"` and pairing `toolUseResult` records via `parentUuid`.
- **Implication**: Schedule a dedicated `Session.parse_jsonl` design spike before writing any #42796 metric keyword. The aggregation logic is the IP. Affects ADR-010.

### exp_08 — A2A Python SDK on PyPI — PASS
- `a2a-sdk 1.0.2` (Linux Foundation, ~30 releases) — adopt as primary.
- `python-a2a 0.5.10` (themanojdesai, 28 releases) — keep as secondary adapter.
- **Implication**: Phase 2 SubAgent module is unblocked. Confirms ADR-008.

### exp_09 — BFCL importable from `inspect_evals` — PASS
- `import inspect_evals.bfcl` succeeded.
- AST matcher source: `.venv/lib/python3.11/site-packages/inspect_evals/bfcl/bfcl.py`.
- **Implication**: Phase-1 BFCL keywords wrap `inspect_evals.bfcl` directly behind a thin `BFCLAdapter` to shield against upstream churn. Confirms ADR-004.

### exp_10 — RuFlo `aidefence_scan` — PARTIAL
- Direct CLI calls (`npx ruflo@latest …`, `npx @claude-flow/cli@latest …`) fail intermittently with `npm error ENOTEMPTY` cache-rename races; no `claude-flow`/`ruflo` binary on `PATH`.
- **However**, `.mcp.json` already declares the `claude-flow` MCP server, exposing `mcp__claude-flow__aidefence_{scan,is_safe,has_pii,analyze,stats,learn}`.
- **Architectural pivot**: Do NOT wrap aidefence as a CLI subprocess. The Phase-4 security keyword should call aidefence over MCP using the same client transport built in exp_01. Affects ADR-020.

## Confirmed assumptions (10)

1. FastMCP in-memory client roundtrip (~2 ms/call).
2. MCP Inspector CLI is suitable for CI compliance gating.
3. LiteLLM offline shape works without keys (`mock_response`).
4. Inspect AI Task/Solver/Scorer triad is composable; `mockllm/model` enables offline ATs.
5. `robotlibcore.DynamicCore` cleanly composes multiple sub-libraries.
6. scipy alone covers the StatsLibrary surface.
7. Claude Code JSONL field names are stable (parser is just aggregation).
8. `a2a-sdk` is mature on PyPI for Phase 2.
9. `inspect_evals.bfcl` is importable for Phase 1.
10. AIDefence is reachable via the `claude-flow` MCP server.

## Refuted / adjusted assumptions (4)

1. **`mcp-eval` 0.0.1 requires Python ≥3.12** — incompatible with 3.11. Decision: **bump library minimum to 3.12** (recommended) OR commit to `pytest-mcp` for Phase 1. Affects ADR-014 spec-version-pinning.
2. **`litellm.__version__` does not exist** — use `importlib.metadata.version("litellm")` in production code. Doc-level change to ADR-001.
3. **MCP Inspector `--help` is incomplete** (`--method` works but undocumented) — pin a known-good version and document the flag in our wrapper. Doc-level change to ADR-014.
4. **`aidefence` is reachable over MCP, not CLI** — wire the security-vetting keyword through MCP transport. Architectural change to ADR-020.

## Open questions

- Will `mcp-eval` ship a 3.11-compatible release in the Phase-1 window, or is 3.12 the floor?
- What is the realistic upper bound on session JSONL size (we sampled 3.6 MB; some agents may produce 100+ MB sessions — streaming parser required)?
- Does `a2a-sdk 1.0.2` cover all four bridge targets (LangGraph, CrewAI, AutoGen, OpenAI Agents SDK), or do we need adapter shims?
- Is the Inspector CLI `--method` flag stable enough to pin against, or do we need to call FastMCP directly for protocol-compliance probes?

## Top 3 architectural implications

1. **MCP-first is the right backbone end-to-end.** In-memory FastMCP delivers ~2 ms/call deterministic unit tests (exp_01); the same MCP client also reaches `aidefence_scan` (exp_10). One transport stack covers tool testing **and** security vetting — collapse the security module into the MCP module's client surface instead of a separate CLI shim.
2. **The session-JSONL parser is the single biggest piece of Phase-3 IP.** The canonical schema in research §7.2 is *not* present at the top level of real Claude Code JSONL — every field (`tool_calls`, `tool_responses`, `interrupts`, `hook_events`, `usage`) must be derived by walking per-line records and following `parentUuid`. Schedule a dedicated `Session.parse_jsonl` design spike before any #42796 metric keyword is written, and ship a Claude-Code parser first (we have a real fixture; Codex/Aider parsers come later).
3. **Pick the Python floor now (3.11 vs 3.12).** Targeting **3.12** unlocks `mcp-eval` (mature, async, OTel-native) and keeps `pytest-mcp` available; targeting 3.11 forces the library to ship its own Inspect-AI-based eval glue. Recommendation: **3.12** — the upside outweighs the user-base friction, and Robot Framework 7.x has full 3.12 support.
