"""Helper library for SubAgents acceptance suites — bootstraps in-process
A2A agents (weather, places, travel_planner) and tears them down in
Suite Teardown so each .robot file starts from a clean registry.

Loaded as a Robot library; keywords are auto-discovered from public
module-level functions.
"""

from __future__ import annotations

from typing import Any

from AgentGuard.subagents import a2a_client, a2a_server
from AgentGuard.subagents.types import (
    Artifact,
    Message,
    MessagePart,
    Task,
    text_artifact,
)


def setup_travel_planner_agents() -> None:
    """Register weather + places + travel_planner in-process A2A agents."""
    a2a_server.reset_registry()

    a2a_server.start_server(
        "weather",
        handler=lambda msg: text_artifact(f"weather for {msg}: sunny, 22C"),
        skills=[{"id": "weather.lookup", "name": "Weather"}],
    )
    a2a_server.start_server(
        "places",
        handler=lambda msg: text_artifact(
            f"places near {msg}: Belém, Alfama, Jerónimos"
        ),
        skills=[{"id": "places.search", "name": "Places"}],
    )

    def planner_handler(msg: str) -> Artifact:
        weather = a2a_client.send_task("inproc://weather", msg)
        places = a2a_client.send_task("inproc://places", msg)
        weather_text = weather.artifacts[0].parts[0].text
        places_text = places.artifacts[0].parts[0].text
        return text_artifact(f"Plan: {weather_text} | {places_text}")

    a2a_server.start_server(
        "travel_planner",
        handler=planner_handler,
        skills=[{"id": "trip.plan", "name": "Trip Planner"}],
    )


def teardown_inproc_agents() -> None:
    """Forget every in-process server so the next suite starts clean."""
    a2a_server.reset_registry()


def inject_synthetic_trajectory(task: Task) -> None:
    """Append a synthetic agent message carrying tool_calls metadata.

    Real A2A agents emit this themselves; the in-process planner stays
    deterministic by having the test inject what we know was called.
    """
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
