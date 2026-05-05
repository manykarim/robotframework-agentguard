"""Shared subprocess helpers for CLI-backed drivers (ADR-009).

Keeps each per-CLI driver under the 300-LoC ceiling by hosting the common
``Popen + timeout + stdout/stderr capture`` plumbing in one place.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from AgentGuard.coding_agent.drivers.exceptions import DriverTimeout


@dataclass(slots=True)
class _RunOutcome:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float


def cli_present(binary: str) -> bool:
    """``shutil.which`` wrapper — returns False if ``binary`` is empty too."""
    if not binary:
        return False
    return shutil.which(binary) is not None


def run_cli(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None,
    timeout_seconds: int,
    stdin_text: str | None = None,
) -> _RunOutcome:
    """Run a CLI command and capture stdout/stderr, normalising timeouts.

    Inherits the parent process environment unless ``env`` is supplied; in
    that case the parent ``os.environ`` is shallow-merged with the override.
    """
    full_env = os.environ.copy()
    if env:
        full_env.update(env)

    start = time.perf_counter()
    try:
        proc = subprocess.run(  # noqa: S603 — argv is constructed by the caller, not user input
            argv,
            cwd=str(cwd),
            env=full_env,
            input=stdin_text,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise DriverTimeout(f"{argv[0]} exceeded {timeout_seconds}s timeout") from exc

    duration_ms = (time.perf_counter() - start) * 1000.0
    return _RunOutcome(
        exit_code=int(proc.returncode),
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
        duration_ms=duration_ms,
    )


__all__ = ["cli_present", "run_cli", "_RunOutcome"]
