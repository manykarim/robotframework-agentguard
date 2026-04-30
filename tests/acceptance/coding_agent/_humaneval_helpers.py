"""Robot acceptance helper — drive the HumanEval mini-fixture with LocalDriver.

Lives outside ``__init__`` so the Robot suite's ``Evaluate`` call can pull it
in without triggering the package import machinery on collection.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from AgentGuard.coding_agent.benchmarks.base import RunResult
from AgentGuard.coding_agent.benchmarks.humaneval import HumanEvalLoader
from AgentGuard.coding_agent.drivers.base import DriverConfig
from AgentGuard.coding_agent.drivers.local import LocalDriver


def run() -> dict[str, float]:
    """Run a single HumanEval task with LocalDriver and return the score dict."""
    tasks = HumanEvalLoader.load(limit=1)
    if not tasks:
        return {"n": 0.0, "pass_at_1": 0.0, "pass_rate": 0.0}

    drv = LocalDriver()
    out: list[RunResult] = []
    with tempfile.TemporaryDirectory() as td:
        for task in tasks:
            cfg = DriverConfig(
                jsonl_path=Path(td) / f"{task.id.replace('/', '_')}.jsonl",
                model="openrouter/openai/gpt-4o-mini",
                max_turns=1,
                timeout_seconds=120,
            )
            dr = drv.run(task.prompt, cfg)
            out.append(
                RunResult(
                    task_id=task.id,
                    passed=(dr.exit_code == 0),
                    duration_seconds=dr.duration_ms / 1000.0,
                )
            )
    return HumanEvalLoader.score(out)


__all__ = ["run"]
