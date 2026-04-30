"""Unit tests for ``AgentGuard.subagents.types`` — A2A 1.0 dataclasses + helpers."""

from __future__ import annotations

import json

import pytest

from AgentGuard.subagents.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentProvider,
    AgentSkill,
    Artifact,
    DelegationChain,
    DelegationLink,
    Message,
    MessagePart,
    Task,
    TaskStatus,
    artifact_text,
    card_to_json,
    from_dict_card,
    text_artifact,
)


# ---------------- TaskStatus ----------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("submitted", TaskStatus.SUBMITTED),
        ("WORKING", TaskStatus.WORKING),
        ("TASK_STATE_COMPLETED", TaskStatus.COMPLETED),
        ("task_state_failed", TaskStatus.FAILED),
        (TaskStatus.CANCELED, TaskStatus.CANCELED),
    ],
)
def test_task_status_from_str(raw: str | TaskStatus, expected: TaskStatus) -> None:
    assert TaskStatus.from_str(raw) is expected


def test_task_status_from_str_unknown_raises() -> None:
    with pytest.raises(ValueError, match="unknown TaskStatus"):
        TaskStatus.from_str("not-a-state")


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (TaskStatus.COMPLETED, True),
        (TaskStatus.FAILED, True),
        (TaskStatus.CANCELED, True),
        (TaskStatus.REJECTED, True),
        (TaskStatus.WORKING, False),
        (TaskStatus.SUBMITTED, False),
        (TaskStatus.AUTH_REQUIRED, False),
    ],
)
def test_task_status_terminal(status: TaskStatus, expected: bool) -> None:
    assert status.is_terminal is expected


# ---------------- AgentCard ----------------


def test_agent_card_defaults() -> None:
    card = AgentCard(name="test")
    assert card.version == "1.0"
    assert card.skills == ()
    assert card.capabilities == AgentCapabilities()
    assert card.provider is None


def test_agent_card_to_dict_minimal() -> None:
    card = AgentCard(name="t", description="d")
    d = card.to_dict()
    assert d["name"] == "t"
    assert d["description"] == "d"
    assert d["version"] == "1.0"
    assert d["capabilities"] == {
        "streaming": False,
        "push_notifications": False,
        "extended_agent_card": False,
    }


def test_agent_card_to_dict_full() -> None:
    card = AgentCard(
        name="planner",
        url="https://example/api",
        skills=(AgentSkill(id="weather.lookup", name="weather", tags=("ext",)),),
        provider=AgentProvider(organization="acme", url="https://acme"),
        documentation_url="https://docs",
        icon_url="https://icon.png",
    )
    d = card.to_dict()
    assert d["url"] == "https://example/api"
    assert d["skills"][0]["id"] == "weather.lookup"
    assert d["provider"]["organization"] == "acme"
    assert d["documentation_url"] == "https://docs"


def test_card_to_json_roundtrip() -> None:
    card = AgentCard(name="x", skills=(AgentSkill(id="s1", name="s"),))
    text = card_to_json(card)
    parsed = json.loads(text)
    assert parsed["name"] == "x"
    assert parsed["skills"][0]["id"] == "s1"


def test_from_dict_card_minimal() -> None:
    raw = {"name": "n", "version": "1.0", "skills": [{"id": "x", "name": "X"}]}
    card = from_dict_card(raw)
    assert card.name == "n"
    assert card.skills[0].id == "x"


def test_from_dict_card_extras_preserved() -> None:
    raw = {"name": "n", "custom_field": {"a": 1}}
    card = from_dict_card(raw)
    assert card.extras["custom_field"] == {"a": 1}


def test_from_dict_card_with_provider_and_interfaces() -> None:
    raw = {
        "name": "x",
        "provider": {"organization": "acme", "url": "https://acme"},
        "supported_interfaces": [
            {"url": "https://x", "protocol_binding": "grpc", "protocol_version": "2.0"}
        ],
    }
    card = from_dict_card(raw)
    assert card.provider is not None
    assert card.provider.organization == "acme"
    assert card.supported_interfaces[0].protocol_binding == "grpc"


# ---------------- Artifact / Message ----------------


def test_text_artifact_helper() -> None:
    art = text_artifact("hello", name="a", artifact_id="art-1")
    assert art.parts[0].text == "hello"
    assert art.mime_type == "text/plain"
    assert art.name == "a"


def test_artifact_text_concatenates() -> None:
    art = Artifact(
        artifact_id="x",
        parts=(
            MessagePart(kind="text", text="line1"),
            MessagePart(kind="text", text="line2"),
        ),
    )
    assert artifact_text(art) == "line1\nline2"


def test_artifact_mime_type_from_first_part() -> None:
    art = Artifact(
        artifact_id="x",
        parts=(MessagePart(kind="data", data={"k": 1}, media_type="application/json"),),
    )
    assert art.mime_type == "application/json"


def test_artifact_mime_type_default_when_missing() -> None:
    # No media_type but has text part → text/plain default.
    art = Artifact(artifact_id="x", parts=(MessagePart(kind="text", text="hi"),))
    assert art.mime_type == "text/plain"


def test_message_default_tool_calls_empty() -> None:
    msg = Message(role="user")
    assert msg.tool_calls == ()


# ---------------- Task ----------------


def test_task_default_status() -> None:
    task = Task(id="t1")
    assert task.status == TaskStatus.SUBMITTED
    assert task.messages == []
    assert task.artifacts == []


def test_task_touch_updates_timestamp() -> None:
    task = Task(id="t")
    before = task.updated_at
    task.touch()
    assert task.updated_at >= before


# ---------------- DelegationChain ----------------


def test_delegation_chain_agent_names() -> None:
    chain = DelegationChain(
        links=(
            DelegationLink(
                parent_task_id="p1", child_task_id="c1", agent_url="inproc://w", agent_name="weather"
            ),
            DelegationLink(parent_task_id="p1", child_task_id="c2", agent_url="inproc://places"),
        )
    )
    assert chain.agent_names() == ["weather", "inproc://places"]
