"""Sync facade over the ``a2a-sdk`` async client + in-process transport.

ADR-008 calls for two transports:

* ``memory`` — binds directly to an :class:`InProcessA2AServer` from
  :mod:`AgentGuard.subagents.a2a_server`. Used by unit tests and by users
  who want a quick test endpoint with zero network surface.
* ``http`` — wraps :func:`a2a.client.create_client` and the JSON-RPC
  transport from ``a2a-sdk>=1.0.2`` (verified in exp_08).

All async work is hidden behind sync facades using :func:`asyncio.run`,
matching the Robot keyword convention from
:class:`AgentGuard.tool_calls.library.ToolCallKeywords`.

The HTTP transport implementation lives in :mod:`AgentGuard.subagents.a2a_http`
to keep this module under the 300-line ceiling. The ``a2a-sdk`` import is
lazy — module load works without the SDK installed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from AgentGuard.subagents import a2a_server as _server_mod
from AgentGuard.subagents.exceptions import (
    AgentCardInvalid,
    TransportError,
)
from AgentGuard.subagents.types import (
    AgentCard,
    Task,
)

logger = logging.getLogger("AgentGuard.subagents.a2a_client")

Transport = str  # "auto" | "memory" | "http"


# ---------------------------------------------------------------------------
# Handle
# ---------------------------------------------------------------------------


@dataclass
class A2AClientHandle:
    """Opaque handle returned by ``Connect To A2A Agent``.

    Stores enough state to drive both transports through a uniform API.
    """

    transport: Transport
    url: str
    card: AgentCard | None = None
    inproc_server: _server_mod.InProcessA2AServer | None = None
    # ``a2a-sdk`` Client for the HTTP transport (lazy-built on first use).
    sdk_client: Any | None = None
    sdk_card: Any | None = None
    extras: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Card resolution
# ---------------------------------------------------------------------------


def get_agent_card(url: str, *, timeout: float = 10.0) -> AgentCard:
    """Fetch ``/.well-known/agent.json`` and return :class:`AgentCard`.

    Supports two URL schemes:

    * ``inproc://<name>`` — read the card from the registered server.
    * ``http(s)://...`` — fetch via :class:`a2a.client.A2ACardResolver`.
    """
    if url.startswith("inproc://"):
        server = _server_mod.lookup_server_for_url(url)
        return server.card

    from AgentGuard.subagents.a2a_http import fetch_http_card

    return fetch_http_card(url, timeout=timeout)


# ---------------------------------------------------------------------------
# Connect / send / wait / cancel
# ---------------------------------------------------------------------------


def connect_to_a2a_agent(
    target: AgentCard | str,
    *,
    transport: Transport = "auto",
    timeout: float = 10.0,
) -> A2AClientHandle:
    """Build a client handle for ``target``.

    ``target`` may be:

    * an :class:`AgentCard` (uses its ``url`` field; transport inferred from URL),
    * an ``inproc://<name>`` URL,
    * an HTTP(S) URL (the card is fetched first when ``transport='auto'``).
    """
    if isinstance(target, AgentCard):
        url = target.url or _interface_url(target)
        if not url:
            raise AgentCardInvalid("AgentCard has no url and no supported_interfaces")
        card: AgentCard | None = target
    else:
        url = target
        card = None

    chosen = _resolve_transport(url, transport)
    if chosen == "memory":
        server = _server_mod.lookup_server_for_url(url)
        return A2AClientHandle(
            transport="memory",
            url=url,
            card=card or server.card,
            inproc_server=server,
        )

    # HTTP transport — fetch the card eagerly so callers can introspect.
    if card is None:
        from AgentGuard.subagents.a2a_http import fetch_http_card

        card = fetch_http_card(url, timeout=timeout)
    return A2AClientHandle(transport="http", url=url, card=card)


def send_task(
    target: A2AClientHandle | str,
    message: str | dict[str, Any],
    *,
    metadata: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> Task:
    """Submit a task to ``target`` and return the resulting :class:`Task`.

    For the in-process transport the task is already terminal on return.
    For HTTP, follow up with ``Wait For Task Completion``.
    """
    handle = _coerce_handle(target)
    if handle.transport == "memory":
        assert handle.inproc_server is not None
        return handle.inproc_server.submit(message, metadata=metadata)

    from AgentGuard.subagents.a2a_http import http_send_task

    return http_send_task(handle, message, metadata=metadata, timeout=timeout)


def wait_for_task_completion(
    handle: A2AClientHandle | None,
    task: Task,
    *,
    timeout: float = 120.0,
    poll_interval: float = 0.5,
) -> Task:
    """Block until ``task`` reaches a terminal state or ``timeout`` elapses.

    ``handle`` may be ``None`` for in-process tasks since the in-process
    server completes synchronously inside :func:`send_task`.
    """
    if task.status.is_terminal:
        return task

    if handle is None or handle.transport == "memory":
        # In-process tasks complete synchronously in submit_async; if we got
        # a non-terminal status the test harness is misconfigured.
        return task

    from AgentGuard.subagents.a2a_http import http_wait_for_completion

    return http_wait_for_completion(handle, task, timeout=timeout, poll_interval=poll_interval)


def cancel_task(handle: A2AClientHandle, task: Task) -> Task:
    """Request cancellation of an in-flight task."""
    if handle.transport == "memory":
        assert handle.inproc_server is not None
        return handle.inproc_server.cancel_task(task.id)

    from AgentGuard.subagents.a2a_http import http_cancel_task

    return http_cancel_task(handle, task)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_transport(url: str, requested: Transport) -> Transport:
    if requested in {"memory", "http"}:
        return requested
    # auto
    if url.startswith("inproc://"):
        return "memory"
    if url.startswith(("http://", "https://", "grpc://")):
        return "http"
    raise TransportError(f"cannot infer transport for url={url!r}")


def _interface_url(card: AgentCard) -> str:
    for iface in card.supported_interfaces:
        if iface.url:
            return iface.url
    return ""


def _coerce_handle(target: A2AClientHandle | str) -> A2AClientHandle:
    if isinstance(target, A2AClientHandle):
        return target
    return connect_to_a2a_agent(target)


__all__ = [
    "A2AClientHandle",
    "Transport",
    "cancel_task",
    "connect_to_a2a_agent",
    "get_agent_card",
    "send_task",
    "wait_for_task_completion",
]
