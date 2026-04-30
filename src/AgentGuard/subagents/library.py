"""SubAgentsKeywords — Robot Framework surface for the SubAgents (A2A) context.

Composed into the top-level :class:`AgentGuard.AgentGuard` library via
``DynamicCore`` registration. All keywords are sync; async work is hidden
behind :mod:`AgentGuard.subagents.a2a_client` which uses
:func:`asyncio.run` internally.

Tier-1 keywords (everything except live HTTP fetches) work without an API
key. Transport-dependent keywords raise
:class:`AgentGuard.subagents.exceptions.TransportError` on network
failure. Trajectory comparison reuses the BFCL matcher from Phase 1
(ADR-004), via :mod:`AgentGuard.subagents.trajectory`.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Protocol

from robot.api.deco import keyword

from AgentGuard.subagents import a2a_client as _client_mod
from AgentGuard.subagents.exceptions import (
    SubAgentError,
    TaskFailed,
)
from AgentGuard.subagents.trajectory import (
    extract_a2a_trajectory,
    match_sequence,
)
from AgentGuard.subagents.types import (
    AgentCard,
    AgentSkill,
    Artifact,
    Task,
    TaskStatus,
    artifact_text,
)
from AgentGuard.subagents.validate import (
    assert_card_required_fields,
    parse_card_input,
)

logger = logging.getLogger("AgentGuard.subagents")


class _ProviderLike(Protocol):
    def chat(self, *args: Any, **kwargs: Any) -> Any: ...


class SubAgentsKeywords:
    """Robot Framework keywords for A2A 1.0 sub-agent testing (ADR-008)."""

    def __init__(self, provider: _ProviderLike | None = None) -> None:
        # Provider accepted for symmetry with other modules but unused —
        # SubAgents tests speak A2A, not the provider's chat API.
        self._provider = provider

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    @keyword(name="Get Agent Card")
    def get_agent_card(self, url: str, timeout: float = 10.0) -> AgentCard:
        """Fetch ``/.well-known/agent.json`` from ``url``.

        Supports ``inproc://<name>`` for in-process test agents and
        ``http(s)://...`` for real A2A endpoints.
        """
        card = _client_mod.get_agent_card(url, timeout=timeout)
        logger.info("fetched AgentCard for %s (%d skills)", card.name, len(card.skills))
        return card

    @keyword(name="Validate Agent Card")
    def validate_agent_card(
        self,
        card: AgentCard | dict[str, Any] | str | Path,
    ) -> AgentCard:
        """Validate that ``card`` matches the A2A 1.0 AgentCard shape.

        Accepts an :class:`AgentCard`, a raw dict, a JSON string, or a
        :class:`~pathlib.Path` to a JSON file. Returns the canonical
        :class:`AgentCard` on success; raises
        :class:`AgentGuard.subagents.exceptions.AgentCardInvalid` otherwise.
        """
        parsed = card if isinstance(card, AgentCard) else parse_card_input(card)
        assert_card_required_fields(parsed)
        return parsed

    @keyword(name="List Agent Skills")
    def list_agent_skills(self, card: AgentCard) -> list[AgentSkill]:
        """Return the skill list declared on ``card``."""
        return list(card.skills)

    # ------------------------------------------------------------------
    # Connection / lifecycle
    # ------------------------------------------------------------------

    @keyword(name="Connect To A2A Agent")
    def connect_to_a2a_agent(
        self,
        target: AgentCard | str,
        transport: str = "auto",
        timeout: float = 10.0,
    ) -> _client_mod.A2AClientHandle:
        """Build a client for ``target`` (AgentCard, URL, or inproc name).

        ``transport`` ∈ ``{auto, memory, http}``. ``auto`` infers from the
        URL scheme: ``inproc://`` → memory, ``http(s)://`` → http.
        """
        return _client_mod.connect_to_a2a_agent(
            target, transport=transport, timeout=timeout
        )

    @keyword(name="Send Task")
    def send_task(
        self,
        target: _client_mod.A2AClientHandle | str,
        message: str | dict[str, Any],
        metadata: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> Task:
        """Submit a task to ``target`` and return the resulting :class:`Task`.

        For the in-process transport the task is already terminal on
        return; for HTTP, follow up with ``Wait For Task Completion``.
        """
        task = _client_mod.send_task(
            target, message, metadata=metadata, timeout=timeout
        )
        logger.info("submitted task %s -> status=%s", task.id, task.status.value)
        return task

    @keyword(name="Wait For Task Completion")
    def wait_for_task_completion(
        self,
        task: Task,
        handle: _client_mod.A2AClientHandle | None = None,
        timeout: float = 120.0,
        poll_interval: float = 0.5,
    ) -> Task:
        """Block until ``task`` reaches a terminal state or ``timeout`` elapses.

        Raises :class:`AgentGuard.subagents.exceptions.TaskTimeout` if the
        task is still non-terminal at the deadline.
        """
        return _client_mod.wait_for_task_completion(
            handle, task, timeout=timeout, poll_interval=poll_interval
        )

    @keyword(name="Cancel Task")
    def cancel_task(
        self,
        handle: _client_mod.A2AClientHandle,
        task: Task,
    ) -> Task:
        """Request cancellation of ``task`` and assert the transition."""
        updated = _client_mod.cancel_task(handle, task)
        if updated.status != TaskStatus.CANCELED:
            raise TaskFailed(
                f"cancel failed: task {task.id} is in state {updated.status.value!r}"
            )
        return updated

    # ------------------------------------------------------------------
    # Status / artifacts
    # ------------------------------------------------------------------

    @keyword(name="Get Task Status")
    def get_task_status(self, task: Task) -> str:
        """Return the current status string of ``task``."""
        return task.status.value

    @keyword(name="Task Should Have Status")
    def task_should_have_status(
        self,
        task: Task,
        expected: str | TaskStatus,
    ) -> None:
        """Assert ``task.status == expected`` (case-insensitive string ok)."""
        expected_status = TaskStatus.from_str(expected)
        if task.status != expected_status:
            err: type[SubAgentError] = (
                TaskFailed if expected_status == TaskStatus.COMPLETED else SubAgentError
            )
            err_text = task.error or ""
            extra = f" (error: {err_text})" if err_text else ""
            raise err(
                f"task {task.id}: expected status {expected_status.value!r}, "
                f"got {task.status.value!r}{extra}"
            )

    @keyword(name="Get Task Artifact")
    def get_task_artifact(
        self,
        task: Task,
        type: str | None = None,  # noqa: A002 - keyword name for Robot ergonomics
    ) -> list[Artifact]:
        """Return the task's artifacts, optionally filtered by mime type.

        ``type`` is matched against :attr:`Artifact.mime_type` (case-insensitive,
        prefix-friendly: ``"text"`` matches ``"text/plain"``).
        """
        if type is None:
            return list(task.artifacts)
        needle = type.lower()
        return [a for a in task.artifacts if a.mime_type.lower().startswith(needle)]

    @keyword(name="Get Task Artifact Text")
    def get_task_artifact_text(self, task: Task, delimiter: str = "\n") -> str:
        """Concatenate text content of all artifacts on ``task``."""
        return delimiter.join(
            artifact_text(a, delimiter=delimiter) for a in task.artifacts
        )

    # ------------------------------------------------------------------
    # Trajectory
    # ------------------------------------------------------------------

    @keyword(name="Get Task Trajectory")
    def get_task_trajectory(self, task: Task) -> list[dict[str, Any]]:
        """Extract the tool-call sequence from ``task``.

        Returns a list of ``{"name": str, "arguments": dict}`` records
        suitable for :func:`AgentGuard.tool_calls.trajectory.match_sequence`
        (used by ``Tool Sequence Should Match``). Empty when the agent did
        not emit tool-call metadata.
        """
        return extract_a2a_trajectory(task)

    @keyword(name="Task Trajectory Should Match")
    def task_trajectory_should_match(
        self,
        task: Task,
        expected: list[str | dict[str, Any]],
        wildcards: bool = True,
    ) -> None:
        """Assert that ``task``'s tool-call trajectory matches ``expected``.

        Reuses the Phase 1 BFCL matcher (ADR-004) so MCP and SubAgent
        suites share one trajectory grammar.
        """
        actual = extract_a2a_trajectory(task)
        if not match_sequence(actual, expected, wildcards=wildcards):
            actual_names = [entry.get("name", "?") for entry in actual]
            raise AssertionError(
                f"Task {task.id} trajectory does not match. "
                f"Actual names: {actual_names}; expected length: {len(expected)}"
            )


# Backwards-compat alias used by ``DynamicCore`` registration in library.py.
SubAgentsLibrary = SubAgentsKeywords


__all__ = [
    "SubAgentsKeywords",
    "SubAgentsLibrary",
]
