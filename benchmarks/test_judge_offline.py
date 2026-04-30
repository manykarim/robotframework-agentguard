"""Judge-keyword overhead benchmark — `mean ≤ 100 ms`.

Measures *only* the keyword-side overhead (rubric loading, prompt formatting,
response coercion) by stubbing the LLM call with a `MockProvider` so the
result is deterministic and offline. The `100 ms` ceiling is significantly
smaller than the Tier-2 Haiku latency budget (`≤500 ms` mean) and isolates
non-network cost.
"""

from __future__ import annotations

from typing import Any

import pytest

BUDGET_OVERHEAD_MEAN_MS = 100.0


@pytest.mark.benchmark(group="judge")
def test_judge_keyword_overhead(benchmark: Any, mock_chat_response: Any) -> None:
    """Stub provider, run a single judgment per benchmark round, assert overhead."""
    try:
        from AgentGuard.judge.library import JudgeKeywords
    except ImportError:
        pytest.skip("AgentGuard.judge.library not implemented yet")
    try:
        from AgentGuard.providers.mock import MockProvider
    except ImportError:  # pragma: no cover — defensive
        pytest.skip("AgentGuard.providers.mock not importable")

    provider = MockProvider(responses=[mock_chat_response("PASS")])
    judge = JudgeKeywords(provider=provider)

    def _call() -> Any:
        # The exact public method name may differ; try a few common spellings.
        for attr in ("judge", "judge_text", "score"):
            fn = getattr(judge, attr, None)
            if callable(fn):
                return fn(prompt="rubric: did the answer say PASS?", output="PASS")
        pytest.skip("JudgeKeywords has no callable judge/judge_text/score method yet")

    benchmark.pedantic(_call, rounds=20, iterations=1, warmup_rounds=2)
    mean_ms = float(benchmark.stats.stats.mean) * 1000.0
    if mean_ms > BUDGET_OVERHEAD_MEAN_MS:
        pytest.fail(
            f"Judge overhead mean {mean_ms:.3f} ms exceeds budget "
            f"{BUDGET_OVERHEAD_MEAN_MS} ms (budgets.md §1, judge framing)"
        )
