# ADR-022: AssertionEngine Adoption as Shared Kernel for Get-Style Keywords

- **Status**: Proposed
- **Date**: 2026-05-04
- **Deciders**: agentguard-architecture-swarm
- **Bounded Context**: cross-cutting (Shared Kernel addition — see DDD update by `ddd-domain-expert` sibling agent)
- **Drivers**: keyword-count reduction, RF-ecosystem idiom alignment, IDE completion via `AssertionOperator` enum

## Context

AgentGuard ships **163 keywords across 11 sub-libraries** today (`docs/KEYWORDS.md`), and the count grows every phase. A large fraction are Get/Should *pairs* — `Tool Hit Rate` returns the value, `Tool Hit Rate Should Be Above` asserts on it — each pair adding two keywords for a single semantic concept. Users coming in from Browser Library or SeleniumLibrary, where one keyword does both, see this duplication immediately and ask why we don't follow the standard idiom.

The exact ergonomic gap: AgentGuard today reads `Tool Hit Rate Should Be Above ${result} 0.7`; the RF-ecosystem idiom reads `Tool Hit Rate ${result} >= 0.7`. The latter is shorter, IDE-completable (operators are an enum), composable (one keyword feeds three control-flow shapes), and already familiar — Browser Library, Mobile Library, and Playwright (in TS) all expose Get keywords with optional `assertion_operator`/`assertion_expected`/`message` parameters that flip the keyword from "return value" to "assert AND return value" depending on whether an operator is supplied. SeleniumLibrary exposes the same pattern under its `expected_condition` family.

The de-facto primitive in the RF ecosystem is the `robotframework-assertion-engine` PyPI package (imports as `import assertionengine`), the spinoff from `MarketSquare/robotframework-browser` providing `verify_assertion(value, assertion_operator, assertion_expected, message=None, custom_message=None, formatters=None)` (the 4th positional is `message`; the 6th is `formatters: list`, plural — corrected from the early briefing per `docs/research/assertion-engine.md`). It ships **13 distinct operators reachable via 27 alias keys** in a functional `Enum(...)` (`==`, `!=`, `>`, `>=`, `<`, `<=`, `*=` contains, `not contains`, `^=` starts, `$=` ends, `matches` — `re.search` not `re.fullmatch`, `validate`, `then`/`evaluate`), plus a `Formatter` ABC (`normalize spaces`, `strip`, `case insensitive`, `apply to expected`). A `with_assertion_polling` decorator that retries the wrapped keyword until success or timeout is a **Browser-Library invention**, NOT part of AssertionEngine itself — AgentGuard would build its own decorator if the polling pattern is wanted (see negative consequences). See `docs/research/assertion-engine.md` for the full operator inventory.

What ADR-022 changes: AgentGuard adopts `robotframework-assertion-engine` as a Shared Kernel utility behind every Get-style keyword, collapses **163 → 131 keywords (−32 conservative; −37 aggressive)** per the analyst's `docs/proposals/keyword-reduction-table.md`, and keeps Should-pair keywords as thin wrappers emitting `DeprecationWarning` for one minor release before removal.

## Decision

Adopt `robotframework-assertion-engine >= 4.0, < 5.0` (matching Browser Library 19.14.2's pin) as a Shared Kernel utility for every Get-style keyword in AgentGuard, migrate Get/Should pairs to single `AssertionOperator`-driven keywords across three phases (4-D pilot, 4-E rollout, 4-F deprecation), and keep the old Should-pair keywords as thin wrappers that emit `DeprecationWarning` for one release before removal.

## Rationale

- **Reduction is real and measurable.** Per the analyst's `docs/proposals/keyword-reduction-table.md`, the migration drops **163 → 131 keywords (−32 conservative; −37 aggressive)**. CodingAgent's #42796 metric pack is the biggest single win: 24 → 12 keywords. The system-architect's higher number (`~102`) double-counts predicate keywords and composite-pipeline assertions that the analyst (correctly) flagged as resisting collapse — see "Edge cases that resist collapse" in `docs/proposals/keyword-reduction-table.md`.
- **Operator inventory is exhaustive.** Per `docs/research/assertion-engine.md`, AssertionEngine's 13 distinct operators cover every comparator AgentGuard currently expresses across `StatsKeywords`, `MCPScenarioKeywords`, `CodingAgentKeywords`, `SkillKeywords`, `SecurityKeywords`, and `HookKeywords` — with one gap: `between(low, high)` is not native; `validate "${low} <= x <= ${high}"` is the documented workaround pending a decision on a small custom-operator extension (Phase 4-D open question).
- **Existing keyword count is documented.** The 163-keyword total is published in `docs/KEYWORDS.md`; the ADR's reduction claim references that table directly.
- **IDE completion benefit.** `AssertionOperator` is a Python `enum.Enum`, so RIDE / RobotCode / RED show the full operator list at the call site — users do not need to remember which `Should Be Above` / `Should Be At Least` / `Should Be Greater Than` variant we picked.
- **Polling pattern reuse.** `with_assertion_polling` is the same primitive Browser Library uses to retry locator assertions until the DOM settles. AgentGuard can apply it to non-deterministic LLM keywords (e.g. retry `Tool Hit Rate` until it stabilises across N samples) — *as opt-in only*; see negative consequences.

## Consequences

### Positive
- **Keyword-count drop of 163 → 131** (per analyst's `docs/proposals/keyword-reduction-table.md`; aggressive-collapse path goes to 126).
- **RF-ecosystem idiom parity** — same call shape as Browser Library, Mobile Library, SeleniumLibrary expectations.
- **Single learning surface** for assertions across the whole library; no more "is it `Should Be Above` or `Should Be Greater Than` here?" lookups.
- **Custom `validate` operator** gives users a Python-expression escape hatch for assertions we did not anticipate (e.g. `validate value['p95'] < value['p99'] * 1.2`).
- **Type annotation surface** gains `AssertionOperator | None`; mypy `--strict` stays clean because the enum is fully typed.

### Negative
- **Polling cost on LLM-touching keywords.** `with_assertion_polling` retries the wrapped keyword until the assertion passes or a timeout expires. For any keyword that triggers a Tier-2 (Haiku) or Tier-3 (Sonnet/Opus) call per ADR-019, polling **doubles or triples cost** on a single failed-then-recovered assertion. Polling MUST be opt-in per keyword and disabled by default for any keyword whose router tier is `tier=2` or `tier=3`. Documented in the keyword-author guide; enforced via a decorator-level assert on `tier` in the polling shim.
- **`validate` operator security.** AssertionEngine's `validate` op evaluates a user-supplied Python expression with `eval()`. That violates ADR-013 sandbox policy in its default form. Default: the `validate` operator is **disabled** in the `AgentGuard.AssertionAdapter` shim; users opt in per-suite via `Configure Assertion Engine validate_enabled=True`, which routes the eval through the same RestrictedPython sandbox ADR-013 mandates for agent-generated code. Documented as a hard gate.
- **Three-phase migration cost.** Each of Phase 4-D, 4-E, 4-F requires its own CI matrix run plus a libdoc HTML regeneration cycle, plus a deprecation-warning regression test pass. Roughly +4 days of swarm time spread across the three phases.
- **One-release backwards-compat tax.** Should-pair keywords stay as thin wrappers emitting `DeprecationWarning` for a full minor-version cycle, which means the 163-keyword count temporarily *grows* by ~5 (the new operator-driven keyword sits next to its old pair) before dropping at removal time.

### Neutral
- **Type-hint surface gains** `AssertionOperator | None`; mypy `--strict` still clean.
- **libdoc HTML regenerates** with the new signature; no manual reformatting needed.
- **Resource files unaffected** — existing `.resource` files that call old keyword names continue to work for the deprecation cycle.

## Alternatives Considered

1. **Status quo (do nothing)** — keep 163 keywords forever. *Rejected* because keyword count is a real adoption barrier; new users compare to Browser Library and ask why we don't follow the idiom, and every new sub-library currently doubles its own surface by emitting Get + Should pairs.
2. **Build a tiny custom assertion mini-engine** — 80 lines of Python wrapping our own operator strings. *Rejected* because AssertionEngine is the de-facto RF standard already vendored by Browser Library; building our own would be NIH, would duplicate the operator parser, and would diverge in subtle ways (polling semantics, formatter ABC) from what RF users already know.
3. **Adopt SeleniumLibrary's `expected_condition` pattern** — predicates passed as callables rather than operator-string enums. *Rejected* because callable predicates are not RF-idiomatic for non-Selenium libraries; the Browser Library / AssertionEngine approach using string operators is what the wider ecosystem has converged on, and it preserves human-readable suite source.
4. **Replace Should-pair keywords with macros / resource files** — let users compose `Should Be True ${value} >= 4.0` from BuiltIn primitives. *Rejected* because this pushes assertion logic out of the library entirely, loses formatter integration, loses polling integration, loses error-message customisation, and forces every test author to re-derive the same assertion idiom by hand.

## Related ADRs

- **ADR-003 (Library Composition)** — `DynamicCore` composition is unaffected by the new keyword shape; the assertion adapter is a Shared Kernel module, not a sub-library.
- **ADR-005 (Statistical Assertion API)** — clarify that statistical assertions (`pass_at_k`, `mann_whitney_u`, `cliffs_delta`) stay in `StatsKeywords` with their domain-specific shapes; AssertionEngine handles only scalar-value comparisons. The two layers compose: `Pass Rate ${runs} >= 0.8` uses the operator, but `Pass Rate Should Stochastically Dominate Baseline` does not.
- **ADR-013 (Sandbox Policy)** — the `validate` operator security gate routes `eval()` through the same RestrictedPython sandbox.
- **ADR-019 (3-Tier Model Routing)** — the polling gate keys off the per-keyword `tier=` annotation; Tier-2 and Tier-3 keywords default to `polling_enabled=False`.
- **ADR-021 (Unified Scenario Test Harness)** — `MCPScenarioKeywords`' hit-rate / count keywords (`Tool Hit Rate`, `Tool Call Count`, `Tool Call Success Rate`) get the operator treatment in Phase 4-E and lose their `Should Be Above` / `Should Be Between` siblings.

## Phased Acceptance Criteria

- **Phase 4-D (1 week, MVP)** — adopt `robotframework-assertion-engine >= 4.0, < 5.0` as a runtime dependency (`uv add robotframework-assertion-engine`); build the `AgentGuard.AssertionAdapter` shim (with `validate` disabled by default and polling-tier gate). Pilot module: `CodingAgentKeywords` metric pairs (12 metric pairs are the highest-leverage starting point per the analyst's table). 24 keywords → 12 keywords. Backwards-compat shim ships emitting nothing yet (silent in 4-D, warnings start in 4-F).
- **Phase 4-E (1 week)** — apply the pattern to `MCPScenarioKeywords` (per ADR-021), `StatsKeywords` (scalar comparators only — distribution comparators stay), `SkillKeywords`, `SecurityKeywords`, `HookKeywords`. CI matrix runs against rf-mcp's 17 scenario YAMLs as the regression net.
- **Phase 4-F (½ week)** — flip the deprecation-warning bit on shim keywords; regenerate libdoc HTML; document the migration in `docs/KEYWORDS.md` and `docs/proposals/keyword-reduction-table.md`; bump minor version. Removal of shim keywords scheduled for the *next* minor after 4-F.
