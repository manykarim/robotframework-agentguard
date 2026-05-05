"""Live HumanEval smoke test (live-tagged).

Loads the bundled HumanEval mini-fixture (5 tasks), runs 2 of them through
:class:`LocalDriver` against OpenRouter ``gpt-4o-mini``, and asserts the
plumbing — we are NOT measuring model quality here, only that the
load → driver → score path works end-to-end without errors.

Cost cap: ≤ $0.05 per run (2 turns × ~$0.0001/turn).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

try:
    from AgentGuard.coding_agent.benchmarks.base import RunResult
    from AgentGuard.coding_agent.benchmarks.humaneval import HumanEvalLoader
    from AgentGuard.coding_agent.drivers.base import DriverConfig
    from AgentGuard.coding_agent.drivers.local import LocalDriver
except ImportError:  # pragma: no cover — Phase 3 race
    pytest.skip("phase3: humaneval/local not yet implemented", allow_module_level=True)


@pytest.mark.live
@pytest.mark.slow
def test_humaneval_two_task_smoke(tmp_path: Path) -> None:
    """Smoke test: load 5 HumanEval tasks, run 2 with LocalDriver, assert pass@1 >= 0.

    We deliberately don't validate the generated code — the assertion is on
    the WIRING, not the LLM's correctness.
    """
    if not os.getenv("OPENROUTER_API_KEY"):
        pytest.skip("live test requires OPENROUTER_API_KEY")

    tasks = HumanEvalLoader.load(limit=5)
    assert len(tasks) == 5

    drv = LocalDriver()
    results: list[RunResult] = []
    for task in tasks[:2]:
        cfg = DriverConfig(
            jsonl_path=tmp_path / f"{task.id.replace('/', '_')}.jsonl",
            model="openrouter/openai/gpt-4o-mini",
            max_turns=1,
            timeout_seconds=120,
        )
        dr = drv.run(task.prompt, cfg)
        # passed=True/False is meaningless here — we don't actually run the
        # check() function. We're proving the wiring works.
        results.append(
            RunResult(
                task_id=task.id,
                passed=(dr.exit_code == 0),
                duration_seconds=dr.duration_ms / 1000.0,
                cost_usd=dr.cost_usd,
                session_jsonl_path=dr.jsonl_path,
            )
        )

    score = HumanEvalLoader.score(results)
    assert score["n"] == 2.0
    # Smoke: pass@1 might be 0 (gpt-4o-mini may not always emit a complete
    # implementation in a 1-turn ReAct loop); we only assert it's a fraction.
    assert 0.0 <= score["pass_at_1"] <= 1.0


@pytest.mark.live
def test_humaneval_score_dict_shape() -> None:
    """The score() contract must return the canonical keys regardless of input."""
    if not os.getenv("OPENROUTER_API_KEY"):
        pytest.skip("live test requires OPENROUTER_API_KEY")

    out = HumanEvalLoader.score([RunResult(task_id="t1", passed=True, duration_seconds=0.1)])
    assert {"n", "pass_at_1", "pass_rate"}.issubset(out)
