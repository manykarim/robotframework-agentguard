"""Process backend — DEV-ONLY, INSECURE. Per sandbox-spec §2 row "Process".

Runs the command as a plain ``subprocess.run`` on the host. No isolation,
no caps drop, no fs read-only. Disabled in CI by default; only usable when:

* ``policy.backend == "process"`` AND
* ``policy.allow_code_execution is True``

The :class:`SandboxPolicy.validate` method already emits the loud
``UserWarning`` mandated by the spec when this combination is selected.
"""

from __future__ import annotations

import shlex
import subprocess
import time
from typing import TYPE_CHECKING

from AgentGuard.security.sandbox_backends.base import (
    DEFAULT_MAX_OUTPUT_BYTES,
    SandboxResult,
)
from AgentGuard.security.types import SandboxUnavailable

if TYPE_CHECKING:
    from AgentGuard.security.sandbox import SandboxPolicy

__all__ = ["ProcessBackend"]


class ProcessBackend:
    """Insecure host-subprocess executor — only for local dev / smoke tests."""

    name: str = "process"

    def __init__(self, max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES) -> None:
        self._max_output_bytes = max_output_bytes

    def is_available(self) -> bool:
        # subprocess is in stdlib — always available
        return True

    def run(
        self,
        policy: SandboxPolicy,
        command: list[str] | str,
        *,
        image: str | None = None,  # noqa: ARG002 — unused; here for protocol parity
        stdin: str | None = None,
        env: dict[str, str] | None = None,
        mounts: list[tuple[str, str]] | None = None,  # noqa: ARG002 — host already sees fs
        timeout_seconds: int | None = None,
    ) -> SandboxResult:
        if policy.backend != "process":
            raise SandboxUnavailable(
                "ProcessBackend can only be used with policy.backend='process'"
            )
        if not policy.allow_code_execution:
            raise SandboxUnavailable(
                "code execution disabled by policy "
                "(set allow_code_execution=True or AGENTGUARD_SANDBOX_ALLOW_CODE_EXECUTION=true)"
            )

        argv: list[str] = (
            shlex.split(command) if isinstance(command, str) else list(command)
        )
        if not argv:
            raise SandboxUnavailable("ProcessBackend requires a non-empty command")

        timeout = timeout_seconds or policy.cpu_limit_seconds
        start = time.perf_counter()
        try:
            completed = subprocess.run(  # noqa: S603 — caller-supplied argv is intentional
                argv,
                input=stdin,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SandboxUnavailable(
                f"process exec timed out after {timeout}s: {exc}"
            ) from exc
        except (OSError, ValueError) as exc:
            raise SandboxUnavailable(f"process exec failed: {exc}") from exc

        duration_ms = (time.perf_counter() - start) * 1000.0
        out = completed.stdout or ""
        err = completed.stderr or ""
        truncated = False
        if len(out.encode("utf-8")) > self._max_output_bytes:
            out = out.encode("utf-8")[: self._max_output_bytes].decode(
                "utf-8", errors="replace"
            )
            truncated = True
        if len(err.encode("utf-8")) > self._max_output_bytes:
            err = err.encode("utf-8")[: self._max_output_bytes].decode(
                "utf-8", errors="replace"
            )
            truncated = True

        return SandboxResult(
            exit_code=int(completed.returncode),
            stdout=out,
            stderr=err,
            duration_ms=duration_ms,
            backend=self.name,
            image=None,
            container_id=None,
            truncated=truncated,
        )
