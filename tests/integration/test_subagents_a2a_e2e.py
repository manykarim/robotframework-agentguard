"""Integration tests for SubAgents — in-memory A2A roundtrip.

Spins an in-process A2A server, drives a full submit → wait → assert flow
through the public ``SubAgentsKeywords`` surface.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from AgentGuard.subagents import a2a_server
from AgentGuard.subagents.exceptions import TaskFailed
from AgentGuard.subagents.library import SubAgentsKeywords
from AgentGuard.subagents.types import text_artifact


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    a2a_server.reset_registry()
    yield
    a2a_server.reset_registry()


@pytest.fixture
def kw() -> SubAgentsKeywords:
    return SubAgentsKeywords()


def test_a2a_inproc_full_lifecycle(kw: SubAgentsKeywords) -> None:
    """Get card → connect → send → wait → status → artifact."""
    a2a_server.start_server(
        "echo",
        handler=lambda msg: f"echoed: {msg}",
        skills=[{"id": "echo.v1", "name": "Echo"}],
        description="Echoes everything",
    )
    card = kw.get_agent_card("inproc://echo")
    assert card.name == "echo"
    skills = kw.list_agent_skills(card)
    assert skills[0].id == "echo.v1"

    handle = kw.connect_to_a2a_agent("inproc://echo")
    task = kw.send_task(handle, "hello world")
    completed = kw.wait_for_task_completion(task, handle, timeout=5.0)
    kw.task_should_have_status(completed, "completed")

    text = kw.get_task_artifact_text(completed)
    assert "echoed: hello world" in text


def test_a2a_failed_task_raises_taskfailed(kw: SubAgentsKeywords) -> None:
    def boom(msg: str) -> str:
        raise RuntimeError("downstream broken")

    a2a_server.start_server("bad", handler=boom)
    task = kw.send_task("inproc://bad", "hi")
    with pytest.raises(TaskFailed, match="failed"):
        kw.task_should_have_status(task, "completed")


def test_a2a_get_artifact_text_filter(kw: SubAgentsKeywords) -> None:
    a2a_server.start_server("json", handler=lambda msg: {"answer": 42})
    task = kw.send_task("inproc://json", "?")
    json_arts = kw.get_task_artifact(task, type="application/json")
    assert len(json_arts) == 1


def test_a2a_validate_card_works_e2e(kw: SubAgentsKeywords) -> None:
    a2a_server.start_server(
        "v",
        handler=lambda m: "ok",
        skills=[{"id": "x", "name": "X"}],
    )
    card = kw.get_agent_card("inproc://v")
    validated = kw.validate_agent_card(card)
    assert validated.name == "v"


def test_a2a_card_to_json_string_roundtrip(kw: SubAgentsKeywords) -> None:
    """A card serialised to JSON can be re-validated."""
    a2a_server.start_server("rt", handler=lambda m: "x")
    card = kw.get_agent_card("inproc://rt")
    from AgentGuard.subagents.types import card_to_json

    text = card_to_json(card)
    revalidated = kw.validate_agent_card(text)
    assert revalidated.name == "rt"


def test_a2a_handler_returning_artifact_object(kw: SubAgentsKeywords) -> None:
    a2a_server.start_server(
        "art-out",
        handler=lambda m: text_artifact("custom artifact body", artifact_id="my-art"),
    )
    task = kw.send_task("inproc://art-out", "?")
    artifacts = kw.get_task_artifact(task)
    assert artifacts[0].artifact_id == "my-art"
