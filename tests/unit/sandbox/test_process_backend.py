"""Unit tests for ``AgentGuard.security.sandbox_backends.process_backend``.

The process backend runs commands directly on the host — there's no isolation
to test, but we cover the policy gate, command coercion, timeout handling,
and the loud-warning posture from sandbox-spec §2.
"""

from __future__ import annotations

import warnings

import pytest

from AgentGuard.security.sandbox import SandboxPolicy
from AgentGuard.security.sandbox_backends.process_backend import ProcessBackend
from AgentGuard.security.types import SandboxUnavailable


def test_process_backend_is_available_always() -> None:
    assert ProcessBackend().is_available() is True


def test_process_backend_name() -> None:
    assert ProcessBackend().name == "process"


def test_process_backend_rejects_non_process_policy() -> None:
    backend = ProcessBackend()
    policy = SandboxPolicy(backend="docker", allow_code_execution=True)
    with pytest.raises(SandboxUnavailable, match="can only be used"):
        backend.run(policy, ["echo", "hi"])


def test_process_backend_rejects_disabled_code_execution() -> None:
    backend = ProcessBackend()
    policy = SandboxPolicy(backend="process", allow_code_execution=False)
    with pytest.raises(SandboxUnavailable, match="code execution disabled"):
        backend.run(policy, ["echo", "hi"])


def test_process_backend_runs_command() -> None:
    backend = ProcessBackend()
    # Allow code execution; suppress the documented UserWarning.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        policy = SandboxPolicy(backend="process", allow_code_execution=True)
    result = backend.run(policy, ["echo", "hello world"])
    assert result.exit_code == 0
    assert "hello world" in result.stdout
    assert result.backend == "process"
    assert result.duration_ms > 0


def test_process_backend_runs_string_command() -> None:
    backend = ProcessBackend()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        policy = SandboxPolicy(backend="process", allow_code_execution=True)
    result = backend.run(policy, "echo via_string")
    assert "via_string" in result.stdout


def test_process_backend_empty_command_raises() -> None:
    backend = ProcessBackend()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        policy = SandboxPolicy(backend="process", allow_code_execution=True)
    with pytest.raises(SandboxUnavailable, match="non-empty"):
        backend.run(policy, [])


def test_process_backend_timeout_raises() -> None:
    backend = ProcessBackend()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        policy = SandboxPolicy(backend="process", allow_code_execution=True)
    with pytest.raises(SandboxUnavailable, match="timed out"):
        backend.run(policy, ["sleep", "5"], timeout_seconds=1)


def test_process_backend_stdin_passed_through() -> None:
    backend = ProcessBackend()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        policy = SandboxPolicy(backend="process", allow_code_execution=True)
    result = backend.run(policy, ["cat"], stdin="hello stdin")
    assert "hello stdin" in result.stdout


def test_process_backend_env_passed_through() -> None:
    backend = ProcessBackend()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        policy = SandboxPolicy(backend="process", allow_code_execution=True)
    # `env` keeps PATH default behaviour fragile; use a custom env containing PATH
    result = backend.run(
        policy,
        ["sh", "-c", "echo $MYVAR"],
        env={"MYVAR": "myvalue", "PATH": "/usr/bin:/bin"},
    )
    assert "myvalue" in result.stdout


def test_process_backend_nonzero_exit_propagates() -> None:
    backend = ProcessBackend()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        policy = SandboxPolicy(backend="process", allow_code_execution=True)
    result = backend.run(policy, ["sh", "-c", "exit 7"])
    assert result.exit_code == 7


def test_process_backend_truncates_huge_output() -> None:
    """If stdout exceeds max_output_bytes, ``truncated`` is True."""
    backend = ProcessBackend(max_output_bytes=10)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        policy = SandboxPolicy(backend="process", allow_code_execution=True)
    result = backend.run(policy, ["sh", "-c", "echo aaaaaaaaaaaaaaaaaaaaaa"])
    assert result.truncated is True


def test_process_backend_unsafe_warning_emitted() -> None:
    """SandboxPolicy.validate emits the loud UserWarning (sandbox-spec §2)."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        SandboxPolicy(backend="process", allow_code_execution=True).validate()
    msgs = [str(w.message) for w in caught if issubclass(w.category, UserWarning)]
    assert any("UNSAFE" in m for m in msgs)
