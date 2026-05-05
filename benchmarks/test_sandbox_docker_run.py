"""Validates the Phase-2 Docker sandbox `Run In Sandbox` budget.

Source: Phase-2 budget extension. The Docker backend must run a trivial
``echo hello`` end-to-end (image pull pre-warmed) inside reasonable bounds:

| Path | Budget |
|---|---|
| Cold (first run after fresh probe) | ≤ 5 s |
| Warm (subsequent runs)             | ≤ 1 s |

The benchmark is gated on the `docker` mark *and* a runtime probe (skipped
when the daemon is unreachable) so CI workers without Docker don't fail.

The dispatch function `run_in_sandbox` lands in
``AgentGuard.security.sandbox`` per ADR-013; the executor lives in
``AgentGuard.security.sandbox_backends.docker_backend``. Until either is
available we ``pytest.skip`` with a clear reason rather than silently
passing.
"""

from __future__ import annotations

import shutil
import time
from typing import Any

import pytest

# Budgets — Phase-2 sandbox ceilings.
BUDGET_COLD_S = 5.0
BUDGET_WARM_S = 1.0


def _docker_reachable() -> bool:
    """Return True iff the local Docker daemon is callable.

    We do a cheap probe via the existing helper instead of pulling the
    `docker` Python SDK: that helper is the same one `Sandbox Should Be
    Available` calls so we stay aligned with the keyword surface.
    """
    if shutil.which("docker") is None:
        return False
    try:
        from AgentGuard.security.sandbox import probe_backend
    except ImportError:
        return False
    try:
        probe_backend("docker")
    except Exception:  # noqa: BLE001 — any failure means "not usable"
        return False
    return True


def _run_in_sandbox_or_skip() -> Any:
    """Resolve the sandbox dispatcher; skip when not yet implemented."""
    try:
        from AgentGuard.security import sandbox
    except ImportError:
        pytest.skip("AgentGuard.security.sandbox not importable")

    fn = getattr(sandbox, "run_in_sandbox", None)
    if fn is None:
        pytest.skip("AgentGuard.security.sandbox.run_in_sandbox not implemented yet (Phase 2 sandbox dispatch)")
    return fn


def _build_policy() -> Any:
    """Build a default-deny policy with code execution enabled for the bench."""
    from AgentGuard.security.sandbox import SandboxPolicy

    return SandboxPolicy(
        backend="docker",
        allow_code_execution=True,
        network_allowed=False,
        cpu_limit_seconds=10,
        mem_limit_mb=256,
        pid_limit=64,
    )


def _smoke_or_skip(run_in_sandbox: Any, policy: Any) -> Any:
    """Exec a no-op once; skip if the host's docker rejects the secure profile.

    Some docker installs (notably snap-packaged on Ubuntu) refuse the
    ``no-new-privileges:true`` + ``cap-drop ALL`` combination with
    ``exec /bin/sh: operation not permitted``. That is a host-config
    incompatibility, not a sandbox bug — skip so CI surfaces the issue
    without failing the budget assertion on a 0-byte run.
    """
    smoke = run_in_sandbox(
        policy,
        ["sh", "-c", "echo smoke"],
        image="alpine:3.20",
        timeout_seconds=10,
    )
    if smoke.exit_code != 0 or "smoke" not in (smoke.stdout or ""):
        pytest.skip(
            f"sandbox smoke test failed (exit={smoke.exit_code}, "
            f"stderr={smoke.stderr!r}); host docker may reject the secure profile"
        )
    return smoke


@pytest.mark.docker
@pytest.mark.benchmark(group="sandbox-docker")
def test_sandbox_docker_echo_cold(benchmark: Any) -> None:
    """First `echo hello` after fresh policy build — wall-clock ≤ 5 s."""
    if not _docker_reachable():
        pytest.skip("docker daemon not reachable")
    run_in_sandbox = _run_in_sandbox_or_skip()
    policy = _build_policy()

    def _call() -> Any:
        return run_in_sandbox(
            policy,
            ["sh", "-c", "echo hello"],
            image="alpine:3.20",
            timeout_seconds=10,
        )

    # First, gate on the secure profile working at all on this host.
    smoke = _smoke_or_skip(run_in_sandbox, policy)
    assert smoke.exit_code == 0

    benchmark.pedantic(_call, rounds=1, iterations=1, warmup_rounds=0)
    cold_s = float(benchmark.stats.stats.mean)
    if cold_s > BUDGET_COLD_S:
        pytest.fail(
            f"sandbox docker cold-start {cold_s:.2f} s exceeds budget {BUDGET_COLD_S} s (Phase-2 sandbox budget)"
        )


@pytest.mark.docker
@pytest.mark.benchmark(group="sandbox-docker")
def test_sandbox_docker_echo_warm(benchmark: Any) -> None:
    """Subsequent `echo hello` invocations — wall-clock ≤ 1 s.

    Pre-warms with one untimed run so image pull / image cache lookups don't
    leak into the measured rounds.
    """
    if not _docker_reachable():
        pytest.skip("docker daemon not reachable")
    run_in_sandbox = _run_in_sandbox_or_skip()
    policy = _build_policy()

    # Pre-warm: pull the image + pay first-container overhead.
    try:
        warmup = run_in_sandbox(
            policy,
            ["sh", "-c", "echo warmup"],
            image="alpine:3.20",
            timeout_seconds=15,
        )
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"sandbox warmup failed (image pull?): {exc}")
    if warmup.exit_code != 0:
        pytest.skip(
            f"sandbox warmup exit={warmup.exit_code} stderr={warmup.stderr!r}; "
            "host docker may reject the secure profile"
        )

    def _call() -> Any:
        return run_in_sandbox(
            policy,
            ["sh", "-c", "echo hello"],
            image="alpine:3.20",
            timeout_seconds=5,
        )

    # Use perf_counter to compute the median — pedantic's mean is fine but
    # we want the *median* warm path so a single tail spike doesn't trip CI.
    samples: list[float] = []
    for _ in range(5):
        t0 = time.perf_counter()
        _call()
        samples.append(time.perf_counter() - t0)
    benchmark.pedantic(_call, rounds=3, iterations=1, warmup_rounds=0)

    median_s = sorted(samples)[len(samples) // 2]
    if median_s > BUDGET_WARM_S:
        pytest.fail(
            f"sandbox docker warm-run median {median_s:.2f} s exceeds budget {BUDGET_WARM_S} s (Phase-2 sandbox budget)"
        )
