"""Integration test: run a real container in the docker sandbox backend.

Skipped cleanly when the Docker daemon is unavailable — meant to run on
developer machines and in CI jobs that have docker-in-docker.

Note on hardening: ``cap_drop=ALL`` + ``no-new-privileges`` makes even
``/bin/echo`` fail in some images (setuid-bound binaries). We use
``python:3.12-alpine`` (the backend default) and call python directly,
which doesn't rely on capabilities.
"""

from __future__ import annotations

import pytest

# `docker` marker is registered in tests/conftest.py until foundation lands it
# centrally in pyproject.toml.
pytestmark = pytest.mark.docker


def _docker_available() -> bool:
    try:
        import docker  # type: ignore[import-untyped]
    except ImportError:
        return False
    try:
        client = docker.from_env()
        return bool(client.ping())
    except Exception:  # noqa: BLE001
        return False


if not _docker_available():
    pytest.skip("Docker daemon unavailable", allow_module_level=True)


from AgentGuard.security.sandbox import SandboxPolicy  # noqa: E402
from AgentGuard.security.sandbox_backends.docker_backend import DockerBackend  # noqa: E402
from AgentGuard.security.sandbox_backends.registry import get_backend  # noqa: E402
from AgentGuard.security.types import SandboxUnavailable  # noqa: E402


@pytest.fixture
def docker_backend() -> DockerBackend:
    backend = DockerBackend()
    if not backend.is_available():
        pytest.skip("Docker not available")
    return backend


def _maybe_skip_capdrop_unsupported(stderr: str) -> None:
    """Skip when the host kernel + image combination refuses exec under cap-drop=ALL.

    On some Docker runtimes (especially user-namespace remapped or rootless),
    dropping ALL caps + ``no-new-privileges`` makes even unprivileged exec
    return ``operation not permitted``. That's the *backend's* policy
    working as documented; the integration test merely asserts the wire
    behaviour when the runtime can support it.
    """
    if "operation not permitted" in stderr:
        pytest.skip(
            "host kernel/runtime refuses exec under cap-drop=ALL "
            "(this is the documented hardened posture)"
        )


def test_docker_backend_echo_hello(docker_backend: DockerBackend) -> None:
    """Run a tiny python script under the hardened defaults."""
    policy = SandboxPolicy(allow_code_execution=True)
    result = docker_backend.run(
        policy,
        ["python", "-c", "print('hello sandbox')"],
    )
    _maybe_skip_capdrop_unsupported(result.stderr)
    assert result.exit_code == 0, f"stderr: {result.stderr}"
    assert "hello sandbox" in result.stdout
    assert result.backend == "docker"


def test_docker_backend_blocks_when_policy_disallows(
    docker_backend: DockerBackend,
) -> None:
    policy = SandboxPolicy(allow_code_execution=False)
    with pytest.raises(SandboxUnavailable):
        docker_backend.run(policy, ["python", "-c", "pass"])


def test_docker_backend_via_registry() -> None:
    backend = get_backend("docker")
    assert backend.name == "docker"


def test_docker_backend_nonzero_exit(docker_backend: DockerBackend) -> None:
    policy = SandboxPolicy(allow_code_execution=True)
    result = docker_backend.run(
        policy, ["python", "-c", "import sys; sys.exit(7)"]
    )
    _maybe_skip_capdrop_unsupported(result.stderr)
    assert result.exit_code == 7

