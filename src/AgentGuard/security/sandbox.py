"""Sandbox policy + backend probes (Phase 1: probe + policy only).

Real backend execution lands in Phase 2 — this module exists so callers
can declare their *intended* posture, and so ``Sandbox Should Be Available``
can fail closed when the requested backend is missing.

Defaults derive from ``policy-defaults.md`` §2 and ``sandbox-spec.md``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from AgentGuard.security.sandbox_backends.base import SandboxResult
from AgentGuard.security.sandbox_backends.registry import get_backend
from AgentGuard.security.types import SandboxUnavailable

Backend = Literal["docker", "k8s", "proxmox", "process"]

_BACKENDS: tuple[Backend, ...] = ("docker", "k8s", "proxmox", "process")


@dataclass(slots=True, frozen=True)
class SandboxPolicy:
    """Declarative description of how a sandbox *should* run code.

    Phase 1 only: nothing here actually launches the sandbox; this is the
    contract the Phase-2 executor will receive.
    """

    backend: Backend = "docker"
    allow_code_execution: bool = False
    network_allowed: bool = False
    mounts: tuple[Path, ...] = field(default_factory=tuple)
    cpu_limit_seconds: int = 300
    mem_limit_mb: int = 512
    pid_limit: int = 256
    drop_caps: bool = True
    read_only_root: bool = True
    no_docker_socket: bool = True
    no_new_privileges: bool = True
    image_digest: str | None = None

    def validate(self) -> None:
        """Raise ``SandboxUnavailable`` if the policy is internally inconsistent."""
        if self.backend not in _BACKENDS:
            raise SandboxUnavailable(f"Unknown sandbox backend {self.backend!r}.")
        if self.backend == "process" and self.allow_code_execution:
            # process backend is dev-only and never the default — but if used
            # for code execution we surface the loud warning the spec mandates.
            import warnings

            warnings.warn(
                "SANDBOX=process — UNSAFE FOR UNTRUSTED CODE",
                category=UserWarning,
                stacklevel=2,
            )
        if self.cpu_limit_seconds <= 0 or self.mem_limit_mb <= 0:
            raise SandboxUnavailable("CPU and memory limits must be positive.")
        if self.pid_limit <= 0:
            raise SandboxUnavailable("PID limit must be positive.")


def policy_from_env() -> SandboxPolicy:
    """Build a ``SandboxPolicy`` from ``AGENTGUARD_SANDBOX_*`` env vars."""

    def _bool(name: str, default: bool) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    def _int(name: str, default: int) -> int:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            return int(raw)
        except ValueError:
            return default

    backend_raw = os.getenv("AGENTGUARD_SANDBOX_BACKEND", "docker").strip().lower()
    backend: Backend = backend_raw if backend_raw in _BACKENDS else "docker"

    mounts_raw = os.getenv("AGENTGUARD_SANDBOX_MOUNTS", "")
    mounts: tuple[Path, ...] = tuple(Path(p).expanduser() for p in mounts_raw.split(":") if p.strip())

    policy = SandboxPolicy(
        backend=backend,
        allow_code_execution=_bool("AGENTGUARD_SANDBOX_ALLOW_CODE_EXECUTION", False),
        network_allowed=_bool("AGENTGUARD_SANDBOX_NETWORK", False),
        mounts=mounts,
        cpu_limit_seconds=_int("AGENTGUARD_SANDBOX_CPU_SECONDS", 300),
        mem_limit_mb=_int("AGENTGUARD_SANDBOX_MEM_MB", 512),
        pid_limit=_int("AGENTGUARD_SANDBOX_PID_LIMIT", 256),
        image_digest=os.getenv("AGENTGUARD_SANDBOX_IMAGE_DIGEST"),
    )
    policy.validate()
    return policy


def probe_backend(backend: Backend) -> dict[str, str]:
    """Confirm the requested backend is callable on this host.

    Returns a small ``{"backend", "version"}`` dict on success or raises
    ``SandboxUnavailable`` if the backend cannot be located or doesn't
    respond within a short timeout. Phase 1 implements ``docker`` against
    the ``docker version`` command; ``k8s`` / ``proxmox`` are stubbed to
    raise ``SandboxUnavailable`` until Phase 2.
    """
    if backend not in _BACKENDS:
        raise SandboxUnavailable(f"Unknown sandbox backend {backend!r}.")

    if backend == "docker":
        return _probe_docker()
    if backend == "process":
        return {"backend": "process", "version": "host", "warning": "UNSAFE FOR UNTRUSTED CODE"}
    raise SandboxUnavailable(f"Sandbox backend {backend!r} is declared but not implemented in Phase 1.")


def _probe_docker() -> dict[str, str]:
    binary = shutil.which("docker")
    if binary is None:
        raise SandboxUnavailable("`docker` CLI not found on PATH.")
    try:
        result = subprocess.run(  # noqa: S603 — we resolved the binary above
            [binary, "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise SandboxUnavailable(f"docker probe failed: {exc}") from exc
    if result.returncode != 0:
        raise SandboxUnavailable(f"docker probe returned exit {result.returncode}: {result.stderr.strip()[:200]}")
    version = result.stdout.strip() or "unknown"
    return {"backend": "docker", "version": version}


# ----------------------------------------------------------------------
# Phase-2 dispatcher (real execution)
# ----------------------------------------------------------------------


def run_in_sandbox(
    policy: SandboxPolicy,
    command: list[str] | str,
    *,
    image: str | None = None,
    stdin: str | None = None,
    env: dict[str, str] | None = None,
    mounts: list[tuple[str, str]] | None = None,
    timeout_seconds: int | None = None,
) -> SandboxResult:
    """Dispatch ``command`` to the backend named by ``policy.backend``.

    Default-deny: every backend re-checks ``policy.allow_code_execution``
    before launching anything, and ``get_backend`` raises ``SandboxUnavailable``
    if the requested backend is not usable on this host.
    """
    policy.validate()
    backend = get_backend(policy.backend)
    return backend.run(
        policy,
        command,
        image=image,
        stdin=stdin,
        env=env,
        mounts=mounts,
        timeout_seconds=timeout_seconds,
    )
