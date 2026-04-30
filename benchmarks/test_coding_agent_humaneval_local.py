"""Validates the Phase-3 HumanEval live smoke budget — total ≤ 30 s, cost ≤ $0.005.

Source: Phase-3 brief. Single-task HumanEval end-to-end with the
``LocalDriver`` against ``openrouter/openai/gpt-4o-mini``. This is a
**wiring smoke**, not a model-quality benchmark — we only assert latency +
cost ceilings, not the pass@k value.

Gated by ``@pytest.mark.live`` and ``OPENROUTER_API_KEY``. Skips cleanly when:

* the env var is missing
* the HumanEval loader is not yet implemented (parallel Phase-3 race)
* the LocalDriver / mini-fixture cannot be located
"""

from __future__ import annotations

import os
import time
from typing import Any

import pytest

# Budgets — Phase-3 HumanEval live ceiling.
BUDGET_TOTAL_S = 30.0
BUDGET_COST_USD = 0.005


def _have_openrouter_key() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY"))


@pytest.mark.live
@pytest.mark.benchmark(group="coding-agent-humaneval-live")
def test_humaneval_local_one_task_live(benchmark: Any) -> None:
    """One HumanEval task end-to-end via LocalDriver/openrouter — ≤ 30 s, ≤ $0.005."""
    if not _have_openrouter_key():
        pytest.skip("OPENROUTER_API_KEY missing — live HumanEval smoke skipped")

    try:
        from AgentGuard.coding_agent.benchmarks import registry as bench_registry
    except ImportError:
        pytest.skip("AgentGuard.coding_agent.benchmarks.registry not implemented yet")
    try:
        from AgentGuard.coding_agent.drivers.base import DriverConfig
        from AgentGuard.coding_agent.drivers.local import LocalDriver
    except ImportError:
        pytest.skip("AgentGuard.coding_agent.drivers.local not implemented yet")

    # Resolve the HumanEval loader (real ``datasets`` or bundled mini fixture).
    try:
        Loader = bench_registry.get_loader("humaneval")
    except Exception as exc:  # noqa: BLE001 — defensive, loader-dispatch race
        pytest.skip(f"HumanEval loader not resolvable: {exc}")

    try:
        loader = Loader()
        tasks = list(loader.load(limit=1))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"HumanEval load failed: {exc}")

    if not tasks:
        pytest.skip("HumanEval loader returned 0 tasks")

    task = tasks[0]
    driver = LocalDriver()
    if not driver.is_available():
        pytest.skip("LocalDriver reports unavailable (provider build failed)")

    cfg = DriverConfig(
        model="openrouter/openai/gpt-4o-mini",
        max_turns=4,
        capture_jsonl=True,
    )

    cost_holder: dict[str, float] = {}

    def _run_once() -> bool:
        start = time.perf_counter()
        result = driver.run(prompt=task.prompt, config=cfg)
        cost_holder["last_cost"] = float(result.cost_usd or 0.0)
        cost_holder["last_duration"] = time.perf_counter() - start
        return bool(result)

    ok = benchmark.pedantic(_run_once, rounds=1, iterations=1, warmup_rounds=0)
    assert ok, "LocalDriver returned a falsy result"

    duration_s = float(benchmark.stats.stats.mean)
    if duration_s > BUDGET_TOTAL_S:
        pytest.fail(
            f"HumanEval live total {duration_s:.2f} s exceeds budget {BUDGET_TOTAL_S} s (Phase-3 HumanEval live)"
        )

    last_cost = cost_holder.get("last_cost", 0.0)
    if last_cost > BUDGET_COST_USD:
        pytest.fail(
            f"HumanEval live cost ${last_cost:.5f} exceeds budget ${BUDGET_COST_USD:.5f} (Phase-3 HumanEval live)"
        )
