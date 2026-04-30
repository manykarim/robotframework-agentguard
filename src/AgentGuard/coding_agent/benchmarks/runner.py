"""Driver-dispatch + per-benchmark validation helpers (research §2.5).

Kept in its own module so :mod:`AgentGuard.coding_agent.benchmarks.library`
stays under the 300-line per-file budget. Everything in here is private to
the benchmarks package — keyword authors should call ``CodingBenchmarkKeywords``
keywords, not these helpers.

The validators all run the candidate code in a *subprocess* (never inline
``exec``) so:

* Benchmark cleanup is automatic on process exit.
* A bad LLM (infinite loop, ``sys.exit``, ``os._exit``) cannot wedge the
  Robot test runner.
* The 10-second per-task hard timeout is enforced by ``subprocess.run``.
"""

from __future__ import annotations

import re
import subprocess  # nosec - sandboxed exec for benchmark validation
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .base import RunResult, Task

if TYPE_CHECKING:  # pragma: no cover
    from AgentGuard.coding_agent.drivers.base import (
        CodingAgentDriver,
        DriverConfig,
        DriverResult,
    )

__all__ = [
    "extract_code",
    "resolve_driver",
    "driver_config",
    "humaneval_validate",
    "mbpp_validate",
    "aider_validate",
    "lcb_validate",
    "swe_bench_plausibility",
    "make_run_result",
    "coerce_task",
    "EXEC_TIMEOUT",
]

#: Hard limit on the seconds we let a candidate solution exec for. Defends
#: against accidental infinite loops in the LLM's output.
EXEC_TIMEOUT = 10

_FENCED_PYTHON = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL)
_FENCED_ANY = re.compile(r"```[a-zA-Z0-9_+-]*\s*\n(.*?)```", re.DOTALL)


def extract_code(text: str) -> str:
    """Best-effort extraction of a Python source block from an LLM response.

    Falls back to the raw text when no fenced block is present (the agent may
    have returned plain code).
    """
    if not text:
        return ""
    match = _FENCED_PYTHON.search(text) or _FENCED_ANY.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def resolve_driver(name: str, provider: Any | None) -> CodingAgentDriver:
    """Resolve a driver name to an instance.

    The drivers context is owned by a sibling agent — we hand off to its
    ``get_driver`` factory when present, and fall back to importing the
    LocalDriver directly so the benchmark keywords are exercisable before
    the registry lands.
    """
    try:
        from AgentGuard.coding_agent import drivers as drivers_pkg

        getter = getattr(drivers_pkg, "get_driver", None)
        if callable(getter):
            return getter(name, provider=provider)  # type: ignore[no-any-return]
    except ImportError:  # pragma: no cover - drivers always shipped Phase-3
        pass
    if name != "local":
        raise RuntimeError(
            f"Driver factory not available; only 'local' is wired in this build "
            f"(requested {name!r})."
        )
    from AgentGuard.coding_agent.drivers.local import LocalDriver

    return LocalDriver(provider=provider)


def driver_config(model: str | None, cwd: str | None) -> DriverConfig:
    from AgentGuard.coding_agent.drivers.base import DriverConfig

    return DriverConfig(model=model, cwd=cwd)


def _run_subprocess_python(
    code: str,
    *,
    stdin: str | None = None,
    timeout: int = EXEC_TIMEOUT,
) -> tuple[bool, str]:
    """Run ``code`` in a subprocess; return ``(ok, stdout-or-stderr)``."""
    with tempfile.NamedTemporaryFile(
        "w", suffix=".py", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(code)
        path = tmp.name
    try:
        proc = subprocess.run(  # noqa: S603 - inputs sourced from fixtures
            [sys.executable, path],
            input=stdin,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if proc.returncode == 0:
            return True, proc.stdout
        return False, (proc.stderr or proc.stdout)
    except subprocess.TimeoutExpired:
        return False, f"timeout after {timeout}s"
    finally:
        Path(path).unlink(missing_ok=True)


def humaneval_validate(candidate_code: str, task: Task) -> tuple[bool, str]:
    """Run HumanEval's ``check(candidate)`` against the candidate."""
    test = str(task.metadata.get("test") or "")
    entry = str(task.metadata.get("entry_point") or "")
    if not test or not entry:
        return False, "missing test or entry_point in fixture metadata"
    program = (
        f"{candidate_code}\n\n{test}\n\n"
        f"check({entry})\nprint('AGENTGUARD_OK')\n"
    )
    return _run_subprocess_python(program)


def mbpp_validate(candidate_code: str, task: Task) -> tuple[bool, str]:
    """Exec the candidate and assert each MBPP test_list entry."""
    tests = task.metadata.get("tests") or []
    setup = str(task.metadata.get("test_setup_code") or "")
    if not tests:
        return False, "missing tests in fixture metadata"
    asserts = "\n".join(str(t) for t in tests)
    program = f"{setup}\n{candidate_code}\n{asserts}\nprint('AGENTGUARD_OK')\n"
    return _run_subprocess_python(program)


def aider_validate(candidate_code: str, task: Task) -> tuple[bool, str]:
    """Run Aider's check() (exercism-shape) against the candidate."""
    test = str(task.metadata.get("test") or "")
    entry = str(task.metadata.get("entry_point") or "")
    if not test or not entry:
        return False, "missing test or entry_point in fixture metadata"
    program = (
        f"{candidate_code}\n\n{test}\n\ncheck({entry})\nprint('AGENTGUARD_OK')\n"
    )
    return _run_subprocess_python(program)


def lcb_validate(candidate_code: str, task: Task) -> tuple[bool, str]:
    """Run all public+private LCB test cases (stdin/stdout)."""
    cases = list(task.metadata.get("public_test_cases") or []) + list(
        task.metadata.get("private_test_cases") or []
    )
    if not cases:
        return False, "no test cases in fixture metadata"
    for idx, case in enumerate(cases):
        if not isinstance(case, dict):
            continue
        stdin = str(case.get("input", ""))
        expected = str(case.get("output", ""))
        ok, output = _run_subprocess_python(candidate_code, stdin=stdin)
        if not ok:
            return False, f"case {idx}: {output}"
        if output.strip() != expected.strip():
            return (
                False,
                f"case {idx}: expected {expected!r}, got {output!r}",
            )
    return True, "all cases passed"


def swe_bench_plausibility(text: str) -> tuple[bool, str]:
    """Heuristic Phase-3 SWE-bench scorer: did the agent emit a unified diff?

    Phase 4 will replace this with the real apply-patch + ``test_cmd`` loop
    under Docker; for now we approximate "made a non-trivial attempt" with a
    diff-format check so the keyword surface is exercisable in CI.
    """
    looks_like_diff = (
        "diff --git" in text
        or text.lstrip().startswith("--- ")
        or text.lstrip().startswith("+++ ")
    )
    if looks_like_diff:
        return True, "plausible diff emitted (Phase-3 scorer)"
    return False, "no diff in agent output (Phase-3 scorer)"


def make_run_result(
    task: Task,
    *,
    passed: bool,
    duration_s: float,
    diff: str | None,
    test_output: str | None,
    driver_result: DriverResult | None,
) -> RunResult:
    return RunResult(
        task_id=task.id,
        passed=passed,
        duration_seconds=duration_s,
        diff=diff,
        test_output=test_output,
        cost_usd=getattr(driver_result, "cost_usd", None) if driver_result else None,
        session_jsonl_path=(
            getattr(driver_result, "jsonl_path", None) if driver_result else None
        ),
    )


def coerce_task(task: Task | dict[str, Any]) -> Task:
    """Robot Framework keyword args may be dicts when ingested via JSON."""
    if isinstance(task, Task):
        return task
    return Task(
        id=str(task.get("id", "")),
        prompt=str(task.get("prompt", "")),
        test_command=task.get("test_command"),
        repo_path=task.get("repo_path"),
        expected_files=list(task.get("expected_files") or []),
        metadata=dict(task.get("metadata") or {}),
    )
