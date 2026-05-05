# ADR-022: AssertionEngine Adoption as Shared Kernel for Get-Style Keywords

- **Status**: Proposed
- **Date**: 2026-05-04 (revised 2026-05-05 — single-phase full replacement; no deprecation)
- **Deciders**: agentguard-architecture-swarm
- **Bounded Context**: cross-cutting (Shared Kernel addition — see `docs/ddd/assertion-engine-shared-kernel.md`)
- **Drivers**: keyword-count reduction, RF-ecosystem idiom alignment, IDE completion via `AssertionOperator` enum, codebase simplicity

## Context

AgentGuard ships **163 keywords across 11 sub-libraries** today (`docs/KEYWORDS.md`), and the count grows every phase. A large fraction are Get/Should *pairs* — `Tool Hit Rate` returns the value, `Tool Hit Rate Should Be Above` asserts on it — each pair adding two keywords for a single semantic concept. Users coming in from Browser Library or SeleniumLibrary, where one keyword does both, see this duplication immediately and ask why we don't follow the standard idiom.

The exact ergonomic gap: AgentGuard today reads `Tool Hit Rate Should Be Above ${result} 0.7`; the RF-ecosystem idiom reads `Tool Hit Rate ${result} >= 0.7`. The latter is shorter, IDE-completable (operators are an enum), composable (one keyword feeds three control-flow shapes), and already familiar — Browser Library, Mobile Library, and Playwright (in TS) all expose Get keywords with optional `assertion_operator`/`assertion_expected`/`message` parameters that flip the keyword from "return value" to "assert AND return value" depending on whether an operator is supplied. SeleniumLibrary exposes the same pattern under its `expected_condition` family.

The de-facto primitive in the RF ecosystem is the `robotframework-assertion-engine` PyPI package (imports as `import assertionengine`), the spinoff from `MarketSquare/robotframework-browser` providing `verify_assertion(value, assertion_operator, assertion_expected, message=None, custom_message=None, formatters=None)`. It ships **13 distinct operators reachable via 27 alias keys** in a functional `Enum(...)` (`==`, `!=`, `>`, `>=`, `<`, `<=`, `*=` contains, `not contains`, `^=` starts, `$=` ends, `matches` — `re.search` not `re.fullmatch`, `validate`, `then`/`evaluate`), plus a `Formatter` ABC (`normalize spaces`, `strip`, `case insensitive`, `apply to expected`). A `with_assertion_polling` decorator that retries the wrapped keyword until success or timeout is a **Browser-Library invention**, NOT part of AssertionEngine itself — AgentGuard would build its own decorator if the polling pattern is wanted (see negative consequences). See `docs/research/assertion-engine.md` for the full operator inventory.

**Crucial framing for this ADR:** AgentGuard 0.1.0 has not been published to PyPI and there are no external consumers depending on the current Should-pair surface. **No backwards-compatibility window is required.** ADR-022 therefore replaces the previous three-phase / shim-wrapper / deprecation-warning plan with a **single Phase 4-D one-shot replacement**: drop every collapsible Should-pair keyword in one commit, ship the new operator-driven surface directly. This trades the deprecation tax (≈ +5 keywords + 4 days swarm time + a release-notes migration column) for a cleaner end state and a smaller maintenance footprint.

What ADR-022 changes: AgentGuard adopts `robotframework-assertion-engine` as a Shared Kernel utility behind every Get-style keyword and collapses **163 → 131 keywords (−32)** in one pass per the analyst's `docs/proposals/keyword-reduction-table.md` (conservative semantics-preserving cut). No shim wrappers ship; the old Should-pair keywords are deleted in the same commit that introduces the operator-driven Get keywords.

## Decision

Adopt `robotframework-assertion-engine >= 4.0, < 5.0` (matching Browser Library 19.14.2's pin) as a Shared Kernel utility for every Get-style keyword in AgentGuard. Apply the migration in **one** Phase 4-D pass: build the `AgentGuard._assertions.AssertionAdapter`, give every collapsible Get keyword the standard `(assertion_operator, assertion_expected, message)` parameters, and **delete the corresponding Should-pair keywords from the same modules in the same commit**. No shim wrappers, no `DeprecationWarning`s, no backwards-compat phase.

## Rationale

- **Reduction is real and measurable.** Per the analyst's `docs/proposals/keyword-reduction-table.md`, the migration drops **163 → 131 keywords (−32)**. CodingAgent's #42796 metric pack is the biggest single win: 24 → 12 keywords. With the deprecation-window tax removed, this is the *immediate* steady state — no temporary +5 inflation.
- **Operator inventory is exhaustive — `validate` closes the `between` gap.** Per `docs/research/assertion-engine.md` §"Update 2026-05-05" and `tests/experiments/exp_11_validate_under_robot.robot` (19/19 PASS against `robotframework-assertion-engine 4.0.0`), the `validate` operator covers every range / composite / dict-field / set-containment use case AgentGuard would have wanted a custom `between(low, high)` for. Form: `Tool Call Count    ${result}    validate    2 <= value <= 10`. **No custom operator extension needed.** One adopter rule the experiment surfaced: every `Get`-style keyword's return type MUST be declared (`-> float` / `-> int`) so AssertionEngine sees a real Python value rather than the RF positional string default; documented as part of the AssertionAdapter contract.
- **The "edge cases that resist collapse" are kept intentionally, not for technical reasons.** `tests/experiments/exp_12_aggressive_collapse.robot` (16/16 PASS) proves that the analyst's "edge cases" — Mann-Whitney U, `Should Not Call Any Tool`, `Hook Should Block`, `Required Tool Should Have Been Called With Params`, `Skill Should Pass Security Scan`, ordered tool-sequence matching — *technically* collapse via `validate` over the keyword's typed return. They are kept as named keywords in the steady state because the Should-style form **reads better at the call site** (e.g. `Skill Should Pass Security Scan ${path}` vs `Scan Skill ${path} validate value.decision != 'deny' and not [f for f in value.findings if f.severity.name == 'CRITICAL']`). Per the user-stated goal "small amount of focused keywords with simple syntax", readability wins where it conflicts with raw count.
- **Cleaner code base, smaller maintenance surface.** No shim wrappers means: no extra test coverage for shims, no parallel-keyword libdoc rendering, no migration-warning messages, no version-bump deprecation cycle. The codebase ships the end state directly.
- **Existing keyword count is documented.** The 163-keyword total is published in `docs/KEYWORDS.md`; the ADR's reduction claim references that table directly.
- **IDE completion benefit.** `AssertionOperator` is a Python `Enum`, so RIDE / RobotCode / RED show the full operator list at the call site — users do not need to remember which `Should Be Above` / `Should Be At Least` / `Should Be Greater Than` variant we picked.

## Consequences

### Positive
- **Keyword-count drop of 163 → 131 in one pass** (per analyst's `docs/proposals/keyword-reduction-table.md`).
- **RF-ecosystem idiom parity** — same call shape as Browser Library, Mobile Library, SeleniumLibrary expectations.
- **Single learning surface** for assertions across the whole library; no more "is it `Should Be Above` or `Should Be Greater Than` here?" lookups.
- **Custom `validate` operator** gives users a Python-expression escape hatch for assertions we did not anticipate (e.g. `validate value['p95'] < value['p99'] * 1.2`); proven on the resistant-case set in exp_12.
- **No deprecation tax** — no shim wrappers, no `DeprecationWarning` plumbing, no warning-message regression tests, no migration-window release notes column. Ship the end state directly.
- **Type annotation surface** gains `AssertionOperator | None`; mypy `--strict` stays clean because the enum is fully typed.

### Negative
- **One-shot replacement is breaking — but there is nothing to break yet.** AgentGuard 0.1.0 has not been published to PyPI; no external consumers depend on the Should-pair surface. The risk window is between the merge of this PR and the eventual 0.1 PyPI release; users who have been tracking `main` directly need to update their `.robot` suites once. Documented in the release notes.
- **Polling cost on LLM-touching keywords.** If AgentGuard later builds a Browser-style polling decorator (not part of AssertionEngine itself), it must be opt-in per keyword and disabled by default for any keyword whose router tier is `tier=2` or `tier=3` (per ADR-019) — every retry is a fresh LLM sample, not a re-observation, so cost compounds. Enforced in the AssertionAdapter via a tier check raising `PollingDisallowedError`. Documented in `docs/ddd/assertion-engine-shared-kernel.md`.
- **`validate` operator security.** AssertionEngine's `validate` op evaluates a user-supplied Python expression with `BuiltIn().evaluate()` (Python `eval`). That violates ADR-013 sandbox policy in its default form. Default in the AssertionAdapter: the `validate` operator is **disabled** and raises `ValidateOperatorDisallowed`; users opt in per-suite via `Configure Assertion Engine validate_enabled=True` AND the configured `SandboxBackend` is non-`process`. Documented as a hard gate.

### Neutral
- **Type-hint surface gains** `AssertionOperator | None`; mypy `--strict` still clean.
- **libdoc HTML regenerates** with the new signature in one pass; no manual reformatting needed.
- **Documentation rewrite is bounded** — `docs/KEYWORDS.md` regenerates from the introspection script; per-sub-library examples need to be updated once.

## Alternatives Considered

1. **Status quo (do nothing)** — keep 163 keywords forever. *Rejected* because keyword count is a real adoption barrier; new users compare to Browser Library and ask why we don't follow the idiom, and every new sub-library currently doubles its own surface by emitting Get + Should pairs.
2. **Build a tiny custom assertion mini-engine** — 80 lines of Python wrapping our own operator strings. *Rejected* because AssertionEngine is the de-facto RF standard already vendored by Browser Library; building our own would be NIH, would duplicate the operator parser, and would diverge in subtle ways (formatter ABC) from what RF users already know.
3. **Adopt SeleniumLibrary's `expected_condition` pattern** — predicates passed as callables rather than operator-string enums. *Rejected* because callable predicates are not RF-idiomatic for non-Selenium libraries; the Browser Library / AssertionEngine approach using string operators is what the wider ecosystem has converged on, and it preserves human-readable suite source.
4. **Replace Should-pair keywords with macros / resource files** — let users compose `Should Be True ${value} >= 4.0` from BuiltIn primitives. *Rejected* because this pushes assertion logic out of the library entirely, loses formatter integration, loses error-message customisation, and forces every test author to re-derive the same assertion idiom by hand.
5. **Three-phase migration with deprecation shims (the original ADR-022 plan, superseded 2026-05-05).** *Rejected* because AgentGuard is pre-1.0 and not on PyPI: the deprecation cycle would have added ≈ +5 temporary keywords, ≈ 4 days of swarm time, a release-notes migration column, and shim-coverage tests — all to soften a transition for users who do not yet exist. The single-phase full replacement is strictly cleaner.
6. **Aggressive collapse — also fold the resistant cases into `validate` (target ≈ 115 keywords).** *Rejected* because `tests/experiments/exp_12_aggressive_collapse.robot` confirms the technical feasibility (16/16 PASS) but call-site readability degrades sharply: `Skill Should Pass Security Scan ${path}` reads cleaner than `Scan Skill ${path} validate value.decision != 'deny' and not [f for f in value.findings if f.severity.name == 'CRITICAL']`. Per the user-stated goal of "small focused keywords with simple syntax", readability beats raw count where they conflict.

## Related ADRs

- **ADR-003 (Library Composition)** — `DynamicCore` composition is unaffected by the new keyword shape; the AssertionAdapter is a Shared Kernel module, not a sub-library.
- **ADR-005 (Statistical Assertion API)** — clarify that statistical assertions (`pass_at_k`, `mann_whitney_u`, `cliffs_delta`) stay in `StatsKeywords` with their domain-specific shapes; AssertionEngine handles only scalar-value comparisons. The two layers compose: `Pass Rate ${runs} >= 0.8` uses the operator, but `Mann Whitney U Should Show Improvement ${current} ${baseline}` does not.
- **ADR-013 (Sandbox Policy)** — the `validate` operator security gate routes `eval()` through the same sandbox.
- **ADR-019 (3-Tier Model Routing)** — the polling gate keys off the per-keyword `tier=` annotation; Tier-2 and Tier-3 keywords reject any future polling decorator.
- **ADR-021 (Unified Scenario Test Harness)** — `MCPScenarioKeywords`' hit-rate / count keywords (`Tool Hit Rate`, `Tool Call Count`, `Tool Call Success Rate`) get the operator treatment in Phase 4-D and lose their `Should Be Above` / `Should Be Between` siblings outright.

## Phase 4-D — One-Shot Replacement (1.5 weeks)

- **Day 1–2: Foundation.**
  - Add `robotframework-assertion-engine >= 4.0, < 5.0` to `[project].dependencies`.
  - Create `src/AgentGuard/_assertions/{__init__,adapter,operators,polling}.py` (no `between.py` — exp_11 closed that gap).
  - `AssertionAdapter` enforces: `validate` disabled by default; tier-≥2 polling rejected; typed-return contract via runtime check on the wrapped keyword's signature.
  - `tests/unit/_assertions/{test_adapter,test_validate_gate,test_polling_gate}.py`.

- **Day 3–6: One-shot collapse across all 11 sub-libraries.**
  - For every collapsible Get/Should pair (32 pairs per analyst): add `(assertion_operator, assertion_expected, message)` to the Get keyword, **delete** the Should-pair keyword from the same `library.py`. No wrapper.
  - Update every per-sub-library test that currently calls a Should-pair keyword to use the operator form. The unit test suite is the regression net.
  - Update `tests/acceptance/*.robot` and `examples/*.robot` to use the operator form. The 38-test acceptance suite is the migration validation.
  - Regenerate `docs/api/AgentGuard*.html` via libdoc.

- **Day 7: Documentation.**
  - Regenerate `docs/KEYWORDS.md` (drops to 131 keywords).
  - Update `docs/PHASE-0-1-COMPLETE.md`, `docs/PHASE-2-COMPLETE.md`, `docs/PHASE-3-COMPLETE.md` keyword-count claims.
  - Rewrite `examples/12_mcp_scenario_replacement.robot` and any other example referencing collapsed keywords (the rf-mcp drop-in proof point now uses the operator form).
  - New `examples/13_assertion_engine_idiom.robot` showing the operator surface end-to-end.

- **Day 8 (½): CI + release.**
  - All 1185+ tests pass with the new surface (regression net).
  - Live OpenRouter job still green.
  - Bump `0.1.0` → `0.2.0` (breaking change between unreleased dev versions; signals the surface stabilised).

**Acceptance criteria:** keyword count is 131 ± 1 (allowing for one-off keyword renames); no `Should Be Above|Below|Between|Equal To|Zero` keyword remains in the public surface; mypy `--strict` clean; ruff clean; CI green; libdoc HTML regenerated for all 11 sub-libraries; examples 01–13 all run.
