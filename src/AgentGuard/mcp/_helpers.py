"""Internal helpers for `MCPKeywords` — kept out of `library.py` to honour the
≤300-line ceiling per file.

Nothing in here is part of the public Robot keyword surface.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import shlex
from typing import Any

from AgentGuard.mcp.exceptions import (
    MCPSchemaError,
    MCPToolError,
    MCPTransportError,
)
from AgentGuard.mcp.server_handle import ServerHandle


def arun(coro: Any) -> Any:
    """Run `coro` to completion on a fresh event loop and tear it down cleanly."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        finally:
            loop.close()


def coerce_args(arguments: dict[str, Any] | str | None) -> dict[str, Any]:
    """Accept dict or JSON string; return a plain dict for FastMCP.

    `None` / empty / `b""` → `{}`.
    """
    if arguments in (None, "", b""):
        return {}
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError as exc:
            raise MCPToolError(f"arguments must be a JSON object: {exc}") from exc
        if not isinstance(parsed, dict):
            raise MCPToolError(f"arguments JSON must decode to an object, got {type(parsed).__name__}")
        return dict(parsed)
    raise MCPToolError(f"unsupported arguments type: {type(arguments).__name__}")


def coerce_schema(schema: dict[str, Any] | str) -> dict[str, Any]:
    """Accept a dict, a JSON string, or a path to a JSON file."""
    if isinstance(schema, dict):
        return schema
    if not isinstance(schema, str):
        raise MCPSchemaError(f"unsupported schema type: {type(schema).__name__}")
    text = schema.strip()
    if text.startswith("{"):
        try:
            loaded = json.loads(text)
        except json.JSONDecodeError as exc:
            raise MCPSchemaError(f"schema is not valid JSON: {exc}") from exc
        if not isinstance(loaded, dict):
            raise MCPSchemaError(f"schema must decode to a JSON object, got {type(loaded).__name__}")
        return dict(loaded)
    if not os.path.exists(text):
        raise MCPSchemaError(f"schema not found: file or JSON expected, got {text!r}")
    try:
        with open(text, encoding="utf-8") as fh:
            loaded = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise MCPSchemaError(f"could not load schema {text!r}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise MCPSchemaError(f"schema must decode to a JSON object, got {type(loaded).__name__}")
    return dict(loaded)


def result_to_dict(result: Any) -> dict[str, Any]:
    """Normalise a FastMCP `CallToolResult` into a plain dict."""
    data = getattr(result, "data", None)
    if data is None:
        content = getattr(result, "content", None)
        if content:
            first = content[0]
            data = getattr(first, "text", None) or getattr(first, "data", None)
    return {
        "data": data,
        "is_error": bool(getattr(result, "is_error", False)),
        "structured_content": getattr(result, "structured_content", None),
        "raw": result,
    }


def tool_to_dict(tool: Any) -> dict[str, Any]:
    return {
        "name": getattr(tool, "name", None),
        "description": getattr(tool, "description", None),
        "inputSchema": getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None),
        "outputSchema": getattr(tool, "outputSchema", None) or getattr(tool, "output_schema", None),
    }


def resource_to_dict(resource: Any) -> dict[str, Any]:
    return {
        "uri": str(getattr(resource, "uri", "")),
        "name": getattr(resource, "name", None),
        "description": getattr(resource, "description", None),
        "mimeType": getattr(resource, "mimeType", None) or getattr(resource, "mime_type", None),
    }


def prompt_to_dict(prompt: Any) -> dict[str, Any]:
    return {
        "name": getattr(prompt, "name", None),
        "description": getattr(prompt, "description", None),
        "arguments": getattr(prompt, "arguments", None),
    }


def make_latency_runner(name: str, args: dict[str, Any], runs: int, samples_ms: list[float]) -> Any:
    """Return a coroutine that warms up once then records `runs` per-call latencies (ms)."""
    import time

    async def _run(session: Any) -> None:
        await session.call_tool(name, args)  # warmup
        for _ in range(runs):
            t0 = time.perf_counter()
            await session.call_tool(name, args)
            samples_ms.append((time.perf_counter() - t0) * 1000.0)

    return _run


def latency_stats(samples_ms: list[float], runs: int) -> dict[str, float]:
    """Compute `{runs, mean, p50, p95, p99, min, max}` from per-call ms samples."""
    import statistics

    samples_ms.sort()
    return {
        "runs": float(runs),
        "mean": statistics.fmean(samples_ms),
        "p50": quantile(samples_ms, 0.50),
        "p95": quantile(samples_ms, 0.95),
        "p99": quantile(samples_ms, 0.99),
        "min": samples_ms[0],
        "max": samples_ms[-1],
    }


async def fetch_capabilities(session: Any) -> dict[str, list[str]]:
    """Aggregate tool/resource/prompt names from one MCP session."""
    tools = await session.list_tools()
    try:
        resources = await session.list_resources()
    except Exception:
        resources = []
    try:
        prompts = await session.list_prompts()
    except Exception:
        prompts = []
    return {
        "tools": [getattr(t, "name", "") for t in tools],
        "resources": [str(getattr(r, "uri", "")) for r in resources],
        "prompts": [getattr(p, "name", "") for p in prompts],
    }


async def fetch_tools(session: Any) -> list[dict[str, Any]]:
    return [tool_to_dict(t) for t in await session.list_tools()]


async def fetch_resources(session: Any) -> list[dict[str, Any]]:
    try:
        items = await session.list_resources()
    except Exception:
        return []
    return [resource_to_dict(r) for r in items]


async def fetch_prompts(session: Any) -> list[dict[str, Any]]:
    try:
        items = await session.list_prompts()
    except Exception:
        return []
    return [prompt_to_dict(p) for p in items]


def quantile(sorted_samples: list[float], q: float) -> float:
    """Linear-interpolation quantile on a pre-sorted list."""
    if not sorted_samples:
        return 0.0
    if len(sorted_samples) == 1:
        return float(sorted_samples[0])
    pos = q * (len(sorted_samples) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_samples) - 1)
    frac = pos - lo
    return float(sorted_samples[lo] * (1 - frac) + sorted_samples[hi] * frac)


def spawn_stdio(command: str, name: str, transport: str) -> ServerHandle:
    """Validate the command and return a ServerHandle.

    The actual subprocess is spawned by FastMCP's StdioTransport on first client
    connect — pre-spawning here would leave dangling fds and break the second client.
    """
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        raise MCPTransportError(f"invalid stdio command {command!r}: {exc}") from exc
    if not argv:
        raise MCPTransportError("stdio command must not be empty")
    return ServerHandle(name=name, transport=transport, target=command, process=None)


def import_factory(spec: str) -> Any:
    """Resolve `pkg.module:factory` or `pkg.module` (with module-level `mcp`/`server`).

    Used by `Start MCP Server` and `Connect To MCP Server` for `transport=memory`.
    """
    if not isinstance(spec, str) or not spec:
        raise MCPTransportError("memory transport requires a dotted import path")
    if ":" in spec:
        mod_path, attr = spec.split(":", 1)
    else:
        mod_path, attr = spec, ""
    try:
        mod = importlib.import_module(mod_path)
    except Exception as exc:
        raise MCPTransportError(f"could not import {mod_path!r}: {exc}") from exc
    if attr:
        target = getattr(mod, attr, None)
        if target is None:
            raise MCPTransportError(f"{mod_path}:{attr} not found")
        return target() if callable(target) else target
    for name in ("mcp", "server", "app"):
        obj = getattr(mod, name, None)
        if obj is not None:
            return obj
    raise MCPTransportError(f"{mod_path} has no `mcp`, `server`, or `app` attribute")
