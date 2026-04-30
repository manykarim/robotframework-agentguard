"""Public dataclasses for the SubAgents (A2A) bounded context (ADR-008).

These types are the only shape exchanged with other modules. The
pb-conversion helpers (``from_pb_*``) live in :mod:`subagents.types_pb`
and the JSON ↔ dataclass logic lives in :mod:`subagents.card`, so this
module imports neither ``a2a-sdk`` nor anything heavy at load time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

JSON = (
    str | int | float | bool | None | list["JSON"] | dict[str, "JSON"]
)
"""Recursive JSON-compatible value type used by artifact / message parts."""


# ---------------------------------------------------------------------------
# Task lifecycle states (A2A 1.0 spec, mirrored from a2a_pb2.TaskState)
# ---------------------------------------------------------------------------


class TaskStatus(StrEnum):
    """A2A 1.0 task lifecycle state (short JSON-RPC names)."""

    UNSPECIFIED = "unspecified"
    SUBMITTED = "submitted"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    INPUT_REQUIRED = "input_required"
    REJECTED = "rejected"
    AUTH_REQUIRED = "auth_required"

    @classmethod
    def from_str(cls, value: str | TaskStatus) -> TaskStatus:
        if isinstance(value, cls):
            return value
        normalised = value.lower().removeprefix("task_state_")
        try:
            return cls(normalised)
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError(f"unknown TaskStatus: {value!r}") from exc

    @property
    def is_terminal(self) -> bool:
        """True iff this state is final (no more transitions)."""
        return self in {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELED,
            TaskStatus.REJECTED,
        }


# ---------------------------------------------------------------------------
# AgentCard primitives
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class AgentSkill:
    """A skill advertised on an :class:`AgentCard` (A2A 1.0 §3.2)."""

    id: str
    name: str
    description: str = ""
    tags: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class AgentCapabilities:
    """Capability flags on the AgentCard (A2A 1.0 §3.3)."""

    streaming: bool = False
    push_notifications: bool = False
    extended_agent_card: bool = False


@dataclass(slots=True, frozen=True)
class AgentProvider:
    """Organisation publishing the agent (A2A 1.0 §3.4)."""

    organization: str = ""
    url: str = ""


@dataclass(slots=True, frozen=True)
class AgentInterface:
    """Transport-binding endpoint for the agent (A2A 1.0 §3.5)."""

    url: str
    protocol_binding: str = "jsonrpc"
    protocol_version: str = "1.0"
    tenant: str = ""


@dataclass(slots=True, frozen=True)
class AgentCard:
    """Discovery document published at ``/.well-known/agent.json`` (A2A 1.0 §3).

    Only the most-commonly-needed fields are first-class; the full SDK shape
    (security schemes, signatures, extensions, ...) is preserved verbatim
    in :attr:`extras` so callers can round-trip without losing data.
    """

    name: str
    description: str = ""
    version: str = "1.0"
    url: str = ""
    capabilities: AgentCapabilities = field(default_factory=AgentCapabilities)
    skills: tuple[AgentSkill, ...] = ()
    default_input_modes: tuple[str, ...] = ()
    default_output_modes: tuple[str, ...] = ()
    provider: AgentProvider | None = None
    supported_interfaces: tuple[AgentInterface, ...] = ()
    documentation_url: str = ""
    icon_url: str = ""
    extras: dict[str, JSON] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Render as a JSON-serialisable dict (A2A 1.0 wire shape)."""
        from AgentGuard.subagents.card import card_to_dict

        return card_to_dict(self)


# ---------------------------------------------------------------------------
# Message / Artifact / Task
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class MessagePart:
    """One part of a multimodal :class:`Message` (text / data / file)."""

    kind: str  # "text" | "data" | "file"
    text: str = ""
    data: dict[str, JSON] = field(default_factory=dict)
    media_type: str = ""
    metadata: dict[str, JSON] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class Message:
    """A single message in a task transcript (A2A 1.0 §4.2)."""

    role: str  # "user" | "agent" | "system"
    parts: tuple[MessagePart, ...] = ()
    message_id: str = ""
    metadata: dict[str, JSON] = field(default_factory=dict)
    # Tool-call sequence extracted from agent reasoning steps. Kept here so
    # SubAgents trajectory comparison can reuse the BFCL matcher (ADR-004).
    tool_calls: tuple[dict[str, JSON], ...] = ()


@dataclass(slots=True, frozen=True)
class Artifact:
    """Typed output produced by a task (A2A 1.0 §4.3).

    ``parts`` is structured the same way as :class:`Message.parts`, so a
    single helper (:func:`artifact_text`) can flatten either to plain text.
    """

    artifact_id: str
    name: str = ""
    description: str = ""
    parts: tuple[MessagePart, ...] = ()
    metadata: dict[str, JSON] = field(default_factory=dict)

    @property
    def mime_type(self) -> str:
        """Best-effort: first part's media type (A2A 1.0 default)."""
        for part in self.parts:
            if part.media_type:
                return part.media_type
        return "text/plain" if any(p.kind == "text" for p in self.parts) else ""


@dataclass
class Task:
    """A2A 1.0 task envelope.

    Mutable so the transport can update :attr:`status`, :attr:`messages`,
    and :attr:`artifacts` in place during ``Wait For Task Completion``.
    """

    id: str
    status: TaskStatus = TaskStatus.SUBMITTED
    context_id: str = ""
    messages: list[Message] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    metadata: dict[str, JSON] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    error: str | None = None  # populated when status == FAILED

    def touch(self) -> None:
        self.updated_at = datetime.now(UTC)


# ---------------------------------------------------------------------------
# Delegation chain (composite agents)
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class DelegationLink:
    """One edge of a multi-agent delegation chain (parent → child task)."""

    parent_task_id: str
    child_task_id: str
    agent_url: str
    agent_name: str = ""


@dataclass(slots=True, frozen=True)
class DelegationChain:
    """Ordered chain of :class:`DelegationLink` for trajectory assertions."""

    links: tuple[DelegationLink, ...] = ()

    def agent_names(self) -> list[str]:
        return [link.agent_name or link.agent_url for link in self.links]


# ---------------------------------------------------------------------------
# JSON ↔ dataclass conversion (thin shims; logic in :mod:`subagents.card`)
# ---------------------------------------------------------------------------


def from_dict_card(raw: dict[str, Any]) -> AgentCard:
    """Convert raw JSON (well-known/agent.json) → :class:`AgentCard`."""
    from AgentGuard.subagents.card import card_from_dict

    return card_from_dict(raw)


def card_to_json(card: AgentCard, *, indent: int | None = None) -> str:
    """Serialise an :class:`AgentCard` to JSON (well-known/agent.json shape)."""
    from AgentGuard.subagents.card import card_to_json as _impl

    return _impl(card, indent=indent)


# Legacy name kept for the pb-conversion module.
_card_from_dict = from_dict_card


# ---------------------------------------------------------------------------
# Helpers for tests / fixtures
# ---------------------------------------------------------------------------


def text_artifact(text: str, *, name: str = "result", artifact_id: str = "art-0") -> Artifact:
    """Convenience: build a single-text-part :class:`Artifact`."""
    return Artifact(
        artifact_id=artifact_id,
        name=name,
        parts=(MessagePart(kind="text", text=text, media_type="text/plain"),),
    )


def artifact_text(artifact: Artifact, delimiter: str = "\n") -> str:
    """Concatenate the text parts of an artifact (mirrors ``a2a.helpers.get_artifact_text``)."""
    return delimiter.join(p.text for p in artifact.parts if p.kind == "text" and p.text)


__all__ = [
    "JSON",
    "AgentCapabilities",
    "AgentCard",
    "AgentInterface",
    "AgentProvider",
    "AgentSkill",
    "Artifact",
    "DelegationChain",
    "DelegationLink",
    "Message",
    "MessagePart",
    "Task",
    "TaskStatus",
    "artifact_text",
    "card_to_json",
    "from_dict_card",
    "text_artifact",
]
