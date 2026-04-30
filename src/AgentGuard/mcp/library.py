"""Robot Framework keywords for testing MCP servers (ADR-002 / research §6.1).

`MCPKeywords` is mounted into the top-level `AgentGuard` library via
`DynamicCore` and can also be loaded standalone (`Library AgentGuard.mcp.MCPKeywords`).
SUITE scope — handles in `Suite Setup` are visible to every test.
"""

from __future__ import annotations

import logging
import warnings
from contextlib import suppress
from typing import Any, cast

import jsonschema
from robot.api.deco import keyword, library

from AgentGuard.mcp import inspector_cli
from AgentGuard.mcp._helpers import (
    arun,
    coerce_args,
    coerce_schema,
    fetch_capabilities,
    fetch_prompts,
    fetch_resources,
    fetch_tools,
    import_factory,
    latency_stats,
    make_latency_runner,
    result_to_dict,
    spawn_stdio,
)
from AgentGuard.mcp.exceptions import (
    MCPCapabilityError,
    MCPConnectionError,
    MCPInspectorError,
    MCPSchemaError,
    MCPToolError,
    MCPTransportError,
)
from AgentGuard.mcp.server_handle import ServerHandle
from AgentGuard.mcp.transports import (
    AUTO,
    HTTP,
    MEMORY,
    SSE,
    STDIO,
    make_client,
    normalize_transport,
)

# Optional: foundation agent's provider Protocol. Treat as Protocol stub if missing.
try:
    from AgentGuard.providers.base import LLMProviderAdapter  # noqa: F401
except Exception:  # pragma: no cover - foundation always ships this
    from typing import Protocol, runtime_checkable

    @runtime_checkable
    class LLMProviderAdapter(Protocol):  # type: ignore[no-redef]
        """Local stub — replaced once `AgentGuard.providers.base` lands."""

        name: str

logger = logging.getLogger("AgentGuard.mcp")

# Per exp_01: in-memory transport median ~2.2 ms/call. Warn if we slip beyond 5 ms.
_INMEMORY_P50_BUDGET_MS = 5.0


@library(scope="SUITE", version="0.1.0", auto_keywords=False)
class MCPKeywords:
    """Robot keywords for testing MCP servers.

    See ADR-002 for transport selection (`memory|stdio|http|sse|auto`).

    Examples:
        | ${h}=    | Start MCP Server | uv run python tests/fixtures/mcp/echo_server.py | stdio |
        | ${caps}= | Get MCP Capabilities | ${h} |
        | ${r}=    | Call MCP Tool | ${h} | add | {"x":2,"y":3} |
        | Stop MCP Server | ${h} |
    """

    def __init__(self, provider: LLMProviderAdapter | None = None) -> None:
        self._provider = provider
        self._handles: dict[str, ServerHandle] = {}
        self._counter = 0

    # ---- internal helpers ------------------------------------------------

    def _register(self, handle: ServerHandle) -> ServerHandle:
        self._handles[handle.name] = handle
        return handle

    def _next_name(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}-{self._counter}"

    async def _with_client(self, handle: ServerHandle, fn: Any) -> Any:
        client = make_client(handle)
        try:
            async with client as session:
                return await fn(session)
        except MCPTransportError:
            raise
        except Exception as exc:  # pragma: no cover - re-raised as MCPConnectionError
            raise MCPConnectionError(
                f"failed to interact with MCP server {handle.name!r}: {exc}"
            ) from exc

    # ---- lifecycle -------------------------------------------------------

    @keyword(name="Start MCP Server")
    def start_mcp_server(self, command: str, transport: str = AUTO) -> ServerHandle:
        """Spawn (or bind) an MCP server and return a ``ServerHandle``.
        memory: ``command`` is a dotted path (``pkg.module:factory`` or ``pkg.module`` with
        ``mcp``/``server``/``app``); stdio: shell command (new process group); http/sse: URL.
        Example: ``${h}=  Start MCP Server  uv run python echo_server.py  stdio``."""
        t = normalize_transport(transport, command)
        name = self._next_name("server")

        if t == MEMORY:
            instance = import_factory(command)
            handle = ServerHandle(name=name, transport=t, target=command, instance=instance)
            return self._register(handle)

        if t == STDIO:
            return self._register(spawn_stdio(command, name=name, transport=t))

        if t in (HTTP, SSE):
            return self._register(ServerHandle(name=name, transport=t, target=command))

        raise MCPTransportError(f"unsupported transport: {t}")

    @keyword(name="Connect To MCP Server")
    def connect_to_mcp_server(self, target: Any, transport: str = AUTO) -> ServerHandle:
        """Connect to an already-running MCP server; handle does not own its lifetime.
        ``target`` may be a URL, a stdio command string, or a FastMCP instance.
        Example: ``${h}=  Connect To MCP Server  http://localhost:3000/mcp``."""
        t = normalize_transport(transport, target)
        name = self._next_name("conn")
        if t == MEMORY:
            instance = import_factory(target) if isinstance(target, str) else target
            handle = ServerHandle(name=name, transport=t, target=target, instance=instance)
        else:
            handle = ServerHandle(name=name, transport=t, target=target)
        return self._register(handle)

    @keyword(name="Stop MCP Server")
    def stop_mcp_server(self, handle: ServerHandle) -> int | None:
        """Tear down an owned server; returns child exit code or None.
        Example: ``Stop MCP Server  ${h}``."""
        if not isinstance(handle, ServerHandle):
            raise MCPTransportError("Stop MCP Server requires a ServerHandle")
        rc = handle.terminate()
        with suppress(KeyError):
            del self._handles[handle.name]
        return rc

    # ---- introspection ---------------------------------------------------

    @keyword(name="Get MCP Capabilities")
    def get_mcp_capabilities(self, handle: ServerHandle) -> dict[str, list[str]]:
        """Return capabilities as ``{tools, resources, prompts}`` (lists of names).
        Example: ``${caps}=  Get MCP Capabilities  ${h}``."""
        return cast(dict[str, list[str]], arun(self._with_client(handle, fetch_capabilities)))

    @keyword(name="MCP Server Should Implement Capabilities")
    def mcp_server_should_implement_capabilities(
        self, handle: ServerHandle, *expected: str
    ) -> None:
        """Assert every ``expected`` name appears under tools/resources/prompts.
        Example: ``MCP Server Should Implement Capabilities  ${h}  add  echo``."""
        caps = self.get_mcp_capabilities(handle)
        flat = {*caps.get("tools", []), *caps.get("resources", []), *caps.get("prompts", [])}
        missing = [name for name in expected if name not in flat]
        if missing:
            raise MCPCapabilityError(
                f"server {handle.name!r} is missing capabilities: {missing}"
            )

    @keyword(name="List MCP Tools")
    def list_mcp_tools(self, handle: ServerHandle) -> list[dict[str, Any]]:
        """Return tool dicts (name, description, inputSchema, outputSchema).
        Example: ``${tools}=  List MCP Tools  ${h}``."""
        return cast(list[dict[str, Any]], arun(self._with_client(handle, fetch_tools)))

    @keyword(name="List MCP Resources")
    def list_mcp_resources(self, handle: ServerHandle) -> list[dict[str, Any]]:
        """Return resource dicts (uri, name, description, mimeType).
        Example: ``${rs}=  List MCP Resources  ${h}``."""
        return cast(list[dict[str, Any]], arun(self._with_client(handle, fetch_resources)))

    @keyword(name="List MCP Prompts")
    def list_mcp_prompts(self, handle: ServerHandle) -> list[dict[str, Any]]:
        """Return prompt dicts (name, description, arguments).
        Example: ``${ps}=  List MCP Prompts  ${h}``."""
        return cast(list[dict[str, Any]], arun(self._with_client(handle, fetch_prompts)))

    # ---- invocation ------------------------------------------------------

    @keyword(name="Call MCP Tool")
    def call_mcp_tool(
        self,
        handle: ServerHandle,
        name: str,
        arguments: dict[str, Any] | str | None = None,
    ) -> dict[str, Any]:
        """Invoke a tool; returns ``{data, is_error, structured_content, raw}``.
        ``arguments`` accepts a Robot dict or a JSON string.
        Example: ``${r}=  Call MCP Tool  ${h}  add  {"x":2,"y":3}``."""
        args = coerce_args(arguments)

        async def _go(session: Any) -> dict[str, Any]:
            return result_to_dict(await session.call_tool(name, args))

        out: dict[str, Any] = arun(self._with_client(handle, _go))
        if out.get("is_error"):
            raise MCPToolError(f"tool {name!r} returned is_error=True: {out.get('data')}")
        return out

    @keyword(name="MCP Tool Output Should Match Schema")
    def mcp_tool_output_should_match_schema(
        self, result: dict[str, Any], schema: dict[str, Any] | str
    ) -> None:
        """Validate ``result['data']`` against a JSON Schema (dict, JSON, or path).
        Example: ``MCP Tool Output Should Match Schema  ${r}  {"type":"integer"}``."""
        spec = coerce_schema(schema)
        payload = result.get("data") if isinstance(result, dict) else result
        try:
            jsonschema.validate(instance=payload, schema=spec)
        except jsonschema.ValidationError as exc:
            raise MCPSchemaError(f"tool output failed schema validation: {exc.message}") from exc

    @keyword(name="Measure MCP Tool Latency")
    def measure_mcp_tool_latency(
        self,
        handle: ServerHandle,
        name: str,
        runs: int = 50,
        arguments: dict[str, Any] | str | None = None,
    ) -> dict[str, float]:
        """Run ``name`` ``runs`` times; return ``{runs, mean, p50, p95, p99, min, max}`` in ms.
        Warns if memory p50 exceeds 5 ms (exp_01 baseline ~2.2 ms/call).
        Example: ``${stats}=  Measure MCP Tool Latency  ${h}  add  50  {"x":1,"y":2}``."""
        if runs <= 0:
            raise MCPToolError("runs must be > 0")
        args = coerce_args(arguments)
        samples_ms: list[float] = []
        arun(self._with_client(handle, make_latency_runner(name, args, runs, samples_ms)))
        stats = latency_stats(samples_ms, runs)
        if handle.transport == MEMORY and stats["p50"] > _INMEMORY_P50_BUDGET_MS:
            warnings.warn(
                f"in-memory MCP p50 {stats['p50']:.2f} ms > {_INMEMORY_P50_BUDGET_MS} ms"
                " budget (exp_01 baseline ~2.2 ms) — check fixture/environment.",
                RuntimeWarning,
                stacklevel=2,
            )
        return stats

    # ---- inspector CLI ---------------------------------------------------

    @keyword(name="MCP Inspector Should Connect")
    def mcp_inspector_should_connect(
        self, target: str, transport: str = STDIO
    ) -> dict[str, Any]:
        """Run ``inspector --cli ... --method tools/list``; assert exit 0.
        ``--method`` is undocumented in ``--help`` but works (exp_02); pinned in
        ``inspector_cli.INSPECTOR_PKG``.
        Example: ``MCP Inspector Should Connect  uv run python echo_server.py``."""
        result = inspector_cli.list_tools(target, transport)
        if not result.ok:
            raise MCPInspectorError(
                f"Inspector exited {result.returncode}: {result.stderr.strip()[:400]}"
            )
        return {"parsed": result.parsed, "stdout": result.stdout}

    @keyword(name="MCP Inspector List Tools")
    def mcp_inspector_list_tools(
        self, target: str, transport: str = STDIO
    ) -> list[dict[str, Any]]:
        """Run ``inspector --cli --method tools/list``; return the tools array.
        Example: ``${tools}=  MCP Inspector List Tools  uv run python echo_server.py``."""
        result = inspector_cli.list_tools(target, transport)
        if not result.ok:
            raise MCPInspectorError(
                f"Inspector exited {result.returncode}: {result.stderr.strip()[:400]}"
            )
        if isinstance(result.parsed, dict) and isinstance(result.parsed.get("tools"), list):
            return list(result.parsed["tools"])
        if isinstance(result.parsed, list):
            return result.parsed
        raise MCPInspectorError(
            f"Inspector returned no `tools` array; raw stdout: {result.stdout[:400]}"
        )
