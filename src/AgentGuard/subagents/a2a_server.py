"""In-process A2A server fixture (ADR-008).

A real A2A 1.0 server (FastAPI/grpc) is overkill for unit tests. This
module provides a lightweight in-process server that registers under a
unique name in a process-global registry, binds an :class:`AgentCard`
describing its skills, dispatches tasks to a sync or async ``handler``
callable, and records every task in memory.

The companion :class:`AgentGuard.subagents.a2a_client.A2AClientHandle`
with ``transport='memory'`` resolves an in-process server by URL of the
form ``inproc://<name>``. This avoids the ``a2a-sdk`` HTTP/gRPC stack
entirely for tests that only care about the lifecycle and artifact shape.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import threading
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from AgentGuard.subagents.exceptions import TransportError
from AgentGuard.subagents.types import (
    AgentCard,
    Artifact,
    Message,
    MessagePart,
    Task,
    TaskStatus,
    text_artifact,
)

logger = logging.getLogger("AgentGuard.subagents.a2a_server")

# A handler may take the raw input string OR a Message dict, and return
# a string, a dict, an Artifact, or a list of Artifacts.
HandlerInput = str | dict[str, Any]
HandlerOutput = str | dict[str, Any] | Artifact | list[Artifact]
HandlerSync = Callable[[HandlerInput], HandlerOutput]
HandlerAsync = Callable[[HandlerInput], Awaitable[HandlerOutput]]
Handler = HandlerSync | HandlerAsync


# --- Registry ---------------------------------------------------------------

_REGISTRY: dict[str, InProcessA2AServer] = {}
_REGISTRY_LOCK = threading.Lock()


def lookup_server(name: str) -> InProcessA2AServer:
    """Find a registered in-process server by name (case-sensitive)."""
    with _REGISTRY_LOCK:
        try:
            return _REGISTRY[name]
        except KeyError as exc:
            raise TransportError(f"no in-process A2A server named {name!r}; known: {sorted(_REGISTRY)}") from exc


def lookup_server_for_url(url: str) -> InProcessA2AServer:
    """Resolve an ``inproc://<name>`` URL to a registered server."""
    if not url.startswith("inproc://"):
        raise TransportError(f"not an inproc:// URL: {url!r}")
    return lookup_server(url[len("inproc://") :])


def list_servers() -> list[str]:
    """Names of all currently-registered in-process servers."""
    with _REGISTRY_LOCK:
        return sorted(_REGISTRY)


# --- Server handle ----------------------------------------------------------


@dataclass
class ServerHandle:
    """Lightweight handle returned by :func:`start_server`."""

    name: str
    url: str  # always ``inproc://<name>`` for in-process servers
    card: AgentCard

    def server(self) -> InProcessA2AServer:
        return lookup_server(self.name)

    def stop(self) -> None:
        stop_server(self.name)


class InProcessA2AServer:
    """In-process A2A agent. Not thread-safe across event loops."""

    def __init__(self, name: str, handler: Handler, card: AgentCard) -> None:
        self.name = name
        self.handler = handler
        self.card = card
        self.tasks: dict[str, Task] = {}
        self._handler_is_async = inspect.iscoroutinefunction(handler)

    @property
    def url(self) -> str:
        return f"inproc://{self.name}"

    # --- Task lifecycle ------------------------------------------------

    async def submit_async(
        self,
        message: HandlerInput,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        """Run the handler within the running event loop and return a terminal Task."""
        context_id = uuid.uuid4().hex
        task_id = uuid.uuid4().hex
        task = Task(
            id=task_id,
            status=TaskStatus.SUBMITTED,
            context_id=context_id,
            metadata=dict(metadata or {}),
        )
        # Record the inbound user message.
        text_in = message if isinstance(message, str) else _stringify_input(message)
        task.messages.append(_text_message("user", text_in))
        self.tasks[task_id] = task

        # Transition to working before invoking the handler.
        task.status = TaskStatus.WORKING
        task.touch()

        try:
            if self._handler_is_async:
                raw_out = await self.handler(message)  # type: ignore[misc]
            else:
                raw_out = self.handler(message)
        except Exception as exc:  # noqa: BLE001 - surface as failed task
            task.status = TaskStatus.FAILED
            task.error = f"{type(exc).__name__}: {exc}"
            task.touch()
            logger.warning("inproc A2A handler %s raised: %s", self.name, exc)
            return task

        artifacts = _coerce_handler_output(raw_out)
        task.artifacts.extend(artifacts)
        # Echo agent reply as a transcript message for trajectory tooling.
        for art in artifacts:
            text_out = "\n".join(p.text for p in art.parts if p.kind == "text")
            if text_out:
                task.messages.append(_text_message("agent", text_out))
        task.status = TaskStatus.COMPLETED
        task.touch()
        return task

    def submit(
        self,
        message: HandlerInput,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        """Sync facade over :meth:`submit_async`; thread-dispatched if nested."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.submit_async(message, metadata=metadata))
        # Nested loop — dispatch to a worker thread to avoid asyncio.run nesting.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(self.submit_async(message, metadata=metadata))).result()

    def get_task(self, task_id: str) -> Task:
        if task_id not in self.tasks:
            raise TransportError(f"unknown task {task_id!r} on server {self.name!r}")
        return self.tasks[task_id]

    def cancel_task(self, task_id: str) -> Task:
        task = self.get_task(task_id)
        if not task.status.is_terminal:
            task.status = TaskStatus.CANCELED
            task.touch()
        return task


# --- Public start/stop ------------------------------------------------------


def start_server(
    name: str,
    handler: Handler,
    *,
    card: AgentCard | None = None,
    description: str = "",
    skills: list[dict[str, Any]] | None = None,
    overwrite: bool = False,
) -> ServerHandle:
    """Register an in-process A2A agent and return its :class:`ServerHandle`."""
    with _REGISTRY_LOCK:
        if name in _REGISTRY and not overwrite:
            raise TransportError(f"in-process A2A server {name!r} already registered; pass overwrite=True to replace.")
        if card is None:
            card = _default_card(name, description, skills)
        server = InProcessA2AServer(name=name, handler=handler, card=card)
        _REGISTRY[name] = server
        return ServerHandle(name=name, url=server.url, card=card)


def stop_server(name: str) -> None:
    """Deregister a server. No-op if missing."""
    with _REGISTRY_LOCK:
        _REGISTRY.pop(name, None)


def reset_registry() -> None:
    """Forget every in-process server (useful between test files)."""
    with _REGISTRY_LOCK:
        _REGISTRY.clear()


# --- Helpers ----------------------------------------------------------------


def _default_card(
    name: str,
    description: str,
    skills: list[dict[str, Any]] | None,
) -> AgentCard:
    from AgentGuard.subagents.types import AgentSkill

    card_skills = tuple(
        AgentSkill(
            id=str(s.get("id", s.get("name", f"skill-{i}"))),
            name=str(s.get("name", f"skill-{i}")),
            description=str(s.get("description", "")),
            tags=tuple(s.get("tags", []) or []),
            examples=tuple(s.get("examples", []) or []),
        )
        for i, s in enumerate(skills or [])
    )
    return AgentCard(
        name=name,
        description=description or f"In-process A2A agent {name}",
        version="1.0",
        url=f"inproc://{name}",
        skills=card_skills,
        default_input_modes=("text/plain",),
        default_output_modes=("text/plain",),
    )


def _text_message(role: str, text: str) -> Message:
    return Message(
        role=role,
        parts=(MessagePart(kind="text", text=text, media_type="text/plain"),),
    )


def _stringify_input(message: dict[str, Any]) -> str:
    if isinstance(message, dict):
        for key in ("text", "content"):
            value = message.get(key)
            if isinstance(value, str):
                return value
    return str(message)


def _coerce_handler_output(raw: HandlerOutput) -> list[Artifact]:
    if isinstance(raw, Artifact):
        return [raw]
    if isinstance(raw, list):
        return [a if isinstance(a, Artifact) else text_artifact(str(a)) for a in raw]
    if isinstance(raw, str):
        return [text_artifact(raw)]
    if isinstance(raw, dict):
        return [
            Artifact(
                artifact_id=uuid.uuid4().hex,
                name="result",
                parts=(MessagePart(kind="data", data=raw, media_type="application/json"),),
            )
        ]
    return [text_artifact(str(raw))]


__all__ = [
    "Handler",
    "InProcessA2AServer",
    "ServerHandle",
    "list_servers",
    "lookup_server",
    "lookup_server_for_url",
    "reset_registry",
    "start_server",
    "stop_server",
]
