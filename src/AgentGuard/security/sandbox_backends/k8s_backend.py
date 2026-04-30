"""Kubernetes pod-per-sample backend — Phase 3 stub.

Will implement the sandbox-spec §2 K8s row (NetworkPolicy egress allowlist,
``readOnlyRootFilesystem``, ``runAsNonRoot``, ``capabilities.drop=[ALL]``,
``seccompProfile: RuntimeDefault``) using the official ``kubernetes`` SDK.
"""

from __future__ import annotations

from importlib.util import find_spec
from typing import TYPE_CHECKING

from AgentGuard.security.sandbox_backends.base import SandboxResult

if TYPE_CHECKING:
    from AgentGuard.security.sandbox import SandboxPolicy

__all__ = ["K8sBackend"]


class K8sBackend:
    """Pod-per-sample executor (not yet implemented)."""

    name: str = "k8s"

    def is_available(self) -> bool:
        # We require the kubernetes SDK; even then a real implementation
        # would also probe API server reachability. Return False until Phase 3.
        return find_spec("kubernetes") is not None and False

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
        raise NotImplementedError(
            "Phase 3 - K8s pod-per-sample backend not yet implemented"
        )
