"""Transport selection + client factory for MCP (ADR-002).

Four transports:
- `memory` : `fastmcp.Client(server_instance)` — deterministic, ~2 ms/call (exp_01).
- `stdio`  : JSON-RPC over a child process's stdin/stdout — canonical CI shape.
- `http`   : streamable-HTTP — modern remote transport.
- `sse`    : Server-Sent Events — supported but flagged DEPRECATED.

`auto` resolves by inspecting the target:
- a `FastMCP` instance / callable host          → memory
- string starting `http://`/`https://`           → http (or sse if path ends `/sse`)
- anything else (treated as a shell command)     → stdio
"""

from __future__ import annotations

import shlex
import warnings
from typing import Any
from urllib.parse import urlparse

from AgentGuard.mcp.exceptions import MCPTransportError
from AgentGuard.mcp.server_handle import ServerHandle

# ---- transport constants -------------------------------------------------

MEMORY = "memory"
STDIO = "stdio"
SSE = "sse"
HTTP = "http"
AUTO = "auto"

_VALID = {MEMORY, STDIO, SSE, HTTP}


# ---- inference -----------------------------------------------------------


def infer_transport(target: Any) -> str:
    """Return the transport AgentGuard would pick for `target` if `transport=auto`.

    Rules (in order):
    - `None`                                   → ValueError (caller should pass something)
    - object with `.run`/`.tool` (FastMCP-ish) → memory
    - str starting `http://` or `https://`     → sse if path includes `/sse`, else http
    - any other str                            → stdio (treated as shell command)
    - everything else                          → memory  (assume in-process server object)

    Examples:
        | ${t}= | Infer Transport | http://localhost:3000/mcp |
        | Should Be Equal | ${t} | http |
    """
    if target is None:
        raise MCPTransportError("Cannot infer transport from None target")
    # Heuristic: FastMCP servers are objects with both `.run` and `.tool` callables.
    if not isinstance(target, str):
        if all(callable(getattr(target, attr, None)) for attr in ("run", "tool")):
            return MEMORY
        # Fall through — unknown object; default to memory and let the client fail loudly.
        return MEMORY
    s = target.strip()
    if not s:
        raise MCPTransportError("Empty target string — cannot infer transport")
    lower = s.lower()
    if lower.startswith(("http://", "https://")):
        path = (urlparse(s).path or "").lower()
        if path.endswith("/sse") or path == "/sse":
            warnings.warn(
                "SSE transport is deprecated by Anthropic; prefer streamable-HTTP.",
                DeprecationWarning,
                stacklevel=2,
            )
            return SSE
        return HTTP
    # Treat any other string as a shell command (stdio server).
    return STDIO


def normalize_transport(transport: str, target: Any) -> str:
    """Coerce `transport` to a canonical value, resolving `auto`."""
    t = (transport or AUTO).lower()
    if t == AUTO:
        return infer_transport(target)
    if t not in _VALID:
        raise MCPTransportError(
            f"Unknown transport {transport!r}; expected one of {sorted(_VALID) + [AUTO]}"
        )
    if t == SSE:
        warnings.warn(
            "SSE transport is deprecated by Anthropic; prefer streamable-HTTP.",
            DeprecationWarning,
            stacklevel=2,
        )
    return t


# ---- client factory ------------------------------------------------------


def make_client(handle: ServerHandle, transport: str | None = None) -> Any:
    """Build a `fastmcp.Client` for `handle`, ready to `async with` enter.

    The factory imports `fastmcp` lazily so the module loads even when fastmcp
    is absent (e.g. during `agentguard doctor` on a slimmed-down install).
    """
    try:
        from fastmcp import Client
    except Exception as exc:  # pragma: no cover - deps validated at runtime
        raise MCPTransportError(
            "fastmcp is required for MCP transport client; install `fastmcp>=3.2.4`."
        ) from exc

    t = (transport or handle.transport or AUTO).lower()
    if t == AUTO:
        t = infer_transport(handle.instance if handle.instance is not None else handle.target)

    if t == MEMORY:
        if handle.instance is None:
            raise MCPTransportError(
                "Memory transport requires an in-process FastMCP instance on the handle"
            )
        return Client(handle.instance)

    if t == STDIO:
        target = handle.target
        if not isinstance(target, str):
            raise MCPTransportError("stdio transport requires a string command target")
        try:
            argv = shlex.split(target)
        except ValueError as exc:
            raise MCPTransportError(f"stdio target is not a valid command: {exc}") from exc
        if not argv:
            raise MCPTransportError("stdio command is empty")
        # Single-token Python script path: let FastMCP auto-infer the python interpreter.
        if len(argv) == 1:
            return Client(argv[0])
        # Multi-word command: build StdioTransport explicitly so FastMCP doesn't have to guess.
        from fastmcp.client.transports import StdioTransport

        return Client(StdioTransport(command=argv[0], args=argv[1:]))

    if t in (HTTP, SSE):
        if not isinstance(handle.target, str):
            raise MCPTransportError(f"{t} transport requires a URL string target")
        return Client(handle.target)

    raise MCPTransportError(f"Cannot construct client for transport={t!r}")
