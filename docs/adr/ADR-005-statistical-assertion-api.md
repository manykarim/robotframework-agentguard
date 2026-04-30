# ADR-005: Statistical Assertion API

- **Status**: Proposed
- **Date**: 2026-04-29
- **Deciders**: agentguard-architecture-swarm
- **Bounded Context**: Statistics

## Context

Multiple peer-reviewed studies (Atil et al., Song et al., *Beyond Reproducibility*) confirm that even with `temperature=0` and fixed seeds, LLMs vary up to 15% across runs and 70% best-vs-worst due to floating-point rounding in fused attention/normalisation kernels and shared-batch effects on cloud providers (research §2.7, risk #4). A single-shot pass/fail assertion is therefore statistically meaningless for any LLM-mediated metric.

The accepted machinery includes: Mann-Whitney U / Wilcoxon (non-parametric stochastic-dominance tests), Cliff's delta and Vargha-Delaney A (effect-size measures), bootstrap CIs, pass@k (HumanEval convention), Total Agreement Rate `TARr@N` / `TARa@N` (Atil et al.), and classification-based LLM-as-Judge.

scipy provides Mann-Whitney/Wilcoxon, bootstrap, and supporting primitives; Cliff's delta, Vargha-Delaney, TAR, and pass@k must be implemented locally.

## Decision

Ship a `StatsKeywords` sub-library (scipy-backed where possible) exposing: `Run N Times`, `Pass At K Should Be Above`, `Total Agreement Rate Should Be Above`, `Mann Whitney U Should Show Improvement`, `Cliffs Delta Should Be At Least`, `Bootstrap Confidence Interval Should Contain`, `LLM Judge Should Score At Least`. **Default N = 10** for any LLM-mediated assertion; emit a "non-deterministic test report" header in `log.html` showing actual variance observed.

## Rationale

- N≥10 is the minimum that produces a meaningful Mann-Whitney U (research §2.7).
- scipy is the ecosystem standard, BSD-licensed, already a Robot Framework community dependency in many projects.
- Forcing the report-header banner makes statistical caveats visible to QA reviewers, mitigating misinterpretation.
- Combining deterministic checks (BFCL AST, ADR-004) with statistical assertions (this ADR) is the Hamel Husain / Braintrust best practice (research risk #1).

## Consequences

- **Positive**: Statistically defensible regression testing; native integration with #42796 metrics (ADR-010); CI failures on real degradation rather than noise.
- **Negative**: 10× runtime/cost per LLM-mediated test by default; teams must budget accordingly.
- **Neutral**: Users can lower N for local iteration via `Run N Times runs=3` but assertion variants will warn when N < 10.

## Alternatives Considered

- **Option A — Single-run pass/fail**: rejected, statistically meaningless given documented LLM nondeterminism.
- **Option B — Only pass@k**: rejected, doesn't support effect-size or baseline comparison; insufficient for regression detection.
- **Option C — Fixed Bayesian framework**: rejected, steeper learning curve, less familiar to QA engineers than scipy frequentist tests.

## Related ADRs

- ADR-010 (#42796 metric calculators feed this Stats API)
- ADR-011 (LLM-as-Judge results are aggregated by the same `Run N Times` machinery)
- ADR-015 (SONA self-learning records every run, feeding baseline distributions)
