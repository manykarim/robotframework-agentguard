"""Validates the Phase-2 command-hook handler budget — `mean ≤ 50 ms / call`.

Source: Phase-2 budget extension. A command hook is the most-used handler type
(Claude Code defaults to `command`) and shells out to a real subprocess; the
50 ms ceiling captures *handler-side* overhead (fork+exec+pipe+parse) on top
of whatever the user's hook script does. We use a trivial echo-decision
fixture so the script's own work is ~0.

The fixture script lives at `tests/fixtures/hooks/echo_decision.py` and is
already exercised by the unit suite.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

# Budget — Phase-2 command-hook ceiling.
BUDGET_MEAN_MS_PER_CALL = 50.0

REPO_ROOT = Path(__file__).parent.parent
ECHO_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "hooks" / "echo_decision.py"


def _ensure_executable(script: Path) -> Path:
    """Make sure the fixture script is executable; chmod +x if missing.

    Some checkout flows (e.g. zip downloads) lose the executable bit; the
    handler resolver in `AgentGuard.hooks.handlers` rejects non-executables
    so we proactively repair here rather than skipping the benchmark.
    """
    if not script.exists():
        pytest.skip(f"hook fixture {script} not present")
    mode = os.stat(script).st_mode
    if not (mode & 0o111):
        os.chmod(script, mode | 0o111)
    return script


def _run_command_hook_once(handler: Path, envelope: dict[str, Any]) -> int:
    from AgentGuard.hooks import handlers

    result = handlers.run_command_hook(handler, envelope, timeout=5.0)
    return result.exit_code


@pytest.mark.benchmark(group="hooks-command")
def test_hooks_command_handler_echo(benchmark: Any) -> None:
    """Echo-decision command hook end-to-end — mean ≤ 50 ms / invocation."""
    try:
        from AgentGuard.hooks import handlers as _handlers  # noqa: F401
        from AgentGuard.hooks.envelope import synthesize_envelope
    except ImportError:
        pytest.skip("AgentGuard.hooks not implemented yet")

    handler = _ensure_executable(ECHO_FIXTURE)
    envelope = synthesize_envelope(
        "PreToolUse",
        tool_name="Bash",
        tool_input={"command": "ls"},
        test_decision="allow",
    )

    benchmark.pedantic(
        _run_command_hook_once,
        args=(handler, envelope),
        rounds=20,
        iterations=1,
        warmup_rounds=2,
    )

    mean_ms = float(benchmark.stats.stats.mean) * 1000.0
    if mean_ms > BUDGET_MEAN_MS_PER_CALL:
        pytest.fail(
            f"command hook echo mean {mean_ms:.2f} ms exceeds budget "
            f"{BUDGET_MEAN_MS_PER_CALL} ms (Phase-2 command-hook budget)"
        )
