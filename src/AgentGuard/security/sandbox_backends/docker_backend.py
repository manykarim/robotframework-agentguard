"""Docker backend — primary production sandbox per ADR-013 / sandbox-spec §2.

Enforces the secure-by-default posture from ``docs/security/sandbox-spec.md``:

* ``--network=none`` unless ``policy.network_allowed`` is ``True``
* read-only root fs with a tmpfs at ``/tmp``
* drop ALL capabilities; ``no-new-privileges``
* non-root UID (``1000:1000`` by default)
* CPU + memory + PID hard caps
* host docker-socket / ``/proc`` / ``/sys`` mounts are always rejected
* ``policy.allow_code_execution`` is the gate — default-deny
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from AgentGuard.security.sandbox_backends.base import (
    DEFAULT_MAX_OUTPUT_BYTES,
    SandboxResult,
)
from AgentGuard.security.types import SandboxUnavailable

if TYPE_CHECKING:
    from AgentGuard.security.sandbox import SandboxPolicy

__all__ = ["DockerBackend", "DEFAULT_IMAGE", "FORBIDDEN_HOST_PATHS"]


DEFAULT_IMAGE: str = "python:3.12-alpine"
"""Conservative default — small (<60 MiB) and present in most CI caches."""

DEFAULT_USER: str = "1000:1000"

FORBIDDEN_HOST_PATHS: frozenset[str] = frozenset(
    {
        "/var/run/docker.sock",
        "/run/docker.sock",
        "/proc",
        "/proc/1/root",
        "/sys",
        "/dev",
        "/",
    }
)
"""Host paths that may NEVER be bind-mounted into the sandbox (sandbox-spec §1)."""


class DockerBackend:
    """Real Docker exec backend (production-grade isolation)."""

    name: str = "docker"

    def __init__(self, max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES) -> None:
        self._max_output_bytes = max_output_bytes
        self._client: Any | None = None  # docker.DockerClient — lazy

    # ------------------------------------------------------------------
    # availability
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        try:
            self._get_client().ping()
            return True
        except Exception:  # noqa: BLE001 — any failure means "not available"
            return False

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import docker
        except ImportError as exc:  # pragma: no cover — docker is a prod dep
            raise SandboxUnavailable("docker SDK not installed") from exc
        try:
            self._client = docker.from_env()
        except Exception as exc:  # noqa: BLE001
            raise SandboxUnavailable(f"docker daemon unreachable: {exc}") from exc
        return self._client

    # ------------------------------------------------------------------
    # run
    # ------------------------------------------------------------------

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
        if not policy.allow_code_execution:
            raise SandboxUnavailable(
                "code execution disabled by policy "
                "(set allow_code_execution=True or AGENTGUARD_SANDBOX_ALLOW_CODE_EXECUTION=true)"
            )

        validated_mounts = _validate_mounts(mounts or [], policy)
        client = self._get_client()
        chosen_image = image or DEFAULT_IMAGE
        timeout = timeout_seconds or policy.cpu_limit_seconds

        run_kwargs = self._build_run_kwargs(
            policy=policy,
            command=command,
            stdin=stdin,
            env=env,
            mounts=validated_mounts,
        )

        try:
            import docker
            from docker.errors import (
                APIError,
                ContainerError,
                ImageNotFound,
            )
        except ImportError as exc:  # pragma: no cover
            raise SandboxUnavailable("docker SDK not installed") from exc

        container: Any | None = None
        start = time.perf_counter()
        try:
            try:
                container = client.containers.run(
                    chosen_image,
                    command,
                    detach=True,
                    **run_kwargs,
                )
            except ImageNotFound as exc:
                raise SandboxUnavailable(
                    f"image not available: {chosen_image}: {exc.explanation}"
                ) from exc
            except (APIError, ContainerError, docker.errors.DockerException) as exc:
                raise SandboxUnavailable(f"docker run failed: {exc}") from exc

            try:
                wait_result = container.wait(timeout=timeout)
            except Exception as exc:  # noqa: BLE001 — includes ReadTimeout
                # Best-effort kill on timeout
                try:
                    container.kill()
                except Exception:  # noqa: BLE001
                    pass
                raise SandboxUnavailable(
                    f"sandbox exec timed out after {timeout}s: {exc}"
                ) from exc

            exit_code = int(wait_result.get("StatusCode", -1))
            stdout_bytes = container.logs(stdout=True, stderr=False) or b""
            stderr_bytes = container.logs(stdout=False, stderr=True) or b""
            container_id = container.id

            stdout, stderr, truncated = _truncate(
                stdout_bytes, stderr_bytes, self._max_output_bytes
            )
            duration_ms = (time.perf_counter() - start) * 1000.0
            return SandboxResult(
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration_ms=duration_ms,
                backend=self.name,
                image=chosen_image,
                container_id=container_id,
                truncated=truncated,
            )
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except Exception:  # noqa: BLE001 — already gone is fine
                    pass

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _build_run_kwargs(
        self,
        *,
        policy: SandboxPolicy,
        command: list[str] | str,  # noqa: ARG002 — accepted for future stdin wiring
        stdin: str | None,  # noqa: ARG002 — interactive stdin needs attach; future work
        env: dict[str, str] | None,
        mounts: list[tuple[str, str]],
    ) -> dict[str, Any]:
        # Bind mounts: list of "src:dst:ro" / "src:dst" strings — Docker SDK accepts both
        volumes: dict[str, dict[str, str]] = {}
        for src, dst in mounts:
            volumes[src] = {"bind": dst, "mode": "ro"}

        # CPU caps: cpu_limit_seconds is a *wall-clock* budget; we map it to a quota
        # equal to one full CPU per period (so a 300s budget => 100% of one core for 300s).
        # Hard limit on memory + pids comes straight from policy.
        kwargs: dict[str, Any] = {
            "network_mode": "bridge" if policy.network_allowed else "none",
            "read_only": policy.read_only_root,
            "tmpfs": {"/tmp": "size=64m,mode=1777"},  # noqa: S108 — guest path inside container, not host
            "cap_drop": ["ALL"] if policy.drop_caps else [],
            "security_opt": (
                ["no-new-privileges:true"] if policy.no_new_privileges else []
            ),
            "user": DEFAULT_USER,
            "mem_limit": f"{policy.mem_limit_mb}m",
            "pids_limit": policy.pid_limit,
            "cpu_period": 100_000,
            "cpu_quota": 100_000,  # one full CPU
            "environment": dict(env) if env else None,
            "volumes": volumes or None,
            "labels": {
                "agentguard.sandbox": "1",
                "agentguard.backend": self.name,
            },
            # Don't auto_remove — we remove explicitly after collecting logs
            "auto_remove": False,
        }
        return kwargs


# ----------------------------------------------------------------------
# free helpers (kept module-level so unit tests can hit them directly)
# ----------------------------------------------------------------------


def _validate_mounts(
    mounts: list[tuple[str, str]],
    policy: SandboxPolicy,
) -> list[tuple[str, str]]:
    """Reject docker-socket / /proc / /sys; enforce ``policy.mounts`` allowlist.

    The docker socket is *unconditionally* refused regardless of
    ``policy.no_docker_socket`` — there is no legitimate test reason to mount
    it (CVE-2024-21626 / Leaky Vessels).
    """
    out: list[tuple[str, str]] = []
    allowlist: set[str] = {str(p.resolve()) for p in policy.mounts}
    for raw_src, dst in mounts:
        try:
            src_resolved = str(Path(raw_src).expanduser().resolve())
        except OSError as exc:
            raise SandboxUnavailable(f"invalid mount source {raw_src!r}: {exc}") from exc

        if raw_src in FORBIDDEN_HOST_PATHS or src_resolved in FORBIDDEN_HOST_PATHS:
            raise SandboxUnavailable(
                f"refusing to mount forbidden host path {raw_src!r} into sandbox"
            )
        # Reject anything that resolves under /proc or /sys
        if any(src_resolved == p or src_resolved.startswith(p + "/") for p in ("/proc", "/sys")):
            raise SandboxUnavailable(
                f"refusing to mount kernel pseudo-fs {raw_src!r} into sandbox"
            )
        # Destination guards: refuse mounting over the docker socket path or kernel fs
        if dst in FORBIDDEN_HOST_PATHS:
            raise SandboxUnavailable(
                f"refusing mount destination {dst!r} (would shadow protected path)"
            )
        # Allowlist gate (if the policy declares any mounts, restrict to them)
        if allowlist and src_resolved not in allowlist:
            raise SandboxUnavailable(
                f"mount {raw_src!r} not in policy allowlist "
                f"(allowed: {sorted(allowlist) or '<none>'})"
            )
        out.append((src_resolved, dst))
    return out


def _truncate(
    stdout_bytes: bytes,
    stderr_bytes: bytes,
    max_bytes: int,
) -> tuple[str, str, bool]:
    """Decode + truncate stdout/stderr; flag truncation."""
    truncated = False
    out_b = stdout_bytes
    err_b = stderr_bytes
    if len(out_b) > max_bytes:
        out_b = out_b[:max_bytes]
        truncated = True
    if len(err_b) > max_bytes:
        err_b = err_b[:max_bytes]
        truncated = True
    return (
        out_b.decode("utf-8", errors="replace"),
        err_b.decode("utf-8", errors="replace"),
        truncated,
    )
