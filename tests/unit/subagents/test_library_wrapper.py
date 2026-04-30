"""Unit tests for ``SubAgentsKeywords`` — Robot keyword wrapper."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from AgentGuard.subagents import a2a_server
from AgentGuard.subagents.exceptions import (
    AgentCardInvalid,
    SubAgentError,
    TaskFailed,
)
from AgentGuard.subagents.library import SubAgentsKeywords
from AgentGuard.subagents.types import (
    AgentCard,
    AgentSkill,
    Task,
    TaskStatus,
)


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    a2a_server.reset_registry()
    yield
    a2a_server.reset_registry()


@pytest.fixture
def kw() -> SubAgentsKeywords:
    return SubAgentsKeywords()


# ---------------- discovery ----------------


def test_get_agent_card_inproc(kw: SubAgentsKeywords) -> None:
    a2a_server.start_server("p", handler=lambda m: "x", skills=[{"id": "s", "name": "S"}])
    card = kw.get_agent_card("inproc://p")
    assert card.name == "p"


def test_validate_agent_card_dict(kw: SubAgentsKeywords) -> None:
    card = kw.validate_agent_card({"name": "x", "version": "1.0", "url": "https://x"})
    assert isinstance(card, AgentCard)
    assert card.name == "x"


def test_validate_agent_card_json_string(kw: SubAgentsKeywords) -> None:
    raw = json.dumps({"name": "x", "url": "inproc://x"})
    card = kw.validate_agent_card(raw)
    assert card.name == "x"


def test_validate_agent_card_path(tmp_path: Path, kw: SubAgentsKeywords) -> None:
    p = tmp_path / "card.json"
    p.write_text(json.dumps({"name": "x", "url": "inproc://x"}))
    card = kw.validate_agent_card(p)
    assert card.name == "x"


def test_validate_agent_card_missing_name_raises(kw: SubAgentsKeywords) -> None:
    with pytest.raises(AgentCardInvalid, match="name"):
        kw.validate_agent_card({"version": "1.0", "url": "https://x"})


def test_validate_agent_card_missing_url_and_interfaces_raises(kw: SubAgentsKeywords) -> None:
    with pytest.raises(AgentCardInvalid, match="url"):
        kw.validate_agent_card({"name": "x"})


def test_validate_agent_card_skill_missing_id(kw: SubAgentsKeywords) -> None:
    with pytest.raises(AgentCardInvalid, match="skill"):
        kw.validate_agent_card(
            {
                "name": "x",
                "url": "inproc://x",
                "skills": [{"name": "s"}],  # missing id
            }
        )


def test_validate_agent_card_bad_input_type(kw: SubAgentsKeywords) -> None:
    with pytest.raises(AgentCardInvalid, match="unsupported"):
        kw.validate_agent_card(42)  # type: ignore[arg-type]


def test_validate_agent_card_invalid_json_string(kw: SubAgentsKeywords) -> None:
    with pytest.raises(AgentCardInvalid, match="not valid JSON"):
        kw.validate_agent_card("{not really json}")


def test_validate_agent_card_passthrough_AgentCard(kw: SubAgentsKeywords) -> None:
    card = AgentCard(name="x", url="inproc://x")
    out = kw.validate_agent_card(card)
    assert out is card


def test_list_agent_skills(kw: SubAgentsKeywords) -> None:
    card = AgentCard(
        name="x",
        url="inproc://x",
        skills=(AgentSkill(id="a", name="A"), AgentSkill(id="b", name="B")),
    )
    skills = kw.list_agent_skills(card)
    assert [s.id for s in skills] == ["a", "b"]


# ---------------- send / status ----------------


def test_send_task_inproc(kw: SubAgentsKeywords) -> None:
    a2a_server.start_server("st", handler=lambda m: "done")
    task = kw.send_task("inproc://st", "Plan a trip")
    assert task.status == TaskStatus.COMPLETED


def test_get_task_status_returns_string(kw: SubAgentsKeywords) -> None:
    task = Task(id="t", status=TaskStatus.WORKING)
    assert kw.get_task_status(task) == "working"


def test_task_should_have_status_pass(kw: SubAgentsKeywords) -> None:
    task = Task(id="t", status=TaskStatus.COMPLETED)
    kw.task_should_have_status(task, "completed")


def test_task_should_have_status_completed_mismatch_raises_failed(
    kw: SubAgentsKeywords,
) -> None:
    task = Task(id="t", status=TaskStatus.WORKING, error="oops")
    with pytest.raises(TaskFailed, match="expected status"):
        kw.task_should_have_status(task, "completed")


def test_task_should_have_status_other_mismatch_raises_subagenterror(
    kw: SubAgentsKeywords,
) -> None:
    task = Task(id="t", status=TaskStatus.COMPLETED)
    with pytest.raises(SubAgentError):
        kw.task_should_have_status(task, "working")


def test_task_should_have_status_accepts_enum(kw: SubAgentsKeywords) -> None:
    task = Task(id="t", status=TaskStatus.CANCELED)
    kw.task_should_have_status(task, TaskStatus.CANCELED)


# ---------------- artifacts ----------------


def test_get_task_artifact_no_filter(kw: SubAgentsKeywords) -> None:
    a2a_server.start_server("a", handler=lambda m: "out")
    task = kw.send_task("inproc://a", "go")
    artifacts = kw.get_task_artifact(task)
    assert len(artifacts) == 1


def test_get_task_artifact_text_filter(kw: SubAgentsKeywords) -> None:
    a2a_server.start_server("at", handler=lambda m: "hello")
    task = kw.send_task("inproc://at", "go")
    text_arts = kw.get_task_artifact(task, type="text")
    assert len(text_arts) == 1


def test_get_task_artifact_text_concatenates(kw: SubAgentsKeywords) -> None:
    a2a_server.start_server("attext", handler=lambda m: "hello")
    task = kw.send_task("inproc://attext", "go")
    text = kw.get_task_artifact_text(task)
    assert "hello" in text


# ---------------- trajectory ----------------


def test_get_task_trajectory_empty(kw: SubAgentsKeywords) -> None:
    task = Task(id="t")
    assert kw.get_task_trajectory(task) == []


def test_task_trajectory_should_match_simple(kw: SubAgentsKeywords) -> None:
    from AgentGuard.subagents.types import Message, MessagePart

    task = Task(id="t", status=TaskStatus.COMPLETED)
    task.messages = [
        Message(
            role="agent",
            parts=(MessagePart(kind="text", text="x"),),
            tool_calls=(
                {"name": "weather.lookup", "arguments": {}},
                {"name": "places.search", "arguments": {}},
            ),
        )
    ]
    # exact-name match should pass
    kw.task_trajectory_should_match(task, ["weather.lookup", "places.search"])


def test_task_trajectory_should_match_mismatch_raises(kw: SubAgentsKeywords) -> None:
    from AgentGuard.subagents.types import Message, MessagePart

    task = Task(id="t")
    task.messages = [
        Message(
            role="agent",
            parts=(MessagePart(kind="text", text="x"),),
            tool_calls=({"name": "x", "arguments": {}},),
        )
    ]
    with pytest.raises(AssertionError, match="does not match"):
        kw.task_trajectory_should_match(task, ["expected.tool"])
