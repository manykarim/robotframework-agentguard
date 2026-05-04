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

## 5. Backwards-compatibility plan

The 81 Should-pair keywords being collapsed are **public API**. We do not break them in a single release.

- **Phase 4-D and Phase 4-E (deprecation window).** Each Should-pair keyword stays in libdoc as a *thin wrapper* that:
  1. Logs a `DeprecationWarning` once per suite, naming the AssertionEngine replacement.
  2. Internally invokes the new operator-driven keyword with the appropriate operator literal (`Should Be Above` → `>`, `Should Be Below` → `<`, `Should Be Between` → custom `between` op, `Should Be Zero` → `==  0`).
  3. Preserves the original signature exactly so that copy-pasted Robot suites and shared keyword resources continue to pass.
- **Phase 4-F.** The wrappers are removed in a new minor version (`X.(Y+1).0`). Release notes flag the removal; the deprecation message during 4-D/4-E will have warned for at least one prior release.

This is the same compatibility pattern Browser Library used when it adopted AssertionEngine on top of its Should-suffixed keywords in 2022 — proven and well-tolerated.

---

## 6. Risk register

| # | Risk | Mitigation |
|---|---|---|
| R1 | Polling cost balloon for Tier-2/3 keywords (e.g. live LLM calls) | `AssertionAdapter` rejects `polling=...` when the keyword's tier ≥ 2 (per ADR-019); raises `PollingNotPermittedError` with remediation text. |
| R2 | `validate` operator code execution | Gated behind ADR-013 sandbox + `--allow-code-execution`; without the flag the adapter strips `validate` from the operator allowlist and raises `CodeExecutionDeniedError`. |
| R3 | Two-idiom user confusion during the deprecation window | Single deprecation message per suite naming the replacement; `docs/migration/assertion-engine.md` table; `examples/13_assertion_engine_idiom.robot` shows both forms. |
| R4 | libdoc HTML diff explodes during the migration | Regenerate libdoc per phase, in separate commits, one sub-library at a time; the diff in any one PR stays ≤ 1 sub-library. |
| R5 | Mann-Whitney / Cliff's δ keywords don't fit the operator pattern (their "expected" is a *distribution*, not a scalar) | Keep them as Should-style. `Tool Hit Rate Distribution Should Stochastically Dominate` and `Cliff's Delta Should Be Negligible` remain Phase-3 idiom — explicitly excluded from the migration. |
| R6 | Predicates without scalar values (`Should Not Call Any Tool`, `Hook Should Block`, `Stop Hook Violations Should Be Zero` in its predicate form) | Keep as-is. AssertionEngine is for *value comparison*; pure predicates don't gain anything from `assertion_operator`. |

---

## 7. Phased delivery (Phase 4-D / 4-E / 4-F)

| Phase | Duration | Scope | Files touched (LOC) | Test surface | libdoc |
|---|---|---|---|---|---|
| **4-D** (MVP) | 1 week | CodingAgent metric pack pilot: 12 Should-pairs collapsed to 12 operator-enabled `Get<Metric>` keywords. New `_assertions/` private module with `AssertionAdapter` + sandbox gate for `validate`. | ~600 LOC under `src/AgentGuard/coding_agent/` + ~400 LOC under `src/AgentGuard/_assertions/` | New `tests/unit/_assertions/`; existing `tests/acceptance/coding_agent/*.robot` extended with operator-form copies. | Regenerate `docs/api/AgentGuard.CodingAgent.html` |
| **4-E** | 1 week | Apply pattern to MCPScenario, Stats (excl. Mann-Whitney/Cliff's δ), Skills, Security, Hooks, ToolCallCorrectness, MCP, SubAgents, Judge. | ~1500 LOC across 9 sub-library `library.py` files; no new modules. | Operator-form copies of existing acceptance tests (one per sub-library). | Regenerate one libdoc page per sub-library, one commit each. |
| **4-F** | ½ week | Remove deprecated Should-pair wrappers; bump minor version; ship migration guide. | ~600 LOC removed; `pyproject.toml` version bump. | Delete deprecated-keyword tests; keep migration-guide example as a smoke test. | Final libdoc regen across all 11 sub-libraries. |

**Total Phase-4-D MVP**: ~1000 LOC net (new), 1 week, 12 keyword pairs collapsed end-to-end.

---

## 8. Files this proposal would add (when implemented)

```
src/AgentGuard/_assertions/
├── __init__.py                # public re-exports for sub-libraries
├── adapter.py                 # AssertionAdapter — wraps assertionengine.verify_assertion,
│                              #   enforces tier policy, polling allow/deny, sandbox gate
└── operators.py               # re-exports operator enum from `assertionengine`
                               #   plus AgentGuard-custom `between(low, high)` (TBD §9.1)

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

1. **Custom `between(low, high)` operator?** Keywords like `Tool Call Count Should Be Between` and `Edits Without Prior Read Percent Should Be Between` need a binary `expected` argument. Upstream AssertionEngine does not ship `between`. **Recommend**: yes, add a single AgentGuard-custom operator in `_assertions/operators.py`. Cleaner than splitting into two `>=` and `<=` lines.
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
