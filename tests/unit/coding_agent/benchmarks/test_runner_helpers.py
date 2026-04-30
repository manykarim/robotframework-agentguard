"""Unit tests for ``benchmarks.runner`` — code-extract + per-suite validators.

These run real subprocesses (Python invokes itself with a tiny script), so
they are network-free but not 100% sandbox-free; the ``EXEC_TIMEOUT`` keeps
runaway code from wedging CI.
"""

from __future__ import annotations

import pytest

try:
    from AgentGuard.coding_agent.benchmarks import runner
    from AgentGuard.coding_agent.benchmarks.base import Task
except ImportError:  # pragma: no cover — Phase 3 race
    pytest.skip("phase3: benchmarks.runner not yet implemented", allow_module_level=True)


# ---------------------------- extract_code ---------------------------------


def test_extract_code_python_fence() -> None:
    body = "Here is the answer:\n```python\ndef add(a, b):\n    return a + b\n```\nOK?"
    out = runner.extract_code(body)
    assert "def add" in out
    assert "Here is" not in out


def test_extract_code_generic_fence() -> None:
    out = runner.extract_code("```py\nprint('hi')\n```")
    assert out == "print('hi')"


def test_extract_code_no_fence_returns_raw() -> None:
    out = runner.extract_code("def foo(): pass")
    assert out == "def foo(): pass"


def test_extract_code_empty_string() -> None:
    assert runner.extract_code("") == ""


# ---------------------------- humaneval_validate ---------------------------


def test_humaneval_validate_passes_for_correct_code() -> None:
    task = Task(
        id="t",
        prompt="",
        metadata={
            "entry_point": "add",
            "test": "def check(candidate):\n    assert candidate(1, 2) == 3\n",
        },
    )
    code = "def add(a, b):\n    return a + b\n"
    ok, output = runner.humaneval_validate(code, task)
    assert ok is True
    assert "AGENTGUARD_OK" in output


def test_humaneval_validate_fails_for_wrong_code() -> None:
    task = Task(
        id="t",
        prompt="",
        metadata={
            "entry_point": "add",
            "test": "def check(candidate):\n    assert candidate(1, 2) == 3\n",
        },
    )
    code = "def add(a, b):\n    return 0\n"
    ok, _ = runner.humaneval_validate(code, task)
    assert ok is False


def test_humaneval_validate_missing_entry_point_returns_false() -> None:
    task = Task(id="t", prompt="", metadata={})
    ok, output = runner.humaneval_validate("def x(): pass", task)
    assert ok is False
    assert "missing" in output


# ---------------------------- mbpp_validate --------------------------------


def test_mbpp_validate_passes() -> None:
    task = Task(
        id="t",
        prompt="",
        metadata={
            "tests": ["assert factorial(0) == 1", "assert factorial(3) == 6"],
            "test_setup_code": "",
        },
    )
    code = "def factorial(n):\n    return 1 if n <= 1 else n * factorial(n - 1)\n"
    ok, _ = runner.mbpp_validate(code, task)
    assert ok is True


def test_mbpp_validate_fails_with_no_tests() -> None:
    task = Task(id="t", prompt="", metadata={})
    ok, output = runner.mbpp_validate("def f(): pass", task)
    assert ok is False
    assert "missing" in output


# ---------------------------- swe_bench_plausibility -----------------------


def test_swe_bench_plausibility_detects_diff() -> None:
    ok, _ = runner.swe_bench_plausibility("diff --git a/foo.py b/foo.py\n--- a/foo.py\n+++ b/foo.py\n")
    assert ok is True


def test_swe_bench_plausibility_negative() -> None:
    ok, _ = runner.swe_bench_plausibility("just text, no diff here")
    assert ok is False


# ---------------------------- coerce_task ----------------------------------


def test_coerce_task_passes_task_through() -> None:
    t = Task(id="x", prompt="hi")
    assert runner.coerce_task(t) is t


def test_coerce_task_builds_from_dict() -> None:
    out = runner.coerce_task(
        {
            "id": "x",
            "prompt": "hi",
            "test_command": "pytest",
            "expected_files": ["a.py"],
            "metadata": {"k": "v"},
        }
    )
    assert isinstance(out, Task)
    assert out.id == "x"
    assert out.test_command == "pytest"
    assert out.expected_files == ["a.py"]
    assert out.metadata == {"k": "v"}


# ---------------------------- make_run_result ------------------------------


def test_make_run_result_builds_with_no_driver() -> None:
    t = Task(id="x", prompt="")
    r = runner.make_run_result(t, passed=True, duration_s=0.1, diff=None, test_output="ok", driver_result=None)
    assert r.task_id == "x"
    assert r.passed is True
    assert r.cost_usd is None
    assert r.session_jsonl_path is None


# ---------------------------- resolve_driver -------------------------------


def test_resolve_driver_local() -> None:
    drv = runner.resolve_driver("local", provider=None)
    assert drv.name == "local"


def test_driver_config_carries_args() -> None:
    cfg = runner.driver_config(model="m", cwd="/tmp")
    assert cfg.model == "m"
    assert cfg.cwd == "/tmp"
