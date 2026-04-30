"""HTTP transport adapter for the SubAgents module.

Wraps the async ``a2a-sdk>=1.0.2`` client (verified in exp_08) behind sync
helpers used by :mod:`AgentGuard.subagents.a2a_client`. Kept in its own
file so the in-process / memory transport can stay free of any
``a2a-sdk`` import at module load time.

The SDK exposes everything via protobuf messages (``a2a.types.*``); we
convert to and from our dataclasses via :mod:`AgentGuard.subagents.types_pb`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import TYPE_CHECKING, Any

from AgentGuard.subagents.exceptions import (
    TaskTimeout,
    TransportError,
)
from AgentGuard.subagents.types import AgentCard, Task

if TYPE_CHECKING:  # pragma: no cover - type-only
    from AgentGuard.subagents.a2a_client import A2AClientHandle


def import_sdk() -> tuple[Any, Any]:
    """Import :mod:`a2a` lazily and return ``(client_module, types_module)``."""
    try:
        import a2a.client as a2a_client
        import a2a.types as a2a_types
    except ImportError as exc:  # pragma: no cover
        raise TransportError("a2a-sdk is not installed; pip install 'a2a-sdk>=1.0.2'") from exc
    return a2a_client, a2a_types


def fetch_http_card(url: str, *, timeout: float) -> AgentCard:
    """Fetch ``/.well-known/agent.json`` over HTTP."""
    a2a_client_mod, _ = import_sdk()
    import httpx

    base_url, _, suffix = url.partition("/.well-known/")
    relative_path = f"/.well-known/{suffix}" if suffix else None

    async def _do() -> AgentCard:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resolver = a2a_client_mod.A2ACardResolver(
                httpx_client=client,
                base_url=base_url,
            )
            try:
                pb_card = await resolver.get_agent_card(
                    relative_card_path=relative_path,
                )
            except Exception as exc:
                raise TransportError(f"failed to fetch agent card from {url!r}: {exc}") from exc
        from AgentGuard.subagents.types_pb import from_pb_card

        return from_pb_card(pb_card)

    return asyncio.run(_do())


def http_send_task(
    handle: A2AClientHandle,
    message: str | dict[str, Any],
    *,
    metadata: dict[str, Any] | None,
    timeout: float,
) -> Task:
    """Send a task to an HTTP A2A endpoint and return the first ``Task`` event."""
    _, a2a_types = import_sdk()
    from a2a.helpers import new_text_message

    text = message if isinstance(message, str) else str(message)
    pb_message = new_text_message(text=text, role=a2a_types.Role.ROLE_USER)
    request = a2a_types.SendMessageRequest(request=pb_message)

    async def _do() -> Task:
        client = await ensure_sdk_client(handle)
        try:
            stream = client.send_message(request)
            last_task: Any = None
            async for event in stream:
                which = event.WhichOneof("payload")
                if which == "task":
                    last_task = event.task
                elif which == "task_status_update":
                    if last_task is not None:
                        last_task.status.CopyFrom(event.task_status_update.status)
                elif which == "task_artifact_update":
                    if last_task is not None:
                        last_task.artifacts.append(event.task_artifact_update.artifact)
        except Exception as exc:  # noqa: BLE001
            raise TransportError(f"send_message failed: {exc}") from exc

        if last_task is None:
            raise TransportError("send_message returned no Task event")
        from AgentGuard.subagents.types_pb import from_pb_task

        out = from_pb_task(last_task)
        if metadata:
            out.metadata.update(metadata)
        return out

    return _run_with_timeout(_do(), timeout)


def http_wait_for_completion(
    handle: A2AClientHandle,
    task: Task,
    *,
    timeout: float,
    poll_interval: float,
) -> Task:
    """Poll ``get_task`` until the task reaches a terminal state."""
    _, a2a_types = import_sdk()

    async def _do() -> Task:
        client = await ensure_sdk_client(handle)
        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            try:
                pb_task = await client.get_task(a2a_types.GetTaskRequest(name=task.id))
            except Exception as exc:  # noqa: BLE001
                raise TransportError(f"get_task failed: {exc}") from exc
            from AgentGuard.subagents.types_pb import from_pb_task

            updated = from_pb_task(pb_task)
            task.status = updated.status
            task.messages = updated.messages
            task.artifacts = updated.artifacts
            task.touch()
            if task.status.is_terminal:
                return task
            if asyncio.get_event_loop().time() > deadline:
                raise TaskTimeout(
                    f"task {task.id} did not complete within {timeout}s (last status: {task.status.value})",
                    task=task,
                )
            await asyncio.sleep(poll_interval)

    return _run_with_timeout(_do(), timeout + poll_interval)


def http_cancel_task(handle: A2AClientHandle, task: Task) -> Task:
    """Cancel a remote task via JSON-RPC."""
    _, a2a_types = import_sdk()

    async def _do() -> Task:
        client = await ensure_sdk_client(handle)
        try:
            pb_task = await client.cancel_task(a2a_types.CancelTaskRequest(name=task.id))
        except Exception as exc:  # noqa: BLE001
            raise TransportError(f"cancel_task failed: {exc}") from exc
        from AgentGuard.subagents.types_pb import from_pb_task

        updated = from_pb_task(pb_task)
        task.status = updated.status
        task.artifacts = updated.artifacts
        task.touch()
        return task

    return _run_with_timeout(_do(), 10.0)


async def ensure_sdk_client(handle: A2AClientHandle) -> Any:
    """Build (and cache on ``handle``) the a2a-sdk client for an HTTP target."""
    if handle.sdk_client is not None:
        return handle.sdk_client
    a2a_client_mod, _ = import_sdk()
    try:
        client = await a2a_client_mod.create_client(handle.url)
    except Exception as exc:  # noqa: BLE001
        raise TransportError(f"could not create a2a-sdk client for {handle.url!r}: {exc}") from exc
    handle.sdk_client = client
    return client


def _run_with_timeout[T](coro: Awaitable[T], timeout: float) -> T:
    """Run an awaitable to completion under :func:`asyncio.run` with a guard."""

    async def _wrapper() -> T:
        return await asyncio.wait_for(coro, timeout=timeout)

    try:
        return asyncio.run(_wrapper())
    except TimeoutError as exc:
        raise TaskTimeout(f"operation did not complete within {timeout}s") from exc


__all__ = [
    "ensure_sdk_client",
    "fetch_http_card",
    "http_cancel_task",
    "http_send_task",
    "http_wait_for_completion",
    "import_sdk",
]
