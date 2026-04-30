"""Composite in-process A2A agent fixture (research §6.4).

The "travel-planner" agent receives ``Plan a trip to <city>`` and delegates
to two child sub-agents:

* ``weather-agent`` — returns a synthetic weather string,
* ``places-agent`` — returns a list of recommended places.

It composes a final summary artifact and records the delegation chain in
:attr:`Artifact.metadata` so SubAgents tests can assert on it via
:class:`AgentGuard.subagents.types.DelegationChain`.

The handler also embeds a synthetic ``tool_calls`` trail in the artifact
metadata so :func:`AgentGuard.subagents.trajectory.extract_a2a_trajectory`
can match against the BFCL grammar (ADR-004); use
:func:`attach_tool_calls_to_messages` to copy it onto the agent message
before calling ``Get Task Trajectory``.
"""

from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any

from AgentGuard.subagents.a2a_server import ServerHandle, start_server
from AgentGuard.subagents.types import (
    Artifact,
    DelegationChain,
    DelegationLink,
    Message,
    text_artifact,
)

_CITY_RE = re.compile(r"trip\s+to\s+([A-Za-z][A-Za-z\s\-']+)", re.IGNORECASE)


def _weather_handler(message: str | dict[str, Any]) -> str:
    text = message if isinstance(message, str) else str(message.get("text", ""))
    city = _extract_city(text)
    return f"Weather in {city}: 22 C, sunny."


def _places_handler(message: str | dict[str, Any]) -> dict[str, Any]:
    text = message if isinstance(message, str) else str(message.get("text", ""))
    city = _extract_city(text)
    return {
        "city": city,
        "places": [f"{city} Old Town", f"{city} Central Park", f"{city} Museum"],
    }


def _extract_city(text: str) -> str:
    match = _CITY_RE.search(text)
    if match:
        return match.group(1).strip().split()[0]
    # Fall back to the last whitespace-separated token.
    parts = text.strip().split()
    return parts[-1] if parts else "unknown"


def make_travel_planner(
    name: str = "travel-planner",
    weather_name: str = "weather-agent",
    places_name: str = "places-agent",
) -> tuple[ServerHandle, ServerHandle, ServerHandle]:
    """Register the planner + two child agents; return ``(planner, weather, places)``."""
    weather = start_server(
        weather_name,
        _weather_handler,
        description="Returns synthetic weather for a city.",
        skills=[
            {
                "id": "weather.get",
                "name": "weather.get",
                "description": "Synthetic weather lookup.",
            }
        ],
        overwrite=True,
    )
    places = start_server(
        places_name,
        _places_handler,
        description="Returns recommended places for a city.",
        skills=[
            {
                "id": "places.recommend",
                "name": "places.recommend",
                "description": "Recommend tourist places.",
            }
        ],
        overwrite=True,
    )

    async def _planner_handler(message: str | dict[str, Any]) -> Artifact:
        text = message if isinstance(message, str) else str(message.get("text", ""))
        city = _extract_city(text)

        # Use the async submit path so we don't try to start a nested
        # asyncio.run inside the planner's own event loop.
        weather_task = await weather.server().submit_async(f"weather for {city}")
        places_task = await places.server().submit_async(f"places in {city}")

        weather_text = (
            "\n".join(p.text for art in weather_task.artifacts for p in art.parts if p.kind == "text") or "(no weather)"
        )
        places_data: dict[str, Any] = {}
        for art in places_task.artifacts:
            for p in art.parts:
                if p.kind == "data":
                    places_data = p.data
                    break

        tool_calls = (
            {
                "name": "delegate",
                "arguments": {
                    "agent": weather.name,
                    "task_id": weather_task.id,
                    "input": f"weather for {city}",
                },
            },
            {
                "name": "delegate",
                "arguments": {
                    "agent": places.name,
                    "task_id": places_task.id,
                    "input": f"places in {city}",
                },
            },
            {"name": "compose", "arguments": {"city": city}},
        )

        chain = DelegationChain(
            links=(
                DelegationLink(
                    parent_task_id="<self>",
                    child_task_id=weather_task.id,
                    agent_url=weather.url,
                    agent_name=weather.name,
                ),
                DelegationLink(
                    parent_task_id="<self>",
                    child_task_id=places_task.id,
                    agent_url=places.url,
                    agent_name=places.name,
                ),
            )
        )

        summary = f"Trip to {city}\n- {weather_text}\n- Suggested places: {', '.join(places_data.get('places', []))}"
        base = text_artifact(summary, name="trip.summary")

        return Artifact(
            artifact_id=base.artifact_id,
            name=base.name,
            description=base.description,
            parts=base.parts,
            metadata={
                "tool_calls": [dict(tc) for tc in tool_calls],
                "delegation_chain": [asdict(link) for link in chain.links],
                "city": city,
            },
        )

    planner = start_server(
        name,
        _planner_handler,
        description="Plans a trip by delegating to weather + places sub-agents.",
        skills=[
            {
                "id": "trip.plan",
                "name": "trip.plan",
                "description": "Compose a trip summary from weather + places sub-agents.",
                "tags": ["travel", "composite"],
                "examples": ["Plan a trip to Lisbon", "Plan a trip to Tokyo"],
            }
        ],
        overwrite=True,
    )
    return planner, weather, places


def attach_tool_calls_to_messages(
    task_messages: list[Message],
    artifact: Artifact,
) -> list[Message]:
    """Copy ``artifact.metadata['tool_calls']`` onto the last agent message.

    The :class:`AgentGuard.subagents.a2a_server.InProcessA2AServer` mirrors
    artifact text into a transcript message but cannot know about
    synthetic tool-call traces. Tests that want trajectory matching on
    composite agents call this after ``Send Task``.
    """
    tool_calls_raw = artifact.metadata.get("tool_calls", [])
    if not tool_calls_raw:
        return task_messages
    last_agent_idx = next(
        (i for i in range(len(task_messages) - 1, -1, -1) if task_messages[i].role == "agent"),
        None,
    )
    if last_agent_idx is None:
        return task_messages
    rebuilt = list(task_messages)
    msg = rebuilt[last_agent_idx]
    rebuilt[last_agent_idx] = Message(
        role=msg.role,
        parts=msg.parts,
        message_id=msg.message_id,
        metadata=msg.metadata,
        tool_calls=tuple(tool_calls_raw),
    )
    return rebuilt


def extract_delegation_chain(artifact: Artifact) -> DelegationChain:
    """Recover a :class:`DelegationChain` from the planner's artifact metadata."""
    raw = artifact.metadata.get("delegation_chain", [])
    if not isinstance(raw, list):
        return DelegationChain()
    links = tuple(
        DelegationLink(
            parent_task_id=str(item.get("parent_task_id", "")),
            child_task_id=str(item.get("child_task_id", "")),
            agent_url=str(item.get("agent_url", "")),
            agent_name=str(item.get("agent_name", "")),
        )
        for item in raw
        if isinstance(item, dict)
    )
    return DelegationChain(links=links)


__all__ = [
    "attach_tool_calls_to_messages",
    "extract_delegation_chain",
    "make_travel_planner",
]
