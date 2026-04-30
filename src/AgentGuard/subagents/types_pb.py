"""Conversion helpers between ``a2a-sdk`` protobuf messages and our dataclasses.

Kept in a separate module so :mod:`AgentGuard.subagents.types` only depends
on stdlib at import time. The ``a2a-sdk`` import is lazy (only happens
when one of these functions is actually called).
"""

from __future__ import annotations

from typing import Any

from AgentGuard.subagents.types import (
    JSON,
    AgentCard,
    Artifact,
    Message,
    MessagePart,
    Task,
    TaskStatus,
    _card_from_dict,
)


def _pb_state_to_status(state_int: int) -> TaskStatus:
    """Convert ``a2a_pb2.TaskState`` int → :class:`TaskStatus`."""
    from a2a.types import TaskState as _PbTaskState

    name = _PbTaskState.Name(state_int)
    return TaskStatus.from_str(name)


def from_pb_card(pb_card: Any) -> AgentCard:
    """Convert ``a2a.types.AgentCard`` protobuf message → dataclass."""
    from google.protobuf.json_format import MessageToDict

    raw = MessageToDict(pb_card, preserving_proto_field_name=True)
    return _card_from_dict(raw if isinstance(raw, dict) else {})


def from_pb_artifact(pb_artifact: Any) -> Artifact:
    """Convert ``a2a.types.Artifact`` → :class:`Artifact`."""
    parts = tuple(_part_from_pb(p) for p in pb_artifact.parts)
    return Artifact(
        artifact_id=pb_artifact.artifact_id,
        name=pb_artifact.name,
        description=pb_artifact.description,
        parts=parts,
        metadata=_struct_to_dict(pb_artifact.metadata),
    )


def from_pb_message(pb_message: Any) -> Message:
    """Convert ``a2a.types.Message`` → :class:`Message`."""
    role_raw = getattr(pb_message, "role", 0)
    # pb2 enum: ROLE_UNSPECIFIED=0, ROLE_USER=1, ROLE_AGENT=2
    role = {1: "user", 2: "agent"}.get(int(role_raw), "user")
    parts = tuple(_part_from_pb(p) for p in pb_message.parts)
    return Message(
        role=role,
        parts=parts,
        message_id=getattr(pb_message, "message_id", ""),
        metadata=_struct_to_dict(getattr(pb_message, "metadata", None)),
    )


def from_pb_task(pb_task: Any) -> Task:
    """Convert ``a2a.types.Task`` → :class:`Task`."""
    return Task(
        id=pb_task.id,
        status=_pb_state_to_status(int(pb_task.status.state)),
        context_id=getattr(pb_task, "context_id", ""),
        messages=[from_pb_message(m) for m in getattr(pb_task, "history", [])],
        artifacts=[from_pb_artifact(a) for a in getattr(pb_task, "artifacts", [])],
        metadata=_struct_to_dict(getattr(pb_task, "metadata", None)),
    )


def _part_from_pb(pb_part: Any) -> MessagePart:
    """Best-effort conversion of an A2A ``Part`` protobuf → :class:`MessagePart`."""
    which = getattr(pb_part, "WhichOneof", lambda _name: None)("part")
    if which == "text":
        return MessagePart(kind="text", text=pb_part.text, media_type="text/plain")
    if which == "data":
        return MessagePart(kind="data", data=_struct_to_dict(pb_part.data))
    if which == "file":
        return MessagePart(
            kind="file",
            data={"uri": getattr(pb_part.file, "uri", "")},
            media_type=getattr(pb_part.file, "mime_type", ""),
        )
    return MessagePart(kind="text", text="")


def _struct_to_dict(struct_msg: Any) -> dict[str, JSON]:
    if struct_msg is None:
        return {}
    try:
        from google.protobuf.json_format import MessageToDict

        out = MessageToDict(struct_msg, preserving_proto_field_name=True)
    except Exception:  # noqa: BLE001
        return {}
    return dict(out) if isinstance(out, dict) else {}


__all__ = [
    "from_pb_artifact",
    "from_pb_card",
    "from_pb_message",
    "from_pb_task",
]
