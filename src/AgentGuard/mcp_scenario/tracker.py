"""TrackedMCPSession — auto-record every tool call against an MCP server (ADR-021).

The tracker is opt-in: callers who don't ``Start Tracked MCP Session`` keep the
existing :class:`AgentGuard.mcp.library.MCPKeywords` behaviour untouched. Once
started, calls dispatched through :meth:`TrackedMCPSession.call_tool` append a
:class:`ToolCallRecord` to the in-memory list.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from AgentGuard.mcp_scenario.types import ToolCallRecord

if TYPE_CHECKING:  # pragma: no cover
    from AgentGuard.mcp.library import MCPKeywords
    from AgentGuard.mcp.server_handle import ServerHandle


@dataclass
class TrackedMCPSession:
    """Recording overlay on an MCP :class:`ServerHandle`.

    Lifecycle: ``Start Tracked MCP Session`` → N ``Call Tracked Tool`` →
    ``End Tracked MCP Session``. The handle itself is not modified; we just
    keep a list of :class:`ToolCallRecord` for the suite scope.
    """

    handle: ServerHandle
    mcp: MCPKeywords
    records: list[ToolCallRecord] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    ended_at: float | None = None

    def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | str | None = None,
    ) -> dict[str, Any]:
        """Dispatch the tool call, record it, and return the raw result.

        ``arguments`` may be a dict or a JSON-encoded string (Robot Framework
        users routinely pass ``{"x": 1}`` literally — RF will hand it across as
        a ``str`` unless a ``${...}`` evaluation is used). String inputs are
        JSON-parsed for the recorded ``ToolCallRecord.arguments`` so the
        ``required_params`` matcher sees real keys.

        On a tool-level error (``is_error=True``) we record ``success=False``
        but still return the result so the caller can inspect it.
        On a transport / library exception we record + re-raise.
        """
        coerced_args = _coerce_args_for_record(arguments)
        try:
            result: dict[str, Any] = self.mcp.call_mcp_tool(self.handle, name, arguments)
        except Exception as exc:  # noqa: BLE001 — record before re-raising
            self.records.append(
                ToolCallRecord(
                    tool_name=name,
                    arguments=dict(coerced_args),
                    success=False,
                    result=None,
                    error=str(exc),
                    timestamp=time.time(),
                )
            )
            raise

        is_error = bool(result.get("is_error"))
        self.records.append(
            ToolCallRecord(
                tool_name=name,
                arguments=dict(coerced_args),
                success=not is_error,
                result=_safe_result_payload(result),
                error=(_extract_error_text(result) if is_error else None),
                timestamp=time.time(),
            )
        )
        return result

    def reset(self) -> None:
        """Clear records (handy mid-suite to scope hit-rate to one phase)."""
        self.records = []
        self.started_at = time.time()
        self.ended_at = None

    def end(self) -> None:
        """Mark the session ended (records remain readable)."""
        self.ended_at = time.time()

    def execution_time_seconds(self) -> float:
        end = self.ended_at if self.ended_at is not None else time.time()
        return max(0.0, end - self.started_at)


def _coerce_args_for_record(arguments: dict[str, Any] | str | None) -> dict[str, Any]:
    """Normalise tool arguments to a plain dict for recording purposes.

    Mirrors the coercion ``MCPKeywords.call_mcp_tool`` applies before
    dispatching, so the recorded ``ToolCallRecord.arguments`` matches what
    the MCP server actually saw.
    """
    if isinstance(arguments, dict):
        return dict(arguments)
    if arguments in (None, "", b""):
        return {}
    if isinstance(arguments, str):
        import json as _json

        try:
            parsed = _json.loads(arguments)
        except (_json.JSONDecodeError, ValueError):
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def _safe_result_payload(result: dict[str, Any]) -> dict[str, Any] | None:
    """Strip the un-serialisable ``raw`` FastMCP CallToolResult before recording."""
    if not isinstance(result, dict):
        return None
    return {k: v for k, v in result.items() if k != "raw"}


def _extract_error_text(result: dict[str, Any]) -> str:
    data = result.get("data")
    if isinstance(data, str):
        return data
    if data is not None:
        return str(data)
    return "tool returned is_error=True"


__all__ = ["TrackedMCPSession"]
