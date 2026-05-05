"""Integration test: composite ``travel_planner`` agent that delegates to
``weather`` and ``places`` sub-agents and emits a BFCL-shape trajectory.

Validates the canonical research §6.4 ``Travel Planner Delegates Weather Lookup``
scenario without needing an LLM (handler is hand-written; LLM-driven version
lives in ``test_subagents_live.py``).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from AgentGuard.subagents import a2a_client, a2a_server
from AgentGuard.subagents.library import SubAgentsKeywords
from AgentGuard.subagents.types import (
    Artifact,
    Message,
    MessagePart,
    text_artifact,
)


@pytest.fixture(autouse=True)
def _registry() -> Iterator[None]:
    a2a_server.reset_registry()
    yield
    a2a_server.reset_registry()


@pytest.fixture
def travel_planner() -> str:
    """Spin up three in-process A2A agents: weather, places, travel_planner."""

    a2a_server.start_server(
        "weather",
        handler=lambda msg: text_artifact(f"weather for {msg}: sunny"),
        skills=[{"id": "weather.lookup", "name": "Weather"}],
    )
    a2a_server.start_server(
        "places",
        handler=lambda msg: text_artifact(f"places near {msg}: Belém, Alfama"),
        skills=[{"id": "places.search", "name": "Places"}],
    )

    def planner_handler(msg: str) -> Artifact:
        # Composite: delegate to weather and places sub-agents.
        weather_task = a2a_client.send_task("inproc://weather", msg)
        places_task = a2a_client.send_task("inproc://places", msg)
        weather_text = weather_task.artifacts[0].parts[0].text
        places_text = places_task.artifacts[0].parts[0].text
        return text_artifact(f"Plan: {weather_text} | {places_text}")

    a2a_server.start_server(
        "travel_planner",
        handler=planner_handler,
        skills=[{"id": "trip.plan", "name": "Trip Planner"}],
    )
    return "inproc://travel_planner"


def test_travel_planner_full_delegation(travel_planner: str) -> None:
    kw = SubAgentsKeywords()
    card = kw.get_agent_card(travel_planner)
    assert card.name == "travel_planner"

    task = kw.send_task(travel_planner, "Lisbon")
    kw.get_task_status(task, "==", "completed")

    text = kw.get_task_artifact_text(task)
    assert "weather" in text.lower()
    assert "places near Lisbon" in text


def test_travel_planner_subagent_servers_present(travel_planner: str) -> None:
    """Auxiliary check: weather and places are reachable independently."""
    assert "weather" in a2a_server.list_servers()
    assert "places" in a2a_server.list_servers()


def test_travel_planner_trajectory_shape(travel_planner: str) -> None:
    """Build an explicit trajectory by calling sub-agents directly and assert
    that ``Task Trajectory Should Match`` works against synthetic tool_calls."""
    kw = SubAgentsKeywords()
    task = kw.send_task(travel_planner, "Lisbon")
    # The default in-process planner doesn't auto-emit tool_calls; emulate
    # what a real A2A agent would post by injecting tool-call metadata into
    # the task message history.

    task.messages.append(
        Message(
            role="agent",
            parts=(MessagePart(kind="text", text="trajectory record"),),
            tool_calls=(
                {"name": "weather.lookup", "arguments": {"city": "Lisbon"}},
                {"name": "places.search", "arguments": {"city": "Lisbon"}},
            ),
        )
    )
    kw.task_trajectory_should_match(task, ["weather.lookup", "places.search"])
