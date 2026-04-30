"""Proxmox (LXC / VM) backend — Phase 3 stub.

Will implement the sandbox-spec §2 Proxmox row (unprivileged LXC, AppArmor
``lxc-container-default-restricted``, ``pve-firewall`` egress allowlist)
using the ``proxmoxer`` SDK.
"""

from __future__ import annotations

from importlib.util import find_spec
from typing import TYPE_CHECKING

from AgentGuard.security.sandbox_backends.base import SandboxResult

if TYPE_CHECKING:
    from AgentGuard.security.sandbox import SandboxPolicy

__all__ = ["ProxmoxBackend"]


class ProxmoxBackend:
    """Proxmox LXC/VM executor (not yet implemented)."""

    name: str = "proxmox"

    def is_available(self) -> bool:
        return find_spec("proxmoxer") is not None and False

    def run(
        self,
        policy: SandboxPolicy,  # noqa: ARG002
        command: list[str] | str,  # noqa: ARG002
        *,
        image: str | None = None,  # noqa: ARG002
        stdin: str | None = None,  # noqa: ARG002
        env: dict[str, str] | None = None,  # noqa: ARG002
        mounts: list[tuple[str, str]] | None = None,  # noqa: ARG002
        timeout_seconds: int | None = None,  # noqa: ARG002
    ) -> SandboxResult:
        raise NotImplementedError("Phase 3 - Proxmox LXC/VM backend not yet implemented")
