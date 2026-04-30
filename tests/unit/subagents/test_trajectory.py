"""Unit tests for ``AgentGuard.subagents.trajectory`` — A2A trajectory extract."""

from __future__ import annotations

from AgentGuard.subagents.trajectory import (
    extract_a2a_trajectory,
    message_dicts,
    trajectory_names,
)
from AgentGuard.subagents.types import Message, MessagePart, Task


def _task_with_calls(*calls_per_message: tuple[dict, ...]) -> Task:
    task = Task(id="t1")
    for tcs in calls_per_message:
        task.messages.append(
            Message(
                role="agent",
                parts=(MessagePart(kind="text", text="x"),),
                tool_calls=tcs,
            )
        )
    return task


def test_extract_trajectory_empty_task() -> None:
    task = Task(id="t1")
    assert extract_a2a_trajectory(task) == []


def test_extract_trajectory_simple_call() -> None:
    task = _task_with_calls(
        ({"name": "weather.lookup", "arguments": {"city": "Lisbon"}},),
    )
    out = extract_a2a_trajectory(task)
    assert out == [{"name": "weather.lookup", "arguments": {"city": "Lisbon"}}]


def test_extract_trajectory_multiple_messages_preserve_order() -> None:
    task = _task_with_calls(
        ({"name": "weather.lookup", "arguments": {"city": "Lisbon"}},),
        ({"name": "places.search", "arguments": {"q": "museum"}},),
    )
    names = trajectory_names(task)
    assert names == ["weather.lookup", "places.search"]


def test_extract_trajectory_skips_invalid_entries() -> None:
    task = _task_with_calls(
        (
            {"name": "valid", "arguments": {}},
            {"no_name": True},  # skipped
            "not-a-dict",  # skipped
        ),
    )
    out = extract_a2a_trajectory(task)
    assert [c["name"] for c in out] == ["valid"]


def test_extract_trajectory_openai_function_envelope() -> None:
    task = _task_with_calls(
        ({"function": {"name": "weather.lookup", "arguments": '{"city": "Paris"}'}},),
    )
    out = extract_a2a_trajectory(task)
    assert out[0]["name"] == "weather.lookup"
    assert out[0]["arguments"] == {"city": "Paris"}


def test_extract_trajectory_string_arguments_parsed() -> None:
    task = _task_with_calls(
        ({"name": "x", "arguments": '{"a": 1}'},),
    )
    out = extract_a2a_trajectory(task)
    assert out[0]["arguments"] == {"a": 1}


def test_extract_trajectory_invalid_json_arguments_become_empty() -> None:
    task = _task_with_calls(
        ({"name": "x", "arguments": "not json"},),
    )
    out = extract_a2a_trajectory(task)
    assert out[0]["arguments"] == {}


def test_message_dicts_round_trips() -> None:
    msgs = [
        Message(role="user", tool_calls=({"name": "a", "arguments": {}},)),
        Message(role="agent", tool_calls=({"name": "b", "arguments": {"k": 1}},)),
    ]
    out = message_dicts(msgs)
    assert out[0]["role"] == "user"
    assert out[0]["tool_calls"][0]["name"] == "a"
    assert out[1]["tool_calls"][0]["arguments"] == {"k": 1}
