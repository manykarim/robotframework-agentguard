"""Backend Protocol + result type for the Phase-2 sandbox executor.

Every concrete backend in this package (``docker_backend``, ``k8s_backend``,
``proxmox_backend``, ``process_backend``) implements
:class:`SandboxBackend` so the dispatcher in ``security/sandbox.py`` can
call them uniformly. The contract is intentionally minimal so the same
shape works for in-container exec (Docker), pod-per-sample (K8s), and
host subprocess (process / dev-only).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from AgentGuard.security.sandbox import SandboxPolicy

__all__ = ["SandboxResult", "SandboxBackend", "DEFAULT_MAX_OUTPUT_BYTES"]


DEFAULT_MAX_OUTPUT_BYTES: int = 1 * 1024 * 1024  # 1 MiB per stream
"""Per-stream truncation budget. Configurable via the backend ``max_output_bytes`` kwarg."""


@dataclass(slots=True, frozen=True)
class SandboxResult:
    """Outcome of a single sandbox ``run`` invocation.

    Mirrors the minimal Inspect AI ``ExecResult`` shape (research §4.4)
    plus a few audit fields we need for the JSONL trail (sandbox-spec §5).
    """

    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    backend: str
    image: str | None = None
    container_id: str | None = None
    truncated: bool = False  # set True if stdout/stderr exceeded max_output_bytes


@runtime_checkable
class SandboxBackend(Protocol):
    """Pluggable sandbox executor.

    Implementations MUST be safe to instantiate even when the underlying
    runtime is missing — callers gate on :meth:`is_available` (or the
    registry's ``get_backend`` which does the gating for them).
    """

    name: str

    def is_available(self) -> bool:
        """Return ``True`` iff this backend can actually execute on the host."""

    def run(
        self,
        policy: SandboxPolicy,
        command: list[str] | str,
        *,
        image: str | None = None,
        stdin: str | None = None,
        env: dict[str, str] | None = None,
        mounts: list[tuple[str, str]] | None = None,
        timeout_seconds: int | None = None,
    ) -> SandboxResult:
        """Execute ``command`` under ``policy`` and return a :class:`SandboxResult`."""
