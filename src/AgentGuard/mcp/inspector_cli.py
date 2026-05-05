"""Subprocess wrapper for `npx @modelcontextprotocol/inspector --cli`.

Per exp_02 (Phase 0):
- `inspector --cli --help` exits 0 and lists
  `--cli/--transport/--server-url/--header/--config/--server`.
- `--cli --method <method>` works (e.g. `--method tools/list`) but is
  *undocumented* in `--help`.
- We therefore pin a known-good Inspector range and document `--method` here.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

from AgentGuard.mcp.exceptions import MCPInspectorError

# We pin an inspector range that has the (undocumented) `--method` flag working.
# The Phase-0 experiment exercised the latest version available via npx; future
# users can override via `AGENTGUARD_INSPECTOR_PKG`.
INSPECTOR_PKG = os.environ.get("AGENTGUARD_INSPECTOR_PKG", "@modelcontextprotocol/inspector")

_NPX_AVAILABLE: bool | None = None  # process-level cache


def npx_available() -> bool:
    """True if `npx` is on PATH (cached for the lifetime of the process)."""
    global _NPX_AVAILABLE
    if _NPX_AVAILABLE is None:
        _NPX_AVAILABLE = shutil.which("npx") is not None
    return _NPX_AVAILABLE


def reset_npx_cache() -> None:
    """Test hook — re-probe `npx` on next call."""
    global _NPX_AVAILABLE
    _NPX_AVAILABLE = None


@dataclass(slots=True)
class InspectorResult:
    """Captured outcome of an Inspector CLI invocation."""

    returncode: int
    stdout: str
    stderr: str
    parsed: Any | None = None  # decoded JSON if stdout parsed cleanly

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def run(
    args: list[str],
    *,
    timeout: float = 60.0,
    extra_env: dict[str, str] | None = None,
) -> InspectorResult:
    """Run `npx -y <INSPECTOR_PKG> --cli <args>` and capture stdout/stderr.

    `args` should NOT include the leading `--cli` (added here) or the package spec.

    Raises:
        MCPInspectorError: if `npx` is missing or the subprocess times out.
    """
    if not npx_available():
        raise MCPInspectorError("`npx` not found on PATH — install Node.js to use the MCP Inspector keywords.")

    cmd = ["npx", "-y", INSPECTOR_PKG, "--cli", *args]
    env = {**os.environ, "CI": "1"}
    if extra_env:
        env.update(extra_env)

    try:
        proc = subprocess.run(  # noqa: S603 - cmd built from pinned constants + caller args
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise MCPInspectorError(f"Inspector CLI timed out after {timeout}s: {' '.join(cmd)}") from exc
    except FileNotFoundError as exc:  # pragma: no cover - guarded by npx_available()
        raise MCPInspectorError("`npx` not executable") from exc

    parsed: Any | None = None
    out = (proc.stdout or "").strip()
    if out and (out.startswith("{") or out.startswith("[")):
        try:
            parsed = json.loads(out)
        except json.JSONDecodeError:
            parsed = None
    return InspectorResult(
        returncode=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
        parsed=parsed,
    )


def list_tools(target: str, transport: str = "stdio") -> InspectorResult:
    """Run `inspector --cli ... --method tools/list` for `(target, transport)`."""
    return run(["--method", "tools/list", *build_target_args(target, transport)])


def build_target_args(
    target: str,
    transport: str = "stdio",
    headers: dict[str, str] | None = None,
) -> list[str]:
    """Translate a (target, transport) pair into Inspector CLI flags."""
    transport = (transport or "stdio").lower()
    if transport == "stdio":
        # `--` separator is required so the trailing tokens are the server command.
        return ["--transport", "stdio", "--", *target.split()]
    if transport in ("http", "sse"):
        flags: list[str] = ["--transport", transport, "--server-url", target]
        for name, value in (headers or {}).items():
            flags.extend(["--header", f"{name}: {value}"])
        return flags
    raise MCPInspectorError(f"Inspector CLI does not support transport={transport!r}")
