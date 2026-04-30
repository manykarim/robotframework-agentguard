"""CrewAI bridge — Crew/Agent/Task ↔ A2A.

CrewAI's primitives:

* ``Crew`` — has ``.name``, ``.agents`` (list of ``Agent``), ``.tasks``
  (list of ``Task``).
* ``Agent`` — has ``.role``, ``.goal``, ``.backstory``, ``.tools``.
* ``CrewOutput`` — return value of ``crew.kickoff()``; carries ``.tasks_output``
  (list of ``TaskOutput``) and ``.raw`` final string.
* ``TaskOutput`` — has ``.agent`` (role string), ``.raw``, and on newer
  versions ``.tool_calls`` / ``.json_dict``.

Replay: CrewAI exposes ``crew.replay(task_id=...)`` since 0.30+; we surface a
helper that returns a callable rather than executing the replay (callers
control side-effects).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from AgentGuard.subagents.bridges.base import (
    BridgeUnavailable,
    find_spec_any,
    make_agent_card,
    make_agent_skill,
    make_task,
)

if TYPE_CHECKING:  # pragma: no cover
    from a2a.types import AgentCard, Task


__all__ = ["CrewAIBridge"]

_INSTALL_HINT = "pip install 'robotframework-agentguard[bridges]' or pip install crewai"


class CrewAIBridge:
    """Adapter for CrewAI ``Crew`` and ``CrewOutput`` objects."""

    name = "crewai"

    @staticmethod
    def is_available() -> bool:
        return find_spec_any("crewai")

    @staticmethod
    def to_agent_card(framework_obj: Any) -> AgentCard:
        """Build an ``AgentCard`` from a ``Crew``.

        Each ``Agent`` in the crew becomes one skill (id=role, description=goal).
        """
        if not CrewAIBridge.is_available():
            raise BridgeUnavailable("crewai", _INSTALL_HINT)
        crew = framework_obj
        crew_name = getattr(crew, "name", None) or type(crew).__name__
        description = getattr(crew, "description", "") or ""

        skills: list[Any] = []
        agents = getattr(crew, "agents", None) or []
        for agent in agents:
            role = getattr(agent, "role", None) or "agent"
            goal = getattr(agent, "goal", "") or ""
            skills.append(
                make_agent_skill(
                    skill_id=str(role),
                    name=str(role),
                    description=str(goal),
                )
            )
        return make_agent_card(
            name=str(crew_name),
            description=str(description),
            skills=skills,
        )

    @staticmethod
    def to_task(framework_obj_run_result: Any) -> Task:
        """Build a ``Task`` from a ``CrewOutput``.

        Status is derived from ``.tasks_output``: every entry needs a non-empty
        ``.raw`` to count as completed; otherwise marked WORKING.
        """
        if not CrewAIBridge.is_available():
            raise BridgeUnavailable("crewai", _INSTALL_HINT)
        from a2a.types import TaskState

        crew_output = framework_obj_run_result
        task_id = (
            getattr(crew_output, "task_id", None)
            or getattr(crew_output, "id", None)
            or _crew_output_id(crew_output)
        )
        tasks_output = getattr(crew_output, "tasks_output", None) or []
        if tasks_output and all(getattr(t, "raw", None) for t in tasks_output):
            task_state = TaskState.TASK_STATE_COMPLETED
        elif tasks_output:
            task_state = TaskState.TASK_STATE_WORKING
        else:
            task_state = TaskState.TASK_STATE_FAILED

        return make_task(task_id=str(task_id), state=task_state)

    @staticmethod
    def extract_trajectory(framework_obj_run_result: Any) -> list[dict[str, Any]]:
        """Walk each ``TaskOutput.tool_calls`` (when present) for trajectory entries."""
        if not CrewAIBridge.is_available():
            raise BridgeUnavailable("crewai", _INSTALL_HINT)
        crew_output = framework_obj_run_result
        out: list[dict[str, Any]] = []
        tasks_output = getattr(crew_output, "tasks_output", None) or []
        for task_output in tasks_output:
            for call in _crewai_task_tool_calls(task_output):
                entry = _normalise_tool_call(call)
                if entry is not None:
                    out.append(entry)
        return out

    @staticmethod
    def replay(framework_obj_run_result: Any) -> list[dict[str, Any]]:
        """Use ``Crew.replay()`` to produce per-task Session-shaped frames.

        ``framework_obj_run_result`` may be:

        * a ``Crew`` (``hasattr(crew, "replay")``) — we invoke
          ``crew.replay(task_id=<last>)`` and walk the resulting
          ``CrewOutput.tasks_output``;
        * a ``CrewOutput`` — we walk its existing ``.tasks_output`` directly,
          falling back to the parent crew's replay when the output is empty;
        * a plain list of ``TaskOutput`` — walked verbatim.

        Each frame normalises to::

            {
              "task_id":    str | None,
              "agent":      str | None,   # role label
              "raw":        str | None,   # final task output text
              "tool_calls": list[{"name": str, "arguments": dict}],
            }

        which mirrors the canonical Session frame shape used by Phase-3
        ``CodingAgent`` parsers, so a CrewAI replay slots into the same
        downstream metric calculators as a Claude Code JSONL replay.
        """
        if not CrewAIBridge.is_available():
            raise BridgeUnavailable("crewai", _INSTALL_HINT)

        tasks_output = _resolve_crew_tasks_output(framework_obj_run_result)

        frames: list[dict[str, Any]] = []
        for task_output in tasks_output:
            task_id = (
                getattr(task_output, "task_id", None)
                or getattr(task_output, "id", None)
                or getattr(task_output, "name", None)
            )
            agent = getattr(task_output, "agent", None)
            raw = getattr(task_output, "raw", None)
            calls = [
                entry
                for call in _crewai_task_tool_calls(task_output)
                if (entry := _normalise_tool_call(call)) is not None
            ]
            frames.append(
                {
                    "task_id": task_id,
                    "agent": agent,
                    "raw": raw,
                    "tool_calls": calls,
                }
            )
        return frames


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _crew_output_id(crew_output: Any) -> str:
    raw = getattr(crew_output, "raw", "")
    return f"crewai-{abs(hash(str(raw))) % (10**12)}"


def _resolve_crew_tasks_output(obj: Any) -> list[Any]:
    """Coerce ``Crew`` / ``CrewOutput`` / list-of-``TaskOutput`` to a flat list.

    For a ``Crew`` we invoke ``crew.replay(task_id=...)`` and walk the
    returned ``CrewOutput``. The ``task_id`` argument is best-effort: callers
    can stash ``crew._last_task_id`` on the crew before kickoff; otherwise we
    fall back to the last task on ``crew.tasks`` (mirrors the CLI's
    ``crewai replay`` selection logic).
    """
    # Crew object — needs replay invocation.
    if hasattr(obj, "replay") and not hasattr(obj, "tasks_output"):
        task_id = getattr(obj, "_last_task_id", None)
        if task_id is None:
            tasks = getattr(obj, "tasks", None) or []
            if tasks:
                last = tasks[-1]
                task_id = getattr(last, "id", None) or getattr(last, "name", None)
        try:
            replayed = obj.replay(task_id=task_id) if task_id else obj.replay()
        except TypeError:
            # Older CrewAI signatures may not accept task_id kw.
            replayed = obj.replay()
        return list(getattr(replayed, "tasks_output", None) or [])

    # CrewOutput — walk tasks_output directly.
    direct = getattr(obj, "tasks_output", None)
    if direct is not None:
        return list(direct)

    # Bare iterable of TaskOutput.
    if isinstance(obj, list):
        return list(obj)

    return []


def _crewai_task_tool_calls(task_output: Any) -> list[Any]:
    # Newer CrewAI: TaskOutput.tool_calls is a list of dicts.
    direct = getattr(task_output, "tool_calls", None)
    if direct:
        return list(direct)
    # Some versions tuck them under .pydantic.tool_calls or .json_dict.
    for attr in ("pydantic", "json_dict"):
        nested = getattr(task_output, attr, None)
        if isinstance(nested, dict) and nested.get("tool_calls"):
            return list(nested["tool_calls"])
    return []


def _normalise_tool_call(call: Any) -> dict[str, Any] | None:
    if isinstance(call, dict):
        if "name" in call:
            args = call.get("arguments") or call.get("args") or call.get("input") or {}
            return {"name": str(call["name"]), "arguments": _ensure_dict(args)}
        if "tool" in call:
            args = call.get("arguments") or call.get("input") or {}
            return {"name": str(call["tool"]), "arguments": _ensure_dict(args)}
    name = getattr(call, "name", None) or getattr(call, "tool", None)
    if name is not None:
        args = (
            getattr(call, "arguments", None)
            or getattr(call, "args", None)
            or getattr(call, "input", None)
            or {}
        )
        return {"name": str(name), "arguments": _ensure_dict(args)}
    return None


def _ensure_dict(value: Any) -> dict[str, Any]:
    import json

    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}
