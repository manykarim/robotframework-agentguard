"""End-to-end skill-grading benchmark with a *mock* model — `total ≤ 1 s` for N=10.

Validates `docs/performance/budgets.md` §3 — fast preflight scenario, except
that the LLM call is replaced with the LiteLLM `mock_response=` primitive
confirmed in `exp_03`. Wall-clock should therefore be dominated by Inspect AI's
Task/Solver/Scorer overhead — under 1 s on a modern laptop.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

# Wall-clock ceiling for N=10 reps with the mockllm provider.
BUDGET_TOTAL_S = 1.0


@pytest.mark.benchmark(group="skills")
def test_skill_grade_offline_n10(benchmark: Any, sample_skill_dir: Path) -> None:
    """Run `run_skill_eval` with `mockllm/model` for N=10; fail if >1 s."""
    try:
        from AgentGuard.skills.grader import GraderConfig, run_skill_eval
    except ImportError:
        pytest.skip("AgentGuard.skills.grader not implemented yet")

    cfg = GraderConfig(
        runs=10,
        prompts=["Say 'OK'."],
        model="mockllm/model",
        judge_model="mockllm/model",
    )

    def _grade() -> Any:
        return run_skill_eval(sample_skill_dir, cfg)

    benchmark.pedantic(_grade, rounds=1, iterations=1, warmup_rounds=0)
    total_s = float(benchmark.stats.stats.mean)
    if total_s > BUDGET_TOTAL_S:
        pytest.fail(
            f"skill grade total {total_s:.3f} s exceeds budget {BUDGET_TOTAL_S} s "
            "(budgets.md §3 — fast preflight)"
        )
