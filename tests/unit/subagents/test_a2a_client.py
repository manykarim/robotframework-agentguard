"""Unit tests for ``AgentGuard.subagents.a2a_client`` — sync facade + transports."""

from __future__ import annotations

from typing import Any

import pytest

from AgentGuard.subagents import a2a_client, a2a_server
from AgentGuard.subagents.exceptions import (
    AgentCardInvalid,
    TaskTimeout,
    TransportError,
)
from AgentGuard.subagents.types import (
    AgentCard,
    AgentInterface,
    AgentSkill,
    TaskStatus,
    text_artifact,
)


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    a2a_server.reset_registry()
    yield
    a2a_server.reset_registry()


# ---------------- transport resolution ----------------


def test_resolve_transport_inproc_auto() -> None:
    assert a2a_client._resolve_transport("inproc://x", "auto") == "memory"


def test_resolve_transport_http_auto() -> None:
    assert a2a_client._resolve_transport("http://x", "auto") == "http"
    assert a2a_client._resolve_transport("https://x", "auto") == "http"


def test_resolve_transport_explicit_wins() -> None:
    assert a2a_client._resolve_transport("https://x", "memory") == "memory"


def test_resolve_transport_unknown_scheme_raises() -> None:
    with pytest.raises(TransportError, match="cannot infer transport"):
        a2a_client._resolve_transport("ftp://x", "auto")


# ---------------- get_agent_card (inproc) ----------------


def test_get_agent_card_inproc() -> None:
    handle = a2a_server.start_server(
        "echo",
        handler=lambda msg: f"echo: {msg}",
        skills=[{"id": "echo", "name": "Echo"}],
    )
    card = a2a_client.get_agent_card(handle.url)
    assert card.name == "echo"
    assert card.skills[0].id == "echo"


def test_get_agent_card_unknown_inproc_raises() -> None:
    with pytest.raises(TransportError, match="no in-process A2A server"):
        a2a_client.get_agent_card("inproc://nope")


# ---------------- connect / send ----------------


def test_connect_and_send_inproc() -> None:
    a2a_server.start_server("planner", handler=lambda msg: "ok", skills=[{"id": "plan", "name": "p"}])
    handle = a2a_client.connect_to_a2a_agent("inproc://planner")
    assert handle.transport == "memory"
    task = a2a_client.send_task(handle, "Plan a trip")
    assert task.status == TaskStatus.COMPLETED
    assert task.artifacts


def test_connect_with_agent_card_object() -> None:
    a2a_server.start_server("p2", handler=lambda m: "x")
    card = AgentCard(name="p2", url="inproc://p2")
    handle = a2a_client.connect_to_a2a_agent(card)
    assert handle.transport == "memory"


def test_connect_card_no_url_raises() -> None:
    card = AgentCard(name="x")
    with pytest.raises(AgentCardInvalid, match="no url"):
        a2a_client.connect_to_a2a_agent(card)


def test_connect_card_uses_supported_interfaces() -> None:
    a2a_server.start_server("ifname", handler=lambda m: "x")
    card = AgentCard(
        name="x",
        supported_interfaces=(AgentInterface(url="inproc://ifname"),),
    )
    handle = a2a_client.connect_to_a2a_agent(card)
    assert handle.url == "inproc://ifname"


def test_send_task_with_string_target() -> None:
    a2a_server.start_server("st", handler=lambda m: "done")
    task = a2a_client.send_task("inproc://st", "go")
    assert task.status == TaskStatus.COMPLETED


def test_send_task_handler_raises_failed_status() -> None:
    def bad(msg: str) -> str:
        raise RuntimeError("kaboom")

    a2a_server.start_server("bad", handler=bad)
    task = a2a_client.send_task("inproc://bad", "trigger")
    assert task.status == TaskStatus.FAILED
    assert task.error and "kaboom" in task.error


# ---------------- wait / cancel ----------------


def test_wait_for_completion_already_terminal() -> None:
    a2a_server.start_server("done", handler=lambda m: "x")
    task = a2a_client.send_task("inproc://done", "go")
    same = a2a_client.wait_for_task_completion(None, task, timeout=1.0)
    assert same.status == TaskStatus.COMPLETED


def test_cancel_task_inproc() -> None:
    a2a_server.start_server("c", handler=lambda m: "x")
    handle = a2a_client.connect_to_a2a_agent("inproc://c")
    task = a2a_client.send_task(handle, "go")
    # already completed → cancel returns the terminal state unchanged
    cancelled = a2a_client.cancel_task(handle, task)
    assert cancelled.status in {TaskStatus.COMPLETED, TaskStatus.CANCELED}


# ---------------- in-process server primitives ----------------


def test_start_server_duplicate_raises() -> None:
    a2a_server.start_server("dup", handler=lambda m: "x")
    with pytest.raises(TransportError, match="already registered"):
        a2a_server.start_server("dup", handler=lambda m: "y")


def test_start_server_overwrite_replaces() -> None:
    a2a_server.start_server("ow", handler=lambda m: "first")
    handle = a2a_server.start_server("ow", handler=lambda m: "second", overwrite=True)
    task = a2a_client.send_task(handle.url, "x")
    text = task.artifacts[0].parts[0].text
    assert text == "second"


def test_list_servers_returns_names() -> None:
    a2a_server.start_server("a", handler=lambda m: "x")
    a2a_server.start_server("b", handler=lambda m: "y")
    assert "a" in a2a_server.list_servers()
    assert "b" in a2a_server.list_servers()


def test_lookup_server_for_url_invalid() -> None:
    with pytest.raises(TransportError, match="not an inproc"):
        a2a_server.lookup_server_for_url("https://x")


def test_async_handler_supported() -> None:
    async def handler(msg: str) -> str:
        return f"async: {msg}"

    handle = a2a_server.start_server("async", handler=handler)
    task = a2a_client.send_task(handle.url, "hi")
    assert task.status == TaskStatus.COMPLETED
    assert "async: hi" in task.artifacts[0].parts[0].text


def test_handler_returning_artifact_object() -> None:
    handle = a2a_server.start_server(
        "art", handler=lambda m: text_artifact("payload", artifact_id="art-7")
    )
    task = a2a_client.send_task(handle.url, "x")
    assert task.artifacts[0].artifact_id == "art-7"


def test_handler_returning_dict_makes_data_artifact() -> None:
    handle = a2a_server.start_server("d", handler=lambda m: {"answer": 42})
    task = a2a_client.send_task(handle.url, "q")
    assert task.artifacts[0].parts[0].kind == "data"
    assert task.artifacts[0].parts[0].data == {"answer": 42}
