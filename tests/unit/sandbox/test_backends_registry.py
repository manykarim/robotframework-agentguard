"""Unit tests for ``AgentGuard.security.sandbox_backends.registry`` + base."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from AgentGuard.security.sandbox_backends import registry
from AgentGuard.security.sandbox_backends.base import (
    DEFAULT_MAX_OUTPUT_BYTES,
    SandboxBackend,
    SandboxResult,
)
from AgentGuard.security.types import SandboxUnavailable


def test_registry_contains_four_backends() -> None:
    assert set(registry.BACKENDS.keys()) == {"docker", "k8s", "proxmox", "process"}


def test_get_backend_unknown_raises() -> None:
    with pytest.raises(SandboxUnavailable, match="Unknown sandbox backend"):
        registry.get_backend("not-real")


def test_get_backend_process_always_available() -> None:
    backend = registry.get_backend("process")
    assert backend.name == "process"
    assert backend.is_available() is True


def test_get_backend_docker_unavailable_raises() -> None:
    """When the docker daemon is down, get_backend should raise."""
    from AgentGuard.security.sandbox_backends.docker_backend import DockerBackend

    with patch.object(DockerBackend, "is_available", return_value=False):
        with pytest.raises(SandboxUnavailable, match="not available"):
            registry.get_backend("docker")


def test_default_max_output_bytes_constant() -> None:
    assert DEFAULT_MAX_OUTPUT_BYTES == 1 * 1024 * 1024


def test_sandbox_result_dataclass() -> None:
    res = SandboxResult(exit_code=0, stdout="ok", stderr="", duration_ms=1.0, backend="process")
    assert res.exit_code == 0
    assert res.image is None
    assert res.truncated is False


def test_protocol_runtime_check_with_process() -> None:
    from AgentGuard.security.sandbox_backends.process_backend import ProcessBackend

    backend = ProcessBackend()
    # SandboxBackend is runtime_checkable
    assert isinstance(backend, SandboxBackend)
