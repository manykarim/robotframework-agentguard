"""Direct unit tests for the new Phase 2 sandbox keywords on SecurityKeywords."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from AgentGuard.security.library import SecurityKeywords
from AgentGuard.security.sandbox_backends.base import SandboxResult


@pytest.fixture
def kw() -> SecurityKeywords:
    return SecurityKeywords()


def _ok_result(stdout: str = "hello", stderr: str = "", exit_code: int = 0) -> SandboxResult:
    return SandboxResult(
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_ms=12.3,
        backend="docker",
        image="python:3.12-alpine",
        container_id="abc123",
    )


# ---- Sandbox Output Should Contain ----


def test_sandbox_output_should_contain_stdout(kw: SecurityKeywords) -> None:
    kw.sandbox_output_should_contain(_ok_result(stdout="hello world"), "hello")


def test_sandbox_output_should_contain_stderr(kw: SecurityKeywords) -> None:
    kw.sandbox_output_should_contain(_ok_result(stdout="", stderr="warning: x"), "warning")


def test_sandbox_output_should_contain_raises_when_missing(kw: SecurityKeywords) -> None:
    with pytest.raises(AssertionError, match="does not contain"):
        kw.sandbox_output_should_contain(_ok_result(stdout="actual", stderr=""), "expected")


# ---- Sandbox Exit Code Should Be ----


def test_sandbox_exit_code_should_be_passes(kw: SecurityKeywords) -> None:
    kw.sandbox_exit_code_should_be(_ok_result(exit_code=0), 0)


def test_sandbox_exit_code_should_be_raises_on_mismatch(kw: SecurityKeywords) -> None:
    with pytest.raises(AssertionError, match="exit code mismatch"):
        kw.sandbox_exit_code_should_be(_ok_result(exit_code=1), 0)


# ---- Run In Sandbox (mocked dispatcher) ----


def test_run_in_sandbox_dispatches_to_run_in_sandbox(kw: SecurityKeywords) -> None:
    expected = _ok_result(stdout="dispatched")
    with patch("AgentGuard.security.sandbox.run_in_sandbox", return_value=expected) as run:
        out = kw.run_in_sandbox(["echo", "hi"], image="python:3.12-alpine")
    assert out is expected
    args, kwargs = run.call_args
    assert kwargs.get("image") == "python:3.12-alpine"


def test_run_in_sandbox_propagates_backend(kw: SecurityKeywords) -> None:
    expected = _ok_result()
    with patch("AgentGuard.security.sandbox.run_in_sandbox", return_value=expected) as run:
        kw.run_in_sandbox(["true"], backend="process", allow_code_execution=True)
    policy = run.call_args[0][0]
    assert policy.backend == "process"
    assert policy.allow_code_execution is True


def test_run_in_sandbox_passes_timeout(kw: SecurityKeywords) -> None:
    expected = _ok_result()
    with patch("AgentGuard.security.sandbox.run_in_sandbox", return_value=expected) as run:
        kw.run_in_sandbox(["true"], timeout_seconds=15)
    assert run.call_args.kwargs.get("timeout_seconds") == 15


def test_run_in_sandbox_network_allowed_flag(kw: SecurityKeywords) -> None:
    expected = _ok_result()
    with patch("AgentGuard.security.sandbox.run_in_sandbox", return_value=expected) as run:
        kw.run_in_sandbox(["true"], network_allowed=True, allow_code_execution=True)
    policy = run.call_args[0][0]
    assert policy.network_allowed is True
