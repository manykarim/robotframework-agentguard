# Proposal: Adopt AssertionEngine as the Shared Assertion Idiom

**Author**: agentguard-architecture-swarm
**Date**: 2026-04-29
**Status**: Proposed (gates on ADR-022 acceptance)
**Goal**: Collapse AgentGuard's 163-keyword surface to a single `Get<X>` + `assertion_operator=` idiom by adopting the `robotframework-assertion-engine` shared kernel — the same pattern used by Browser Library, ApiLibraryCore, and JSONLibrary — without sacrificing the tier-aware semantics that make the current Should-pair surface readable.

---

## 1. What AssertionEngine is, in 60 seconds

```
   *.robot                       AgentGuard sub-library                AssertionEngine
   ────────                      ──────────────────────                ──────────────────
                                                                       (shared kernel)

   Read Edit Ratio   ──────▶   ┌──────────────────────────┐         ┌──────────────────────┐
   ${session}                  │ @keyword                 │         │                      │
   >=                          │ def read_edit_ratio(     │ ──────▶ │ verify_assertion(    │
   4.0                         │     session,             │         │   value=4.7,         │
                               │     assertion_operator,  │         │   operator=>=,       │
                               │     assertion_expected,  │         │   expected=4.0,      │
                               │     message=None,        │         │   message=None,      │
                               │     polling=None):       │         │   polling=None )     │
                               │   value = compute(...)   │         │                      │
                               │   return verify(...)     │ ◀────── │ → returns value      │
                               └──────────────────────────┘         │ → raises if mismatch │
                                                                    └──────────────────────┘
                                                                              │
                                                                              ▼
                                                                    log.html: ONE keyword
                                                                    line, with operator,
                                                                    expected, actual, ms.
```

**The problem.** AgentGuard ships 163 keywords across 11 sub-libraries (CodingAgent, MCPScenario, Stats, Skills, Security, Hooks, ToolCallCorrectness, MCP, SubAgents, Judge, Telemetry). Roughly half are split across the `Get<Metric>` / `<Metric> Should Be Above|Below|Between|Equal To|Zero` idiom, doubling the libdoc surface and forcing every test author to remember which keyword *also* sets a Robot variable. The split also misaligns AgentGuard with the rest of the RF ecosystem — Browser Library, ApiLibraryCore, JSONLibrary, and DatabaseLibrary all expose a single `Get<X>` keyword that takes an inline `assertion_operator` parameter and lets `robotframework-assertion-engine` perform the comparison in one log line.

---

## 2. Mapping table: AgentGuard ↔ AssertionEngine

| Sub-library | Current keyword count | Post-migration count | Biggest collapsible pair |
|---|---|---|---|
| **CodingAgent** | 25 | 13 | `Read Edit Ratio` + `Read Edit Ratio Should Be Above` → `Read Edit Ratio` |
| **CodingAgent.Benchmarks** | 8 | 4 | `SWE Bench Pass At K` + `SWE Bench Pass At K Should Be Above` → `SWE Bench Pass At K` |
| **MCPScenario** | 23 | 14 | `Tool Hit Rate` + `Tool Hit Rate Should Be Above` → `Tool Hit Rate` |
| **Stats** | 16 | 11 | `Pass At K` + `Pass At K Should Be Above` → `Pass At K` (Mann-Whitney/Cliff's δ stay paired — see §6) |
| **Skills** | 18 | 10 | `Skill Pass Rate` + `Skill Pass Rate Should Be Above` → `Skill Pass Rate` |
| **Security** | 14 | 9 | `Security Score` + `Security Score Should Be Above` → `Security Score` |
| **Hooks** | 11 | 8 | `Hook Block Count` + `Hook Block Count Should Be At Most` → `Hook Block Count` (predicates stay) |
| **ToolCallCorrectness** | 17 | 11 | `Tool Sequence Match Rate` + `... Should Be Above` → `Tool Sequence Match Rate` |
| **MCP** | 12 | 9 | `MCP Tool Call Latency Ms` + `... Should Be Below` → `MCP Tool Call Latency Ms` |
| **SubAgents** | 9 | 6 | `Subagent Handoff Success Rate` + `... Should Be Above` → `Subagent Handoff Success Rate` |
| **Judge** | 10 | 7 | `Judge Score` + `Judge Score Should Be Above` → `Judge Score` |
| **TOTAL** | **163** | **102** | **−37%** surface reduction |

> Authoritative per-keyword numbers and column-by-column diffs live in the analyst's table: `docs/proposals/keyword-reduction-table.md`. The numbers above are reproduced from that file; if they ever disagree, the table wins.

---

## 3. Side-by-side test rewrite (the proof point)

The highest-leverage example is `examples/05_coding_agent_metrics.robot` — the #42796 metric pack. It exercises 5 of the 12 calculators in 7 lines, and every line is a Should-pair.

### 3.1 BEFORE — current Should-pair idiom (7 keyword calls, 7+5 keyword definitions in libdoc)

```robot
*** Test Cases ***
Claude Code Maintains Healthy Read-Edit Discipline
    ${session}=    Parse Session JSONL    ${SESSION_PATH}
    Read Edit Ratio Should Be Above                          ${session}    1.0
    Edits Without Prior Read Percent Should Be Below         ${session}    50
    Reasoning Loops Per 1K Tool Calls Should Be Below        ${session}    100
    User Interrupts Per 1K Should Be Below                   ${session}    50
    Stop Hook Violations Should Be Zero                      ${session}
```

Each `... Should ...` keyword is a thin wrapper that calls `Get<Metric>` internally and then re-implements `>` / `<` / `==` over the result. In `log.html` each row shows **two** keyword calls (the outer Should + the inner Get) and a `BuiltIn.Should Be True` underneath them.

### 3.2 AFTER — AssertionEngine idiom (7 keyword calls, 5 keyword definitions in libdoc)

```robot
*** Test Cases ***
Claude Code Maintains Healthy Read-Edit Discipline
    ${session}=    Parse Session JSONL    ${SESSION_PATH}
    Read Edit Ratio                          ${session}    >=    1.0
    Edits Without Prior Read Percent         ${session}    <     50
    Reasoning Loops Per 1K Tool Calls        ${session}    <     100
    User Interrupts Per 1K                   ${session}    <     50
    Stop Hook Violations                     ${session}    ==    0
```

The same line *also* still works as a getter with no assertion (`${ratio}=    Read Edit Ratio    ${session}`) because `assertion_operator` defaults to `None` — exactly Browser Library's pattern.

### 3.3 `log.html` rendering difference

| | Before (Should-pair) | After (AssertionEngine) |
|---|---|---|
| Rows per assertion | 2 (outer Should + inner Get) + 1 BuiltIn | 1 (single keyword with operator/expected/actual columns) |
| KEYWORD log lines for the test above | 7 outer + 5 inner + 5 BuiltIn = **17** | **5** |
| Failure message | "Edits Without Prior Read Percent 62.0 is not below 50" | "Edits Without Prior Read Percent 62.0 < 50 failed" with operator/expected/actual columns |

Roughly a **3× reduction in `log.html` row count** for assertion-heavy suites, and one fewer cognitive jump when scanning for the failure point.

---

## 4. Operator surface in AgentGuard

AssertionEngine ships ~22 operators (full inventory: `docs/research/assertion-engine.md` §3). AgentGuard adopts the operator catalog as-is; we expose a curated subset by default and gate the rest:

| Operator | AgentGuard tier | Use case | Notes |
|---|---|---|---|
| `==`, `equal`, `should be` | always-on | exact metric comparisons | most common for counters / ids |
| `!=`, `inequal`, `should not be` | always-on | negation | |
| `>`, `>=`, `<`, `<=` | always-on | thresholds | the bread-and-butter for #42796 metrics |
| `contains`, `not contains` | always-on | substring / list membership | tool-name lists, error messages |
| `*=`, `^=`, `$=` (glob/prefix/suffix) | always-on | shape checks on names | e.g. `${name}    ^=    bash:` |
| `matches` (regex) | always-on | structured ids | session ids, run ids |
| `then`, `evaluate` | always-on | scalar arithmetic on the captured value | safe — no eval over user input |
| `validate` | **gated** by `--allow-code-execution` | arbitrary Python lambda body | Sandboxed per ADR-013; `CodeExecutionDeniedError` without the flag |

**Operators we will *not* expose by default**: `validate` (Python eval), `then` chains that re-enter `verify_assertion` recursively, and any custom operator that takes a callable. These are gated behind the same `allow_code_execution` flag that gates Inspect AI sandbox runs (ADR-013), keeping a single consent surface for "AgentGuard may execute code I supplied".

---

## 5. ~~Backwards-compatibility plan~~ → One-shot full replacement (revised 2026-05-05)

**There is no backwards-compatibility plan.** AgentGuard 0.1.0 has not been published to PyPI and there are no external consumers depending on the current Should-pair surface. Per the user's directive, the migration ships the end state directly:

- **No shim wrappers.** Each collapsible Should-pair keyword is *deleted* from its `library.py` in the same commit that adds the operator parameters to the corresponding Get keyword.
- **No `DeprecationWarning` plumbing.** No warning-suppression env var, no warning-regression tests, no migration-window release notes column.
- **No multi-phase deprecation window.** Phase 4-D ships the final 131-keyword surface in one pass.

The only break-risk window is between this PR's merge and the eventual 0.1 PyPI release: anyone tracking `main` directly updates their `.robot` suites once. Documented in the release notes for 0.2.0.

This decision saves the deprecation tax that the original three-phase plan would have cost: ≈ +5 temporary keywords during the window, ≈ 4 days of swarm time, the shim-coverage test surface, and the migration-warning regression net. The end state is *strictly* the same number of keywords (131) but the codebase ships there directly without intermediate state.

---

## 6. Risk register

| # | Risk | Mitigation |
|---|---|---|
| R1 | Polling cost balloon for Tier-2/3 keywords (e.g. live LLM calls) — applies if a future Browser-style polling decorator is built on top of the AssertionAdapter | `AssertionAdapter` rejects `polling=...` when the keyword's tier ≥ 2 (per ADR-019); raises `PollingNotPermittedError` with remediation text. |
| R2 | `validate` operator code execution | Gated behind ADR-013 sandbox + `--allow-code-execution`; without the flag the adapter strips `validate` from the operator allowlist and raises `CodeExecutionDeniedError`. |
| R3 | One-shot break for users tracking `main` directly | The break window is the merge-to-0.1-release interval. Release notes for 0.2.0 ship a 1-page Before→After table; the surface change is mechanical (s/`Should Be Above ${a} ${b}`/`${a} >= ${b}`/g per pattern). |
| R4 | libdoc HTML diff is large (one commit changes every sub-library) | Acceptable — the diff is mostly autogenerated and reviewable as a single artifact. The PR description anchors the 11 libdoc files for review. |
| R5 | Mann-Whitney / Cliff's δ keywords don't fit the operator pattern (their "expected" is a *distribution*, not a scalar) | Keep them as Should-style. `Tool Hit Rate Distribution Should Stochastically Dominate` and `Mann Whitney U Should Show Improvement` are excluded from the migration — explicitly retained per the analyst's edge-case set. |
| R6 | Predicates without scalar values (`Should Not Call Any Tool`, `Hook Should Block`, `Skill Should Pass Security Scan`) | Kept as-is **for readability**, not because `validate` cannot express them. `tests/experiments/exp_12_aggressive_collapse.robot` (16/16 PASS) proves they *technically* fold into `validate ... value.decision != 'deny'` etc.; they stay as named keywords because the call site reads cleaner. Per user goal "small focused keywords with simple syntax", readability beats raw count. |
| R7 | Aggressive-collapse temptation creep over time | Documented policy in `docs/ddd/assertion-engine-shared-kernel.md`: a Should-pair collapses iff the operator form reads ≥ as cleanly as the Should form. Predicates and composite-pipeline assertions stay. |

---

## 7. Phase 4-D — One-shot replacement (1.5 weeks, single phase)

| Day | Scope | Files touched (LOC) | Test surface | libdoc |
|---|---|---|---|---|
| **1–2** | Foundation: `_assertions/{adapter,operators,polling}.py`; `pyproject.toml` adds `robotframework-assertion-engine >= 4.0, < 5.0`; `tests/unit/_assertions/` covers adapter / validate-gate / polling-gate. | ~400 LOC new under `src/AgentGuard/_assertions/` + ~200 LOC tests | New | New `AgentGuard._assertions` page (private; not user-facing) |
| **3–4** | Collapse pass A: `CodingAgentKeywords` (12 metric pairs → 12 keywords) + `MCPScenarioKeywords` (5 pairs collapsed). Delete the Should-pair keywords; update existing tests + `examples/05` + `examples/12` to operator form. | ~800 LOC net change in 2 sub-library `library.py` files (signature + body); -12 LOC per shim deletion; existing tests rewritten | Existing tests rewritten in-place — no parallel coverage | Regenerate `AgentGuard.CodingAgent.html` + `AgentGuard.MCPScenario.html` |
| **5** | Collapse pass B: `StatsKeywords` (scalar comparators only — distribution comparators stay), `SkillKeywords`, `SecurityKeywords` (scalar `Sandbox Exit Code`), `HookKeywords` (scalar comparators only — semantic predicates stay). | ~600 LOC across 4 sub-library `library.py` files | Existing tests rewritten in-place | Regenerate 4 libdoc pages |
| **6** | Collapse pass C: `MCPKeywords` (`MCP Server Should Implement Capabilities` collapses via `*=` contains), `SubAgentsKeywords` (`Task Should Have Status` collapses via `==`), `JudgeKeywords` (`LLM Judge Should Score At Least` → operator on `Get LLM Judge Score`), `BenchmarksKeywords` (the four `Pass At K Should Be Above` per benchmark collapse). | ~400 LOC across 4 sub-library `library.py` files | Existing tests rewritten in-place | Regenerate 4 libdoc pages |
| **7** | Documentation rewrite: regenerate `docs/KEYWORDS.md` (drops to 131 keywords); update `docs/PHASE-{0-1,2,3}-COMPLETE.md` keyword-count claims; rewrite `examples/12_mcp_scenario_replacement.robot` operator form; new `examples/13_assertion_engine_idiom.robot` showing the unified surface. | Docs only — no source change | n/a | Top-level `AgentGuard.html` regenerated |
| **8 (½)** | CI green-up + release: full pytest pass (1185+ tests with operator form); live OpenRouter still green; `0.1.0` → `0.2.0`. | `pyproject.toml` version bump | All tests must pass with the operator-form rewrites | Final libdoc archive |

**Total**: ~2200 LOC net change across 11 sub-libraries + new `_assertions/` module, 1.5 weeks, 32 keyword pairs collapsed end-to-end. Final keyword count: **131**.

---

## 8. Files this proposal would add (when implemented)

```
src/AgentGuard/_assertions/
├── __init__.py                # public re-exports for sub-libraries
├── adapter.py                 # AssertionAdapter — wraps assertionengine.verify_assertion,
│                              #   enforces tier policy, polling allow/deny, sandbox gate
└── operators.py               # re-exports operator enum from `assertionengine`
                               #   no custom operators needed — exp_11 confirmed `validate`
                               #   covers every range / composite / dict-field use case.

pyproject.toml                 # add `robotframework-assertion-engine >= 4.0, < 5.0`
                               #   to [project].dependencies (matches Browser Library 19.14.x pin).
                               # NOTE: PyPI install name is `robotframework-assertion-engine`;
                               #   Python import name is `assertionengine`.

src/AgentGuard/<sublib>/library.py   # 11 sub-library files updated to expose
                                     #   `assertion_operator=` and `assertion_expected=`
                                     #   on each Get<Metric> keyword

tests/unit/_assertions/
├── test_adapter.py            # tier policy, polling deny, sandbox gate
└── test_operators.py          # operator catalog parity with upstream

examples/13_assertion_engine_idiom.robot   # both BEFORE and AFTER forms,
                                           # plus a polling demo and a sandboxed-validate demo

docs/migration/assertion-engine.md         # per-keyword Before→After table for users
```

No keyword definitions are proposed in this document beyond the per-sub-library `library.py` signature change. The actual keyword bodies are unchanged — only the decorator and the trailing `verify_assertion(...)` call are added.

---

## 9. Open questions for review

1. **~~Custom `between(low, high)` operator?~~ RESOLVED 2026-05-05 — no custom operator needed.** `tests/experiments/exp_11_validate_under_robot.robot` (19/19 PASS against `robotframework-assertion-engine 4.0.0`) confirms `validate    ${low} <= value <= ${high}` covers the range case cleanly with RF-native variable substitution. The same pattern handles composite predicates (`value > 0 and value % 2 == 0`), dict-field comparisons (`value['p95'] < value['p99'] * 1.2`), set containment (`set(['a','b']).issubset(value)`), and float-tolerance windows (`abs(value - 1.0) < 1e-3`). One implementation rule: every Get keyword MUST declare a typed return (`-> float`, `-> int`) so AssertionEngine sees a Python value rather than the RF positional string default; this becomes part of the AssertionAdapter contract and is enforced via mypy `--strict`. See `docs/research/assertion-engine.md` §"Update 2026-05-05".
2. **Polling enabled by default for any keyword?** **Recommend**: NO. Polling is explicit opt-in via `polling=...` keyword arg. Most AgentGuard metrics are *over a Session* (already-captured artifact), not over a live system, so polling is rarely meaningful. Live keywords (MCP latency, telemetry) accept it explicitly.
3. **`validate` operator when user passes `--allow-code-execution`?** **Recommend**: YES. ADR-013 already gates code execution behind that flag, so a user with the flag set has already consented to the same trust boundary. The adapter checks `library.allow_code_execution` once at init and adds `validate` to the operator allowlist accordingly.
4. **Robot Framework < 7.x compatibility?** RF 7+ is already required by Phase 0 (`pyproject.toml`). The `enum`-typed `@keyword` parameter that AssertionEngine relies on for IDE completion is rougher pre-7. **Recommend**: keep the RF >= 7.x pin already in place; document in the migration guide that older RF will accept string operators only (functional but no IDE hints).

---

## 10. Cross-references

- **ADR-022** — `docs/adr/ADR-022-assertion-engine-shared-kernel.md` — the formal decision record this proposal implements.
- **DDD update** — `docs/ddd/assertion-engine-shared-kernel.md` — places `_assertions/` as a Shared Kernel module across all 11 bounded contexts.
- **Analyst reduction table** — `docs/proposals/keyword-reduction-table.md` — authoritative per-sub-library, per-keyword Before→After numbers (the source for §2 above).
- **Researcher dossier** — `docs/research/assertion-engine.md` — full operator inventory, upstream API surface, Browser Library / ApiLibraryCore prior-art notes.
- **Companion proposal** — `docs/proposals/PROPOSAL-rf-mcp-test-harness-replacement.md` — the proposal style template used here.
- **Source of truth** — upstream `marketsquare/robotframework-assertion-engine` repo (`assertionengine/__init__.py:verify_assertion`) and Browser Library's `Browser/keywords/getters.py` for the canonical adopter pattern.
