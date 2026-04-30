"""ServerHandle — opaque identifier for an in-flight or attached MCP server.

A handle bundles:
- `name`         : human-friendly id (used in Robot logs)
- `transport`    : resolved transport (`memory|stdio|sse|http`)
- `target`       : raw target supplied by the user (command string, URL, or FastMCP instance)
- `process`      : optional `subprocess.Popen` for stdio/http server processes we spawned
- `instance`     : optional in-process FastMCP instance for the in-memory transport
- `metadata`     : free-form dict (suite name, env vars, etc.)

The handle is *not* a live client — `transports.make_client(handle)` is what
opens a `fastmcp.Client` ready to `__aenter__`.
"""

from __future__ import annotations

import os
import signal
import subprocess
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ServerHandle:
    """Lifecycle anchor for an MCP server under test."""

    name: str
    transport: str
    target: Any
    process: subprocess.Popen[bytes] | None = None
    instance: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_running(self) -> bool:
        """True if we own a child process and it is still alive (or in-memory)."""
        if self.instance is not None:
            return True
        if self.process is None:
            # Connected-only handle — caller owns the lifetime.
            return True
        return self.process.poll() is None

    def terminate(self, timeout: float = 5.0) -> int | None:
        """Best-effort teardown. Returns the exit code of an owned process, or None."""
        if self.process is None:
            return None
        if self.process.poll() is not None:
            return self.process.returncode
        try:
            # Send SIGTERM to the whole process group (works for `npm`/`npx` wrappers).
            try:
                pgid = os.getpgid(self.process.pid)
                os.killpg(pgid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                self.process.terminate()
            try:
                return self.process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self.process.kill()
                return self.process.wait(timeout=timeout)
        finally:
            self.process = None
