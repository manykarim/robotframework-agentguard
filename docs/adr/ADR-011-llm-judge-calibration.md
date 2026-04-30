# ADR-011: LLM-as-Judge Calibration

- **Status**: Proposed
- **Date**: 2026-04-29
- **Deciders**: agentguard-architecture-swarm
- **Bounded Context**: Judge

## Context

LLM-as-Judge is the only practical scorer for many free-form outputs (skill quality, semantic equivalence, rubric-based grading). Hamel Husain and Braintrust both stress that judges drift, must be validated against human labels, and should be **classification-based** (e.g., rubric categories) rather than numeric scoring (which is noisier and harder to calibrate) (research §2.7, risk #1).

Common failure modes: judge model inflates scores ("everything is a 7"); judge model has positional bias (always picks first option in pairwise); judge model agrees with verbose-but-wrong over concise-but-right. Without calibration against human labels, these biases silently degrade test signal.

Inter-rater agreement metrics (Cohen's κ for binary/categorical, Krippendorff's α for ordinal/multi-rater) provide an objective gate. Cohen's κ ≥ 0.7 is the conventional "substantial agreement" threshold; below that, the judge is not trustworthy enough to score real runs.

Pending experiment `exp_11` is calibrating Sonnet/Opus/Haiku judges against a 200-item human-labeled set to determine which qualify.

## Decision

All LLM judges must be **classification-based** (categorical rubric labels, not numeric scores). Before any judge can score real test runs, it must pass a `Calibrate Judge` keyword that runs it against a human-labeled set and computes Cohen's κ. **Judges with κ < 0.7 are blocked** from scoring; they raise `JudgeNotCalibratedError` until either re-calibrated or explicitly bypassed via `--allow-uncalibrated-judge`.

## Rationale

- Classification beats numeric scoring (Hamel Husain, Braintrust, mcpx-eval — research §2.7).
- κ ≥ 0.7 is the industry-standard "substantial agreement" threshold.
- Hard-fail-by-default prevents teams from accidentally shipping a miscalibrated judge into CI.
- Bypass flag (with explicit naming) allows controlled experimentation without weakening the default.

## Consequences

- **Positive**: Judge quality is auditable and gateable; biases caught before they pollute CI; human-labeled set becomes a reusable calibration asset.
- **Negative**: Up-front cost to build the human-labeled calibration set; teams without one cannot use LLM-as-Judge until they create it.
- **Neutral**: Calibration must be re-run when judge model changes (e.g., Sonnet 4.5 → 4.6); ADR-014 spec pinning helps detect this.

## Alternatives Considered

- **Option A — Trust judge by default**: rejected, contradicts published best practice (Husain, Braintrust).
- **Option B — Numeric scoring with confidence intervals**: rejected, numeric scoring drift is poorly bounded; classification gives discrete categories that κ can measure.
- **Option C — Multi-judge ensemble without calibration**: rejected, ensembles of biased judges produce biased averages; calibration must precede ensembling.

## Related ADRs

- ADR-001 (Judge model selected via the same provider adapter)
- ADR-005 (Judge scores feed Stats API for cross-run aggregation)
- ADR-019 (Tier 2/3 routing chooses Haiku vs Sonnet/Opus judge per task complexity)
- **Hard dependency on pending experiment `exp_11` (judge calibration κ)**
