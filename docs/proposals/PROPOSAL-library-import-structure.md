# Proposal: Library Import Structure — Short, Idiomatic, Sub-Library Friendly

**Author**: agentguard-architecture-swarm
**Date**: 2026-05-05
**Status**: Proposed (gates on ADR-023 — to be authored separately)
**Empirical basis**: `tests/experiments/exp_13{,b,c}_*` (5/5 PASS)
**Related**: ADR-003 (Library Composition), ADR-022 (AssertionEngine adoption), `docs/KEYWORDS.md`, `docs/PHASE-0-1-COMPLETE.md`

---

## 1. Problem

The Phase 1–3 module layout puts every keyword class under a deep `<context>/library.py` path:

```
src/AgentGuard/
├── library.py                                    # AgentGuard
├── mcp/library.py                                # MCPKeywords
├── skills/library.py                             # SkillsKeywords
├── tool_calls/library.py                         # ToolCallKeywords
├── stats/library.py                              # StatsKeywords
├── judge/library.py                              # JudgeKeywords
├── security/library.py                           # SecurityKeywords
├── hooks/library.py                              # HooksKeywords
├── subagents/library.py                          # SubAgentsKeywords
├── coding_agent/library.py                       # CodingAgentKeywords
├── coding_agent/benchmarks/library.py            # CodingBenchmarkKeywords
└── mcp_scenario/library.py                       # MCPScenarioKeywords
```

Top-level `Library AgentGuard` works (the `library.py` composes all 11 sub-libraries via DynamicCore — ADR-003). But importing one slice in isolation requires the full Python path:

```robot
*** Settings ***
# OK — kitchen-sink import.
Library    AgentGuard

# NOT OK — deep, internal-shaped, non-PascalCase.
Library    AgentGuard.coding_agent.benchmarks.library.CodingBenchmarkKeywords
```

The user-stated bar: importing a single sub-library should look like importing any other top-line RF library:

```robot
Library    AgentGuard.MCP
Library    AgentGuard.Skill
Library    AgentGuard.Tool
Library    AgentGuard.Benchmark
```

## 2. RF library-import resolution — facts that drive the design

`Library X.Y` in Robot Framework resolves as follows (verified empirically by `tests/experiments/exp_13b/test_facade.robot` — 1/1 PASS):

1. RF imports the Python module `X.Y` (so `X/Y.py` or `X/Y/__init__.py` must exist).
2. RF looks up `getattr(module, 'Y')` — the **last segment of the module path matched as a class name**.
3. If that class exists, RF instantiates it and calls all `@keyword`-decorated methods.
4. If it doesn't, RF falls back to module-level `@keyword` functions and warns: `Imported library 'X.Y' contains no keywords.` (Observed in exp_13.)

**Critical implication**: a façade module `src/AgentGuard/MCP.py` MUST contain a name `MCP` at module scope. The simplest pattern is to alias the existing internal class:

```python
# src/AgentGuard/MCP.py — façade
from AgentGuard.mcp.library import MCPKeywords as MCP
__all__ = ["MCP"]
```

`tests/experiments/exp_13c/test_alias.robot` (1/1 PASS) confirms `from X import OriginalClass as ModuleMatchingName` survives RF's `getattr(module, name)` lookup regardless of `OriginalClass.__name__`. So we can keep `MCPKeywords` as the internal class name (no source changes elsewhere) and only add a thin façade.

## 3. Proposed façade layout

12 short, PascalCase façade modules at `src/AgentGuard/<Name>.py`. Each is **5–10 lines** — a single `from … import … as <Name>` and `__all__`.

### Naming convention

- **PascalCase** matches the wider RF ecosystem (`Browser`, `SeleniumLibrary`, `RequestsLibrary`, `AppiumLibrary`).
- **Singular** matches what the user listed (`Skill`, `Tool`, not `Skills`, `Tools`). Browser Library uses singular (`Page`, not `Pages`); SeleniumLibrary uses singular (`Element`).
- **Domain-meaningful**, not implementation-shaped: `Skill` not `Skills`, `Coding` not `CodingAgent`, `Scenario` not `MCPScenario`.

### Mapping table

| User-facing import | Façade file (NEW) | Internal class (EXISTING) | Currently exposed via |
|---|---|---|---|
| `Library AgentGuard` | `src/AgentGuard/__init__.py` (existing) → re-exports `library.AgentGuard` | `AgentGuard` (composes everything) | Works today |
| `Library AgentGuard.MCP` | `src/AgentGuard/MCP.py` | `MCPKeywords` aliased as `MCP` | `Library AgentGuard.mcp.library` (Python path) |
| `Library AgentGuard.Skill` | `src/AgentGuard/Skill.py` | `SkillsKeywords` aliased as `Skill` | `Library AgentGuard.skills.library` |
| `Library AgentGuard.Tool` | `src/AgentGuard/Tool.py` | `ToolCallKeywords` aliased as `Tool` | `Library AgentGuard.tool_calls.library` |
| `Library AgentGuard.Stats` | `src/AgentGuard/Stats.py` | `StatsKeywords` aliased as `Stats` | `Library AgentGuard.stats.library` |
| `Library AgentGuard.Judge` | `src/AgentGuard/Judge.py` | `JudgeKeywords` aliased as `Judge` | `Library AgentGuard.judge.library` |
| `Library AgentGuard.Security` | `src/AgentGuard/Security.py` | `SecurityKeywords` aliased as `Security` | `Library AgentGuard.security.library` |
| `Library AgentGuard.Hook` | `src/AgentGuard/Hook.py` | `HooksKeywords` aliased as `Hook` | `Library AgentGuard.hooks.library` |
| `Library AgentGuard.SubAgent` | `src/AgentGuard/SubAgent.py` | `SubAgentsKeywords` aliased as `SubAgent` | `Library AgentGuard.subagents.library` |
| `Library AgentGuard.Coding` | `src/AgentGuard/Coding.py` | `CodingAgentKeywords` aliased as `Coding` | `Library AgentGuard.coding_agent.library` |
| `Library AgentGuard.Benchmark` | `src/AgentGuard/Benchmark.py` | `CodingBenchmarkKeywords` aliased as `Benchmark` | `Library AgentGuard.coding_agent.benchmarks.library` |
| `Library AgentGuard.Scenario` | `src/AgentGuard/Scenario.py` | `MCPScenarioKeywords` aliased as `Scenario` | `Library AgentGuard.mcp_scenario.library` |

11 sub-library façade modules + 1 top-level (existing). All deep paths remain reachable for advanced users — the façade is *additive*, not a replacement.

## 4. Side-by-side BEFORE / AFTER

### MCP server smoke test

```robot
# BEFORE (today):
*** Settings ***
Library    AgentGuard.mcp.library    WITH NAME    MCP

*** Test Cases ***
Server Implements Tools
    ${handle}=    MCP.Connect To MCP Server    http://localhost:8080/mcp
    MCP.MCP Server Should Implement Capabilities    ${handle}    tools
```

```robot
# AFTER (proposed):
*** Settings ***
Library    AgentGuard.MCP

*** Test Cases ***
Server Implements Tools
    ${handle}=    Connect To MCP Server    http://localhost:8080/mcp
    MCP Server Should Implement Capabilities    ${handle}    tools
```

(The `WITH NAME` ceremony also disappears — the import name is already short.)

### Multiple sub-libraries side-by-side

```robot
*** Settings ***
Library    AgentGuard.Skill        # Load Skill, Run Skill Eval, Validate Skill Frontmatter, ...
Library    AgentGuard.Security     # Skill Should Pass Security Scan, Redact Trajectory, ...
Library    AgentGuard.Stats        # Mann Whitney U Should Show Improvement, ...

*** Test Cases ***
Skill Pipeline With Security Scan And Statistical Baseline
    ${skill}=     Load Skill                      skills/my-skill
    Skill Should Pass Security Scan               ${skill}
    ${current}=   Run N Times    runs=30          Run Skill Eval    ${skill}
    ${baseline}=  Load Baseline                   baselines/2026-q1.json
    Mann Whitney U Should Show Improvement        ${current}    ${baseline}    alpha=0.05
```

Three short imports, no Python-path noise. Keyword-name conflicts across imports are not a concern today (verified by `docs/KEYWORDS.md` — every keyword name is unique across the 11 sub-libraries); if a future sub-library introduces a collision, RF's `WITH NAME` is the standard escape hatch.

### Kitchen-sink import unchanged

```robot
*** Settings ***
Library    AgentGuard    provider=litellm    model=openrouter/anthropic/claude-sonnet-4-5

*** Test Cases ***
Everything Available Under One Library Import
    ${info}=    Get AgentGuard Info
    Length Should Be    ${info}[components]    11
    # All ~131 keywords (post-ADR-022) reachable here without any other Library line.
```

## 5. What lives at the top level vs sub-library only?

The user wrote: *"Most important and general KWs should be available in top module, while others would require import of the sub module."*

Two interpretations are possible:

### Option A (recommended) — top is kitchen-sink, sub-libraries are *namespace isolation*

`Library AgentGuard` continues to expose every keyword (current behavior). Sub-library imports exist purely for users who want a smaller namespace, faster startup (only the chosen sub-library initialises), or their own naming discipline.

**Pros**: zero migration cost; matches Browser Library / SeleniumLibrary / RequestsLibrary convention (one library, all keywords); intuitive default.

**Cons**: top-level imports the full dependency tree (a2a-sdk, docker SDK, jsonlines, etc.) even when the user only wants `MCP`. Mitigated by the existing lazy-import composition pattern in `src/AgentGuard/library.py` — sub-libraries are imported on first call, not at top-level import time.

### Option B — top is curated, sub-libraries are mandatory for everything else

Top-level keeps only the "core 30" (introspection, MCP basics, Stats, Tool-call matching). Skills, Security, Hooks, SubAgents, CodingAgent, Benchmarks, MCPScenario require explicit sub-library import.

**Pros**: smallest top-level surface; clearest "if you want X, import X" UX.

**Cons**: every existing test suite breaks; the PR adds a second migration the day after Phase 4-D's keyword-collapse migration; confuses users who saw `Library AgentGuard` give them everything yesterday.

### Recommendation: Option A

Top-level stays as kitchen-sink (zero break). Façades are *additive* — they exist for users who want them. This matches every other major RF library and keeps the migration scope to "11 small new files".

## 6. What lives in each façade module — code shape

Every façade is the same five lines:

```python
"""src/AgentGuard/MCP.py — convenience façade.

Equivalent of `from AgentGuard.mcp.library import MCPKeywords as MCP`.
Lets users write `Library AgentGuard.MCP` without exposing the
internal `mcp.library` Python path.
"""

from AgentGuard.mcp.library import MCPKeywords as MCP

__all__ = ["MCP"]
```

That's it. No re-implemented constructor, no new keyword class, no DynamicCore composition (those happen in `src/AgentGuard/library.py` for the kitchen-sink import).

The internal name (`MCPKeywords`) stays — this is the alias only. mypy `--strict` is unaffected because the alias is a name, not a redefinition.

## 7. Risk register

| # | Risk | Mitigation |
|---|---|---|
| R1 | A user imports both `Library AgentGuard` AND `Library AgentGuard.MCP` and now has *two* `MCPKeywords` instances at runtime (the kitchen-sink one and the sub-library one). | Document in the README: importing a sub-library on top of the kitchen-sink is harmless but redundant. Each instance carries its own suite-scope state (e.g. tracked sessions); use one or the other consistently. |
| R2 | Naming collisions between two sub-libraries when both are imported (e.g. a hypothetical `Skill.Save Baseline` and `Coding.Save Baseline`). | Today there are no collisions across the 11 sub-libraries (audited from `docs/KEYWORDS.md`). RF's `WITH NAME <prefix>` remains the standard escape hatch if collisions appear. |
| R3 | Singular vs plural drift — the existing internal classes use plural (`SkillsKeywords`, `HooksKeywords`); façades use singular (`Skill`, `Hook`). | Aliased at import time (`as Skill`); the singular form is exclusively the façade-module / library-import name, the plural form remains the internal class name. Documented in the docstring of each façade. |
| R4 | Class-name-equals-module-name discipline must hold for every façade. If we ship `src/AgentGuard/MCP.py` containing `from … import MCPKeywords` (no `as MCP` rename), `Library AgentGuard.MCP` warns "contains no keywords" (observed in exp_13). | Enforce via a unit test that walks every façade module and asserts `getattr(module, last_segment)` returns a class with `@keyword`-decorated methods. |
| R5 | Deep paths still work, leading to two equally-valid imports for the same keywords — choice paralysis. | Document the façades as the *recommended* path; mark deep paths as "internal — subject to change without notice" in the contributor docs. |
| R6 | The PascalCase singular names (`Hook`) clash with future RF built-in or BuiltIn library names. | Today's RF built-ins (`BuiltIn`, `Collections`, `OperatingSystem`, `Process`, `String`, `XML`, `DateTime`, `DialogLibrary`, `Screenshot`, `Telnet`, `Remote`) do not include any of our proposed names. The `AgentGuard.<Name>` prefix also makes collisions impossible — the user-typed import is always namespaced. |

## 8. Implementation footprint

- **11 new façade modules** under `src/AgentGuard/`, each ~5 lines. Total: ~60 LOC.
- **1 contract test** at `tests/unit/test_library_facades.py` walking each façade and asserting the class-name-matches-module-name discipline. ~50 LOC.
- **README + KEYWORDS.md update** documenting the façade as the recommended import path. Documentation-only churn.
- **Examples 01–13 update** — optional refresh of one or two examples to show the façade form (e.g. `examples/12_mcp_scenario_replacement.robot` could switch from `Library AgentGuard` to `Library AgentGuard.Scenario` to demonstrate the pattern).

**No source-class renames.** `MCPKeywords` stays as the internal class name; the façade is purely additive. Phase 4-D (AssertionEngine adoption per ADR-022) and this proposal are orthogonal — neither blocks the other.

**Estimated effort**: ½ day — could ship as part of Phase 4-D or as its own micro-PR.

## 9. Open questions

1. **Should `library.py` files be renamed `_library.py` to mark them as internal?** *Recommendation*: no — that's a rename across every sub-library and existing tests reach into them by name. Mark them internal in docs only; the façade IS the recommended path.
2. **Should `AgentGuard.Coding` be `AgentGuard.CodingAgent` for clarity?** Browser Library uses single-word names (`Browser`, not `WebBrowser`); `AgentGuard.Coding` matches that brevity. *Recommendation*: ship as `Coding`; users typing it have already imported `AgentGuard.<X>` so the context is clear.
3. **Should `AgentGuard.Scenario` be `AgentGuard.MCPScenario` to disambiguate from future skill-scenario / coding-agent-scenario contexts?** Per ADR-021, the TestHarness context generalises to non-MCP scenarios in Phase 4-B. *Recommendation*: ship as `Scenario` (the unified name aligns with the unified-harness vision); extend semantics rather than splitting the import.
4. **Should the top-level `Library AgentGuard` keyword count be trimmed (Option B in §5)?** *Recommendation*: NO. Kitchen-sink stays.

## 10. Cross-references

- **ADR-003 (Library Composition)** — DynamicCore composition in `src/AgentGuard/library.py` is unaffected by the façade additions.
- **ADR-022 (AssertionEngine Adoption)** — Phase 4-D one-shot replacement and this proposal are orthogonal; both are documentation-only changes for users (the façades let them write `Library AgentGuard.MCP`; ADR-022 lets them write `Tool Hit Rate ${result} >= 0.7`).
- **`docs/KEYWORDS.md`** — keyword-name uniqueness across the 11 sub-libraries already verified; no collision risk for sub-library import.
- **`tests/experiments/exp_13_facade_proof.{py,robot}`** — proves implicit class lookup requires class-name = module-last-segment.
- **`tests/experiments/exp_13b/{MCP.py,test_facade.robot}`** — proves the canonical pattern works without warnings.
- **`tests/experiments/exp_13c/{MCP.py,_real.py,test_alias.robot}`** — proves `from X import OriginalClass as Alias` survives RF's `getattr(module, name)` lookup.
- **`docs/research/experiments/exp_13_library_facade.log`** — captured robot output (5/5 PASS).

## 11. Files this proposal would add (when implemented)

```
src/AgentGuard/MCP.py             # 5 lines: from AgentGuard.mcp.library import MCPKeywords as MCP
src/AgentGuard/Skill.py           # 5 lines: from AgentGuard.skills.library import SkillsKeywords as Skill
src/AgentGuard/Tool.py            # 5 lines: from AgentGuard.tool_calls.library import ToolCallKeywords as Tool
src/AgentGuard/Stats.py           # 5 lines: from AgentGuard.stats.library import StatsKeywords as Stats
src/AgentGuard/Judge.py           # 5 lines: from AgentGuard.judge.library import JudgeKeywords as Judge
src/AgentGuard/Security.py        # 5 lines: from AgentGuard.security.library import SecurityKeywords as Security
src/AgentGuard/Hook.py            # 5 lines: from AgentGuard.hooks.library import HooksKeywords as Hook
src/AgentGuard/SubAgent.py        # 5 lines: from AgentGuard.subagents.library import SubAgentsKeywords as SubAgent
src/AgentGuard/Coding.py          # 5 lines: from AgentGuard.coding_agent.library import CodingAgentKeywords as Coding
src/AgentGuard/Benchmark.py       # 5 lines: from AgentGuard.coding_agent.benchmarks.library import CodingBenchmarkKeywords as Benchmark
src/AgentGuard/Scenario.py        # 5 lines: from AgentGuard.mcp_scenario.library import MCPScenarioKeywords as Scenario

tests/unit/test_library_facades.py   # walk-and-assert contract test for all 11 façades

docs/KEYWORDS.md                  # documentation update — recommend façade form
README.md                         # add a "Sub-library imports" section showing the façades
```

Total: 11 new source modules (≈ 60 LOC), 1 new test module (≈ 50 LOC), 2 doc updates.
