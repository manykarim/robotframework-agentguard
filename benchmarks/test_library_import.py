"""Validates `docs/performance/budgets.md` §5 — Library import + first keyword <2 s.

Spawns a fresh Python subprocess so import-cache effects do not falsify the
measurement. We measure two checkpoints in a single subprocess run:

1. `import AgentGuard` + `AgentGuard()` construction.
2. First keyword call (`Get AgentGuard Info`).

Both must complete inside the 2 s **suite-setup** ceiling.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from typing import Any

import pytest

BUDGET_TOTAL_S = 2.0


_INNER = textwrap.dedent(
    """
    import json, time, importlib, sys
    t0 = time.perf_counter()
    mod = importlib.import_module("AgentGuard")
    AgentGuard = mod.AgentGuard
    inst = AgentGuard(provider="mock", telemetry=False, env_file=None)
    t_import = time.perf_counter() - t0
    info = inst.get_agentguard_info()
    t_first_kw = time.perf_counter() - t0
    sys.stdout.write(json.dumps({
        "import_s": t_import,
        "first_kw_s": t_first_kw,
        "components": info.get("components", []),
    }))
    """
).strip()


@pytest.mark.benchmark(group="startup")
def test_library_import_and_first_keyword(benchmark: Any) -> None:
    """Cold-import + construct + first keyword call, in a fresh subprocess."""
    captured: dict[str, Any] = {}

    def _run() -> None:
        proc = subprocess.run(
            [sys.executable, "-c", _INNER],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        captured.update(json.loads(proc.stdout))

    benchmark.pedantic(_run, rounds=2, iterations=1, warmup_rounds=0)

    first_kw_s = float(captured.get("first_kw_s", 0.0))
    if first_kw_s == 0.0:
        pytest.fail("library import benchmark produced no measurement")
    if first_kw_s > BUDGET_TOTAL_S:
        pytest.fail(
            f"Library import + first keyword {first_kw_s:.3f} s exceeds budget {BUDGET_TOTAL_S} s (budgets.md §5)"
        )
