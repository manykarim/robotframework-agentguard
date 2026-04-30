# Proposal: Replace rf-mcp's `tests/e2e/` with AgentGuard's TestHarness

**Author**: agentguard-architecture-swarm
**Date**: 2026-05-01
**Status**: Proposed (gates on ADR-021 acceptance)
**Goal**: A full and complete test harness for **MCP Servers**, **Agent Skills**, and **Coding Agents** — built on AgentGuard's existing 132-keyword surface plus the 23 new TestHarness keywords from ADR-021.

---

## 1. What rf-mcp's e2e harness does, in 60 seconds

```
                     ┌──────────────────┐
   tests/e2e/        │ scenarios/*.yaml │   17 scenario YAMLs (web, api, mobile, …)
   ─────────────     └────────┬─────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │  Scenario        │ pydantic model: id, prompt, expected_tools[],
                     │  (models.py)     │ min_tool_hit_rate, tags, expected_outcome
                     └────────┬─────────┘
                              │
                              ▼
        ┌───────────────────────────────────────┐
        │  test_autonomous_agent_with_scenario  │ pytest parametrized over 17 YAMLs
        └────────┬──────────────────────────────┘
                 │
        ┌────────┴───────────┐
        │ PydanticAI Agent   │  with USE_REAL_LLM=true → OpenAI gpt-5-mini
        │  + MCP tools       │
        └────────┬───────────┘
                 │ all call_tool() invocations
                 ▼
        ┌───────────────────────────────┐         ┌──────────────────────┐
        │  TrackedMCPClient             │ ──────▶ │ MetricsCollector     │
        │  (wraps fastmcp.Client)       │         │  ToolCallRecord[]    │
        └───────────────────────────────┘         └──────────┬───────────┘
                                                             │
                                                             ▼
                                                  ┌──────────────────────┐
                                                  │  ScenarioResult JSON │ → metrics/<id>_<ts>.json
                                                  │  tool_hit_rate, ...  │   (375+ in upstream)
                                                  └──────────────────────┘
                                                             │
                                                             ▼
                                                  ┌──────────────────────┐
                                                  │  Pytest assertions   │
                                                  │  hit_rate ≥ X        │
                                                  │  failed ≤ N          │
                                                  │  expected tools ⊆ called
                                                  └──────────────────────┘
```

**Five primitives:** Scenario YAML · TrackedMCPClient · MetricsCollector · ScenarioResult · autonomous-agent driver.

---

## 2. Mapping table: rf-mcp ↔ AgentGuard

| rf-mcp construct | rf-mcp file | AgentGuard equivalent (today) | Status |
|---|---|---|---|
| `Scenario` (pydantic) | `models.py:16` | — | **NEW** — `Scenario` dataclass |
| `ExpectedToolCall(name, min_calls, max_calls, required_params)` | `models.py:7` | `ExpectedCall(name, arguments)` (BFCL, single-call) | **NEW** — aggregate-counting variant |
| `ToolCallRecord(name, arguments, success, result, error, timestamp)` | `models.py:41` | `ToolCall(id, name, arguments, timestamp)` from `coding_agent/session/types.py` | **EXTEND** — add `success/result/error` |
| `ScenarioResult` (JSON output) | `models.py:52` | `SkillScorecard` (skill-only) | **NEW** — scenario-shaped variant |
| `MetricsCollector` (in-memory) | `metrics_collector.py:12` | — | **NEW** — `TrackedMCPSession` |
| `MetricsCollector.calculate_tool_hit_rate` | `metrics_collector.py:57` | — | **NEW** — `Tool Hit Rate` keyword |
| `MetricsCollector.get_summary_stats` | `metrics_collector.py:174` | — | **NEW** — `Tool Call Statistics` keyword |
| `TrackedMCPClient` (wraps `fastmcp.Client`) | `tracked_client.py:10` | `MCPKeywords.call_mcp_tool` (manual) | **NEW** — auto-recording wrapper |
| `MCPAgentIntegration` (PydanticAI agent + MCP tools) | `agent_integration.py` | `LocalDriver` (synthetic ReAct, no MCP target) | **EXTEND** — `LocalDriver(mcp_server=...)` |
| `scenarios/*.yaml` parametrized | `test_autonomous_agents.py:93` | — | **NEW** — `Run MCP Scenario` keyword |
| `metrics/<id>_<ts>.json` artifact | written by `save_metrics` | `SkillScorecard.save` (skill JSON) | **NEW** — `Save Scenario Result` |
| `USE_REAL_LLM=true` env gate | `test_autonomous_agents.py:14` | `@pytest.mark.live` + `OPENROUTER_API_KEY` | ✅ exists |
| Tool sequence ordered match | (rf-mcp doesn't have this) | `Tool Sequence Should Match` (BFCL) | ✅ exists — extra value |
| `Required Parameters Should Be Present` | (rf-mcp does it inline) | `Required Parameters Should Be Present` | ✅ exists |

**Net new code surface: 23 keywords** in one new sub-library (`AgentGuard.mcp_scenario.library.MCPScenarioKeywords`).

---

## 3. Side-by-side test rewrite (the proof point)

### 3.1 rf-mcp's `restful_booker_api.yaml` scenario

```yaml
id: restful_booker_api
context: api
prompt: |
  Use RobotMCP to write a test suite and execute it step wise.
  Read https://restful-booker.herokuapp.com/apidoc/index.html ...
expected_tools:
  - tool_name: analyze_scenario
    min_calls: 1
    max_calls: 1
  - tool_name: recommend_libraries
    min_calls: 0
    max_calls: 2
  - tool_name: manage_session
    min_calls: 1
    max_calls: 3
  - tool_name: execute_step
    min_calls: 4
    max_calls: 20
  - tool_name: build_test_suite
    min_calls: 1
    max_calls: 1
min_tool_hit_rate: 0.70
tags: [api, http, restful-booker, authentication]
```

### 3.2 rf-mcp's pytest test (Python, ~50 LOC)

```python
@pytest.mark.skipif(not should_use_real_llm(), reason="Requires USE_REAL_LLM=true")
@pytest.mark.parametrize("scenario_file", get_all_scenarios(), ids=lambda p: p.stem)
async def test_autonomous_agent_with_scenario(scenario_file, mcp_server, metrics_collector):
    scenario = load_scenario(scenario_file)
    integration = MCPAgentIntegration(mcp_server, metrics_collector)
    agent = integration.create_agent_with_mcp_tools(model_name=get_model_name())
    metrics_collector.start_recording()
    output, _ = await integration.run_agent_with_scenario(agent, scenario.prompt)
    metrics_collector.stop_recording()
    result = metrics_collector.generate_result(scenario, agent_output=output)
    metrics_collector.save_metrics(result, Path("tests/e2e/metrics"))
    assert result.tool_hit_rate >= scenario.min_tool_hit_rate
    failed = [tc for tc in metrics_collector.tool_calls if not tc.success]
    assert len(failed) <= 2
```

### 3.3 AgentGuard equivalent — Robot Framework (≤ 15 LOC)

```robot
*** Settings ***
Library    AgentGuard
Suite Setup       Connect Rf Mcp + Tracked Session
Suite Teardown    End Tracked MCP Session    ${SESSION}

*** Variables ***
${SCENARIO_DIR}    ${EXECDIR}/../rf-mcp/tests/e2e/scenarios

*** Test Cases ***
Restful Booker Scenario Hit Rate Above 70 Percent
    [Tags]    rf-mcp    e2e    live    api
    ${scenario}=    Load MCP Scenario    ${SCENARIO_DIR}/restful_booker_api.yaml
    ${result}=    Run MCP Scenario    ${scenario}    server=${HANDLE}
    ...    driver=local    model=openrouter/openai/gpt-4o-mini
    Tool Hit Rate Should Be Above    ${result}    ${scenario.min_tool_hit_rate}
    Failed Tool Call Count Should Be At Most    ${result}    2
    Save Scenario Result    ${result}    ${OUTPUT_DIR}/restful_booker_api.json

*** Keywords ***
Connect Rf Mcp + Tracked Session
    ${server}=    Evaluate    __import__('robotmcp.server', fromlist=['mcp']).mcp
    ${HANDLE}=    Connect To MCP Server    ${server}    transport=memory
    ${SESSION}=    Start Tracked MCP Session    ${HANDLE}
    Set Suite Variable    ${HANDLE}
    Set Suite Variable    ${SESSION}
```

The pytest version is 50 LOC of Python scattered across `test_autonomous_agents.py`, `metrics_collector.py`, `tracked_client.py`, `models.py`, `agent_integration.py`, `fixtures.py`, `scenario_loader.py` (≈ 600 LOC of supporting code). The Robot version is **15 LOC + a one-line scenario load**, and every keyword shows up in `log.html` with its inputs, outputs, and recorded tool calls.

### 3.4 The scenario YAML is unchanged

Same field names. Same semantics. **Drop-in adoption.** Pull rf-mcp's `tests/e2e/scenarios/` into `tests/fixtures/mcp_scenarios/`, add the Robot test above, and rf-mcp's full e2e matrix runs through AgentGuard.

---

## 4. Tool-call statistics — what AgentGuard will expose

Per rf-mcp `metrics_collector.py:174-195` (`get_summary_stats`):

| Statistic | rf-mcp source | AgentGuard keyword | Default threshold |
|---|---|---|---|
| `total_tool_calls` | `len(tool_calls)` | `Tool Call Count` (Get) / `Tool Call Count Should Be Between` | scenario-defined |
| `successful_calls` | `sum(success)` | (returned in stats dict) | — |
| `failed_calls` | `total - successful` | `Failed Tool Call Count Should Be At Most` | scenario-defined |
| `success_rate` | `successful/total` | `Tool Call Success Rate Should Be Above` | 0.85 |
| `tool_call_counts[name]` | `Counter` over names | `Tool Call Count` with `name=` filter | — |
| `unique_tools_called` | `len(counter)` | (in stats dict) | — |
| `tool_hit_rate` | per `calculate_tool_hit_rate` | `Tool Hit Rate Should Be Above` | scenario-defined |
| `tool_call_records[]` (full) | `metrics_collector.tool_calls` | `Get Tool Call Records` | — |

The `Tool Call Statistics` keyword returns the dict above as a Robot dict, suitable for further filtering or for `Log Many` in the test report.

---

## 5. Generated-artifact analysis — closing the loop

rf-mcp scenarios produce **two artifacts** worth analyzing:
1. The **scenario JSON metric file** (`metrics/<id>_<ts>.json`) — tracked above.
2. The **generated Robot Framework test suite** that the agent built via `build_test_suite`. rf-mcp tests today do not validate the suite itself; AgentGuard adds:

```robot
${result}=    Run MCP Scenario    ${scenario}    server=${HANDLE}
${suite_path}=    Get Generated Robot Suite Path    ${result}
Generated Robot Suite Should Pass    ${suite_path}    timeout=120s
```

Implementation: `Run MCP Scenario` introspects each `tool_call.result` for `build_test_suite`'s output path, stores it under `result.metadata["generated_suites"]`. `Generated Robot Suite Should Pass` runs `robot --dryrun` (or full execution if `mode=full`) on the captured path and asserts the suite is valid + passes.

This is **strictly net-new validation** — rf-mcp does not test that the agent's emitted suite is syntactically valid Robot Framework, only that the agent called `build_test_suite`. AgentGuard would.

Other artifacts captured into `result.metadata` by default:
- `generated_suites: list[Path]` — paths to `*.robot` files written during the run.
- `session_state: dict` — last `get_session_state` snapshot (when applicable).
- `cwd: Path` — the working directory at run start (for delta computation).
- `files_created: list[Path]` — diff of `cwd` after the run vs before.
- `cost_usd: float` — from the LiteLLM provider.
- `model: str` — exact model identifier.

`Get Generated Files` returns `metadata["files_created"]`. `Generated Artifact Should Match Schema` JSON-schema-validates any structured artifact.

---

## 6. The unified harness vision (across the three pillars)

The `Scenario` abstraction generalizes naturally. Same primitives, three audiences:

### MCP Servers — the rf-mcp pattern (this proposal's focus)
```robot
${result}=    Run MCP Scenario    ${scenario}    server=${RF_MCP_HANDLE}    driver=local
Tool Hit Rate Should Be Above    ${result}    0.7
Generated Robot Suite Should Pass    ${result.metadata}[generated_suites][0]
```

### Agent Skills — extension via `skill=` parameter
```robot
${scenario}=    Load MCP Scenario    scenarios/skill_uses_browser.yaml
${result}=    Run MCP Scenario    ${scenario}    skill=${BROWSER_SKILL}    driver=local
Tool Hit Rate Should Be Above    ${result}    0.8
Skill Output For Prompts Should Be Semantically Equal    ${result}    ${expected_responses}
```
The skill is loaded as system message; the scenario's `expected_tools` become "the agent should invoke these MCP tools when handed this skill". Reuses `SkillsKeywords.run_skill_eval` under the hood.

### Coding Agents — replaces benchmark loaders' assertion side
```robot
${scenario}=    Load MCP Scenario    scenarios/swe_bench_django_42.yaml
${result}=    Run MCP Scenario    ${scenario}    driver=claude-code    repo=fixtures/django
Tool Hit Rate Should Be Above    ${result}    0.6
First Run Test Pass Rate Should Be Above    ${result.session}    0.8
${suite}=    Get Generated Robot Suite Path    ${result}
Generated Robot Suite Should Pass    ${suite}
```
The CodingAgent driver from Phase 3 fits without modification — `result.session` is the JSONL-parsed Session, and the existing 12 #42796 calculators apply directly.

**One Scenario abstraction. Three driver targets. Same assertion vocabulary.** That is what makes this "a full and complete test harness".

---

## 7. Migration path for rf-mcp users

Three steps, no code rewrite required for the YAML scenarios:

1. `pip install robotframework-agentguard[integrations]` (already adds rf-mcp).
2. Copy scenarios verbatim: `cp -r path/to/rf-mcp/tests/e2e/scenarios tests/fixtures/mcp_scenarios`.
3. Add a Robot suite per scenario (or one parametrized suite using `Set Test Variable` over a glob), per §3.3 above.

The existing 375+ `metrics/*.json` artifacts can be loaded into AgentGuard for retrospective analysis:
```robot
${past}=    Load Scenario Result    metrics/restful_booker_api_20260214_222742.json
${current}=    Run MCP Scenario    ${scenario}    server=${HANDLE}
Tool Hit Rate Distribution Should Stochastically Dominate    ${current}    ${past}    alpha=0.05
```

That's a **Mann-Whitney across historical runs** — an analysis rf-mcp's own harness does not provide today.

---

## 8. Risk register for the proposal

| # | Risk | Mitigation |
|---|---|---|
| R1 | rf-mcp scenario YAML schema evolves | Pin to v1 per ADR-014; emit deprecation warning on unknown keys (ADR-006 forwards-compat pattern). |
| R2 | `LocalDriver(mcp_server=...)` couples driver to MCP module | Optional parameter; drivers without it keep current behavior. |
| R3 | Tool Hit Rate misclassifies "called many times incorrectly" as success | Add `Required Tool Should Have Been Called With Params` per-`required_params` check (rf-mcp already does this; we expose it as a separate keyword). |
| R4 | Generated suites may run untrusted code | `Generated Robot Suite Should Pass` defaults to `--dryrun`; full execution requires `--allow-code-execution` flag (consistent with ADR-013). |
| R5 | Live-LLM cost balloons across N scenarios | Default driver=`local` with `model=openrouter/openai/gpt-4o-mini` (cheap); explicit `tier=3` opt-in for Sonnet/Opus. |
| R6 | rf-mcp's `agent_integration.py` uses Pydantic AI; AgentGuard uses LiteLLM | LiteLLM has been validated through Phase 0 (exp_03) and Phase 3 (LocalDriver live runs); shape parity is fine. Mention as a portability difference — same surface, different innards. |

---

## 9. Phasing (gates on ADR-021)

- **Phase 4-A (1 month, MVP)** — `MCPScenarioKeywords` (12 of 23 keywords): scenario load/save/run, tracked-session wrapper, hit rate, scenario result save/load. **Gate**: AgentGuard runs all 17 rf-mcp scenarios with byte-equivalent JSON artifacts.
- **Phase 4-B (1 month, autonomous + artifacts)** — `LocalDriver(mcp_server=...)`, generated-suite analysis (4 keywords), Claude-Code driver `--mcp-config` injection. **Gate**: `examples/12_mcp_scenario_replacement.robot` reproduces three rf-mcp scenarios live with OpenRouter.
- **Phase 4-C (½ month, statistical comparison)** — Mann-Whitney/Cliff's-δ keywords, OTel scenario-tag emission, libdoc HTML, full migration guide. **Gate**: rf-mcp upstream consumes AgentGuard as its e2e backend (or equivalent third-party validation).

Total Phase-4 budget: **2.5 months sequential or 1.5 months parallel** with the 7-agent swarm pattern.

---

## 10. Files this proposal would add (when implemented)

```
src/AgentGuard/mcp_scenario/
├── __init__.py
├── library.py           # MCPScenarioKeywords (the 23 keywords)
├── types.py             # Scenario, ExpectedToolCall, ToolCallRecord, ScenarioResult
├── loader.py            # YAML load/save (rf-mcp v1 schema)
├── tracker.py           # TrackedMCPSession (wraps ServerHandle)
├── runner.py            # ScenarioRunner — driver dispatch + execution
├── statistics.py        # tool_hit_rate, success_rate, summary_stats (pure-python)
├── artifacts.py         # generated-suite extraction + validation
└── schema.json          # Scenario YAML JSON-schema for validation

src/AgentGuard/coding_agent/drivers/local.py    # extend with `mcp_server=` param

tests/fixtures/mcp_scenarios/                   # 17 rf-mcp scenarios + a few new ones
tests/integration/test_mcp_scenario_*.py
tests/integration/test_rf_mcp_scenario_replacement.py     # explicit drop-in proof
tests/acceptance/mcp_scenario/*.robot
examples/12_mcp_scenario_replacement.robot

docs/api/AgentGuard.MCPScenario.html             # libdoc
docs/PHASE-4-COMPLETE.md
```

Estimated source-LOC: ~1500 (smaller than Phase 3's coding_agent module since most plumbing already exists).

---

## 11. Open questions for review

1. Should the Scenario YAML allow nested `expected_tools[].sequence` to combine BFCL ordered match with hit-rate aggregate? (Recommend: defer to v2.)
2. Should `Generated Robot Suite Should Pass` default to `--dryrun` or full execution? (Recommend: `--dryrun` for safety; full requires `--allow-code-execution`.)
3. Should the `MCPScenario` context support **non-MCP** scenarios (e.g. for Skills + CodingAgents pillars)? (Yes per §6, but that requires renaming → `Scenario`/`ScenarioRun` for both YAML schema and keywords. Deferred to Phase 4-B.)
4. Should we adopt rf-mcp's `pydantic` model layer or stick with our `dataclass` convention? (Recommend: dataclass + `cattrs` for round-trip; pydantic adds a heavy dep we currently lack on the prod path.)

---

## 12. Cross-references

- **ADR-021** — formal decision record (this proposal's blocker).
- **DDD updates** — `docs/ddd/bounded-contexts.md` (NEW: TestHarness context), `docs/ddd/context-map.md` (NEW: relations to MCP / Skills / CodingAgent / Stats / ToolCallCorrectness).
- **PLAN updates** — `docs/PLAN.md` §8 Phase 4-A/B/C inserted.
- **Source of truth** — `manykarim/rf-mcp/tests/e2e/` at the commit observed locally; `metrics_collector.py:57-99` for hit-rate formula.
