"""Backend factory — name → ready-to-call :class:`SandboxBackend` instance.

The dispatcher in ``security/sandbox.py`` calls :func:`get_backend` with
``policy.backend``; if the backend cannot run on the current host we
raise :class:`SandboxUnavailable` so callers can fall back or fail closed.
"""

from __future__ import annotations

from AgentGuard.security.sandbox_backends.base import SandboxBackend
from AgentGuard.security.sandbox_backends.docker_backend import DockerBackend
from AgentGuard.security.sandbox_backends.k8s_backend import K8sBackend
from AgentGuard.security.sandbox_backends.process_backend import ProcessBackend
from AgentGuard.security.sandbox_backends.proxmox_backend import ProxmoxBackend
from AgentGuard.security.types import SandboxUnavailable

__all__ = ["BACKENDS", "get_backend"]


BACKENDS: dict[str, type[SandboxBackend]] = {
    "docker": DockerBackend,
    "k8s": K8sBackend,
    "proxmox": ProxmoxBackend,
    "process": ProcessBackend,
}


def get_backend(name: str) -> SandboxBackend:
    """Instantiate the named backend; raise ``SandboxUnavailable`` if unusable."""
    cls = BACKENDS.get(name)
    if cls is None:
        raise SandboxUnavailable(f"Unknown sandbox backend {name!r}; known: {sorted(BACKENDS.keys())}")
    backend = cls()
    if not backend.is_available():
        raise SandboxUnavailable(f"Sandbox backend {name!r} is not available on this host.")
    return backend
