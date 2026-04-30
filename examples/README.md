# Examples

Reference `.robot` suites that demonstrate AgentGuard keywords. Phase-1 suites
are runnable today; Phase-2 / Phase-3 suites are placeholders that document the
intended shape and `Skip` themselves at runtime so you can copy them and adapt
without surprises.

## Run a single suite

```bash
PYTHONPATH=. uv run robot examples/01_mcp_server_basics.robot
```

(`PYTHONPATH=.` is needed so the suites can import the in-process fixtures
under `tests/fixtures/`.)

## Run every example except docker-gated ones

```bash
PYTHONPATH=. uv run robot --exclude docker --exclude pending examples/
```

## What is in scope per phase

| File                                | Phase | Status   | Notes                                                  |
|-------------------------------------|-------|----------|--------------------------------------------------------|
| `01_mcp_server_basics.robot`        | 1     | Runnable | Uses in-memory FastMCP echo fixture                    |
| `02_skill_grading.robot`            | 1     | Runnable | Uses `mockllm/model` (offline)                         |
| `03_hook_block_destructive.robot`   | 2     | Runnable | Real hooks against `tests/fixtures/hooks/*.sh`         |
| `04_subagent_a2a.robot`             | 2     | Runnable | In-process travel-planner + child agent fixtures       |
| `05_coding_agent_metrics.robot`     | 3     | Runnable | Real #42796 metric pack against synthetic Claude JSONL |
| `06_bfcl_tool_selection.robot`      | 1     | Runnable | Uses 30-case golden fixture                            |
| `07_sandbox_run.robot`              | 2     | Runnable | Real Docker backend; tag `docker` to opt out in CI     |
| `08_swe_bench.robot`                | 3     | Runnable | SWE-bench loader smoke (mini-fixture fallback); `slow` |
| `09_humaneval_live.robot`           | 3     | Live     | OpenRouter HumanEval smoke; `live` tag, needs API key  |

The `Skip` placeholders are intentional. They show contributors *exactly* where
new keywords plug in, and they keep `examples/` in sync with the phased roadmap
in [`docs/PLAN.md`](../docs/PLAN.md) §8.

### Phase 2 examples in detail

- **`03_hook_block_destructive.robot`** — five test cases against real shell-script hooks:
  - `PreToolUse` blocks `rm -rf /` (security_check.sh, exit-2 = block).
  - `Stop` hook returns `block` with `Test suite must pass`.
  - Anti-loop: `Stop` honours `stop_hook_active=True` and allows.
  - `Hook Should Inject Context` against an `additional_context` payload.
  - `Detect Stop Hook Loop` over five repeated blocks (loop_trap.sh).
- **`04_subagent_a2a.robot`** — three test cases using the composite
  `travel_planner` fixture (delegates to `weather-agent` + `places-agent`):
  - `Get Agent Card` lists the planner's `trip.plan` skill.
  - Send Task / Wait For Task Completion / `Task Trajectory Should Match`
    asserts the BFCL-shaped `delegate -> delegate -> compose` chain.
  - `Get Task Artifact` exposes the delegation-chain metadata.
- **`07_sandbox_run.robot`** — two test cases against the Docker backend:
  - `Sandbox Should Be Available docker` probes the daemon.
  - Default-deny policy + `python -c "print('hi')"` inside `python:3.12-alpine`.
    Skipped automatically when the host's docker rejects the secure profile
    (snap-installed docker is the canonical case).

### Phase 3 examples in detail

- **`05_coding_agent_metrics.robot`** — mirrors research §6.5: `Parse Session
  JSONL` against `tests/fixtures/coding_agent/sessions/claude_code_with_tools.jsonl`,
  then asserts `Read Edit Ratio Should Be Above 1.0`,
  `Edits Without Prior Read Percent Should Be Below 50`, and the
  `Stop Hook Violations Should Be Zero` antipattern guard. Thresholds are
  intentionally loose — the fixture is small and the point is wiring, not
  production gating. Also exercises the aggregate `Compute 42796 Metric Pack`
  to log a full `BehavioralReport`.
- **`08_swe_bench.robot`** — SWE-bench Verified loader smoke. Uses the bundled
  mini-fixture fallback when the `[benchmarks]` extra (`datasets>=3.0`) is
  not installed. Asserts the loader returns a populated `Task` dataclass —
  the real apply-patch + run-tests-under-Docker loop is Phase-4 work.
- **`09_humaneval_live.robot`** — single-task HumanEval against
  `openrouter/openai/gpt-4o-mini` via the LocalDriver. Tagged `live`; the
  suite-level `Skip If Live Disabled` short-circuits when `OPENROUTER_API_KEY`
  is unset. Threshold is `-0.001` because this is a wiring smoke, not a
  pass@k quality benchmark (gpt-4o-mini against one task is not statistically
  meaningful, and HumanEval is a leaked-into-pretraining set anyway).

## Fixtures

Phase-1 suites read from `tests/fixtures/`:

- `tests/fixtures/mcp/echo_server.py` — in-memory FastMCP echo+add server
- `tests/fixtures/skills/sample-skill/SKILL.md` — minimal valid skill
- `tests/fixtures/tool_calls/golden_calls.json` — 30 BFCL-shaped pairs

Phase-2 suites add:

- `tests/fixtures/hooks/security_check.sh` — destructive-bash blocker
- `tests/fixtures/hooks/require_tests.sh` — Stop hook honouring `stop_hook_active`
- `tests/fixtures/hooks/inject_context.sh` — `additional_context` injector
- `tests/fixtures/hooks/loop_trap.sh` — always-block Stop antipattern
- `tests/fixtures/hooks/echo_decision.py` — Python echo-decision fixture
- `tests/fixtures/a2a/travel_planner.py` — composite in-process A2A agent

Phase-3 suites add:

- `tests/fixtures/coding_agent/sessions/claude_code_with_tools.jsonl` —
  synthetic Claude Code JSONL with realistic `tool_use` / `toolUseResult`
  pairing (the IP-bearing parser fixture).
- `tests/fixtures/coding_agent/sessions/claude_code_minimal.jsonl` —
  no-tools session for sanity-checking the parser's degenerate path.
- `tests/fixtures/coding_agent/benchmarks/{humaneval,mbpp}_mini.json` —
  mini-fixture fallbacks used when `datasets` is not installed.

If a suite errors on a missing fixture, the corresponding owning agent
(see `.swarm-coordination.md`) has not yet shipped it.

## Live mode

To run the same suites against a real provider, set
`OPENROUTER_API_KEY` in `.env` and pass `--include live` plus a real
`model=` argument. The Phase-1 examples default to mock providers so they pass
without any network access.
