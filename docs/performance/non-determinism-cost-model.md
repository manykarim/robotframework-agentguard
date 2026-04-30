# Non-Determinism Cost Model

> Default `N≥10` reps (research §2.7, §8 risk #4) interacts multiplicatively with tier routing. This file shows the full cost matrix for the canonical 30-skill suite, then identifies the three highest-leverage optimizations. All per-rep numbers come from `budgets.md §4`.

---

## 1. Baseline Cost Matrix — 30 skills × N reps × tier

Per-rep cost (judge call only; subject model attributed to system-under-test). Mix: 2K-in / 500-out tokens per Anthropic Apr-2026 pricing.

| Tier (judge) | $/rep | N=1 / 30 skills | N=10 / 30 skills | N=30 / 30 skills (canary) | N=100 / 30 skills (calibration) |
|--------------|-------|-----------------|------------------|---------------------------|---------------------------------|
| **1** (no LLM) | $0.0000 | $0.00 | **$0.00** | $0.00 | $0.00 |
| **2** Haiku | $0.0034 | $0.10 | **$1.02** | $3.06 | $10.20 |
| **3** Sonnet | $0.0135 | $0.41 | **$4.05** | $12.15 | $40.50 |
| **3** Opus | $0.0675 | $2.03 | **$20.25** | $60.75 | $202.50 |

**Realistic mix per CI build** (Phase 1 default): 70% of assertions are Tier 1 (BFCL + #42796 + stats), 25% are Tier 2 (simple semantic equivalence + plausibility), 5% are Tier 3 Sonnet (multi-criterion judging). Per-skill blended cost at N=10:

```
$0.00 × 0.70 + $0.034 × 0.25 + $0.135 × 0.05  ≈  $0.015 / skill
30 skills × $0.015                              =  $0.45 / build
```

A daily CI build at this mix costs **≈$0.45/day, ≈$13.50/month**. Nightly canary at N=30 with full-Sonnet rubric: **≈$12/night, ≈$360/month**. Calibration runs (N=100, Opus, infrequent): **≈$200/run, budgeted quarterly**.

The numbers stored in RuFlo memory key `perf_cost_projection_30skills` are: `tier1=$0, tier2=$1.02, tier3_sonnet=$4.05, tier3_opus=$20.25` (all at N=10, full-suite, no optimizations).

---

## 2. The Three Highest-Leverage Optimizations

Ranked by expected $-saved-per-engineering-hour. Each is detailed enough to scope as a Phase-1 work item.

### Optimization #1 — Cached judgments (expected: ~70% cost reduction on stable suites)

**Mechanism.** Hash `(skill_content_sha256, rubric_sha256, judge_model_id, judge_prompt_template_version)` → reuse the prior judgment if the hash is unchanged. Store cache in AgentDB (HNSW already required for memory-specialist work). Default TTL 30 days; invalidated on any input change or on a `--no-cache` CI flag.

**Why it dominates.** In a stable suite the rubric and skill changes are rare; the only thing that varies run-to-run is the *subject model's* output, which is what the judge is judging — but the judgment for an identical subject output against an identical rubric *is* deterministic enough to cache. Empirically (Inspect AI, Braintrust public reports) cache hit rates of 60-80% are typical after week 1 of a new suite. At 70% hit rate the realistic-mix daily build drops from $0.45 → ~$0.14.

**Risk.** Stale caches mask judge-model upgrades. Mitigation: include `judge_model_id` in the hash and enforce a hard TTL.

`[ASSUMPTION → exp_09]`: measure actual hit rate on the 10 reference suites after 30 days.

### Optimization #2 — Adaptive N (expected: ~50% cost reduction on stable suites, no quality loss)

**Mechanism.** Start every skill at N=3. Compute bootstrap CI on the assertion metric. If CI half-width < 0.05 *and* all 3 reps agreed, declare stable and skip the remaining 7 reps. Otherwise add reps in batches of 3 until CI converges or N=10 is hit. For flaky skills the router automatically *raises* N to 30 the next run (recorded in AgentDB).

**Why it works.** Stable skills do not need N=10 to prove stability; flaky skills *need more than 10*. Static N=10 is the worst of both. Atil et al. (research §2.7) show that ~60% of well-designed evaluations stabilize at N≤5.

**Cost impact.** Realistic-mix daily build with adaptive N: $0.45 → ~$0.22. Combined with cache (compounding): $0.45 → ~$0.07.

`[ASSUMPTION → exp_10]`: measure stabilization rate on canonical 30-skill suite; if <50% stabilize at N≤5, the optimization saves less than projected.

### Optimization #3 — Smart routing (WASM-first, escalate on ambiguity) (expected: ~30% additional reduction by avoiding unnecessary Tier-3)

**Mechanism.** The `hooks_route` MCP tool's score (see `tier-routing.md §3`) is computed *before* any LLM call. For semantic-equivalence checks, run a Tier-1 deterministic check first (string normalize → regex → AST diff → embedding cosine ≥0.95). Only if all four fail does the router escalate to Tier 2; only if Tier 2 returns "ambiguous" (judge confidence <0.6) does it escalate to Tier 3. This is exactly the cascade pattern from CLAUDE.md ADR-026.

**Cost impact.** Roughly 50% of the 25% "Tier 2" share in the realistic mix collapses to Tier 1 once the deterministic prefilters pass; ~10% of the 5% "Tier 3 Sonnet" share collapses to Tier 2. Net: another 20-30% cost reduction *after* cache + adaptive N.

`[ASSUMPTION → exp_11]`: measure prefilter pass rate on the reference rubric set.

### Honorable mentions (smaller leverage, still worth doing)

- **Batched LLM calls.** Where a rubric supports it, judge N samples in one prompt (one round-trip, ~10% input-token amortization, ~30% latency savings). Limited applicability — most rubrics need per-sample rationale.
- **Provider routing via LiteLLM Router.** Cheapest-acceptable model per assertion class (e.g. DeepSeek for non-rationale judging). 2-4× cost reduction *if* a non-Anthropic judge is acceptable to the user — opt-in only because it changes the validity profile.

---

## 3. Combined Optimization Stack — Projected Bottom Line

| Configuration | Daily CI cost (30 skills, blended) | Nightly canary (N=30, Sonnet) |
|---------------|-------------------------------------|-------------------------------|
| Naive (no optimizations) | $0.45 | ~$12 |
| + Cache (70% hit) | $0.14 | ~$3.60 |
| + Adaptive N (50% stable) | $0.07 | ~$1.80 |
| + Smart routing prefilters | **$0.05** | **~$1.30** |

A team running the full 30-skill suite on every PR (≈100 PRs/month) with all three optimizations enabled spends **<$10/month on judge calls**. The same team without any optimizations spends ~$45/month — recoverable, but the *order of magnitude* matters for adoption.

---

## 4. Cost Ceiling Enforcement

The library ships a hard `Cost Ceiling Should Not Be Exceeded` Tier-1 keyword that halts the suite when the cumulative LiteLLM ledger exceeds a configurable cap (default: per-skill ceilings from `budgets.md §4` × number of skills × 1.5 safety factor). This prevents a misconfigured rubric or a runaway loop from burning the team's budget.
