"""AutoGen bridge — TeamChat / messages ↔ A2A.

AutoGen split into two top-level packages around 0.4:

* ``autogen_agentchat`` — the modern team / participant API.
  - ``BaseGroupChat`` / ``RoundRobinGroupChat`` etc. expose ``.name``
    and ``._participants`` (or ``.participants``).
* ``autogen`` (or ``autogen.agentchat``) — the legacy 0.2 API with
  ``ConversableAgent`` and ``GroupChat``.

The "run result" we adapt is either:

* a ``TaskResult`` from ``team.run(task=...)`` (carries ``.messages`` list and
  ``.stop_reason``), or
* a plain ``list[BaseChatMessage]`` from streaming.

Tool calls live on ``ToolCallRequestEvent``-shaped messages (modern) or in
``message.tool_calls`` (legacy).
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


__all__ = ["AutoGenBridge"]

_INSTALL_HINT = "pip install autogen-agentchat (or pyautogen for the 0.2 API)"


class AutoGenBridge:
    """Adapter for AutoGen teams / chats and their run results."""

    name = "autogen"

    @staticmethod
    def is_available() -> bool:
        return find_spec_any("autogen_agentchat", "autogen", "pyautogen")

    @staticmethod
    def to_agent_card(framework_obj: Any) -> AgentCard:
        """Build an ``AgentCard`` from a team or group chat object."""
        if not AutoGenBridge.is_available():
            raise BridgeUnavailable("autogen", _INSTALL_HINT)
        team = framework_obj
        team_name = getattr(team, "name", None) or type(team).__name__
        description = getattr(team, "description", "") or ""

        skills: list[Any] = []
        participants = (
            getattr(team, "participants", None)
            or getattr(team, "_participants", None)
            or getattr(team, "agents", None)  # legacy GroupChat
            or []
        )
        for participant in participants:
            agent_name = getattr(participant, "name", None) or type(participant).__name__
            agent_description = (
                getattr(participant, "description", None)
                or getattr(participant, "system_message", "")
                or ""
            )
            skills.append(
                make_agent_skill(
                    skill_id=str(agent_name),
                    name=str(agent_name),
                    description=str(agent_description)[:500],
                )
            )
        return make_agent_card(
            name=str(team_name),
            description=str(description),
            skills=skills,
        )

    @staticmethod
    def to_task(framework_obj_run_result: Any) -> Task:
        """Build a ``Task`` from a ``TaskResult`` or list of messages.

        State is mapped from ``stop_reason``: anything truthy ⇒ COMPLETED.
        Bare message lists are treated as COMPLETED (the call returned).
        """
        if not AutoGenBridge.is_available():
            raise BridgeUnavailable("autogen", _INSTALL_HINT)
        from a2a.types import TaskState

        run_result = framework_obj_run_result
        stop_reason = getattr(run_result, "stop_reason", None)
        messages = _autogen_messages(run_result)

        if stop_reason or messages:
            task_state = TaskState.TASK_STATE_COMPLETED
        else:
            task_state = TaskState.TASK_STATE_FAILED

        task_id = (
            getattr(run_result, "task_id", None)
            or getattr(run_result, "id", None)
            or f"autogen-{abs(hash(str(stop_reason))) % (10**12)}"
        )
        return make_task(task_id=str(task_id), state=task_state)

    @staticmethod
    def extract_trajectory(framework_obj_run_result: Any) -> list[dict[str, Any]]:
        """Walk AutoGen messages for tool-execution events."""
        if not AutoGenBridge.is_available():
            raise BridgeUnavailable("autogen", _INSTALL_HINT)
        run_result = framework_obj_run_result
        messages = _autogen_messages(run_result)
        out: list[dict[str, Any]] = []
        for msg in messages:
            for call in _autogen_tool_calls(msg):
                entry = _normalise_tool_call(call)
                if entry is not None:
                    out.append(entry)
        return out

    @staticmethod
    def replay(framework_obj_run_result: Any) -> Any:
        """AutoGen has no first-class replay; raise with a state-introspection hint."""
        raise NotImplementedError(
            "AutoGen does not ship a replay primitive. Inspect TaskResult.messages "
            "for state introspection, or persist + re-run the team manually."
        )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _autogen_messages(run_result: Any) -> list[Any]:
    if isinstance(run_result, list):
        return list(run_result)
    msgs = getattr(run_result, "messages", None)
    if msgs is None:
        msgs = getattr(run_result, "chat_history", None)
    return list(msgs or [])


def _autogen_tool_calls(msg: Any) -> list[Any]:
    # Modern: ToolCallRequestEvent.content is a list[FunctionCall].
    msg_type = type(msg).__name__
    if msg_type in {"ToolCallRequestEvent", "ToolCallExecutionEvent"}:
        content = getattr(msg, "content", None)
        if isinstance(content, list):
            return list(content)
    # Legacy ConversableAgent message dicts: {"tool_calls": [...]}
    if isinstance(msg, dict) and msg.get("tool_calls"):
        return list(msg["tool_calls"])
    direct = getattr(msg, "tool_calls", None)
    if direct:
        return list(direct)
    return []


def _normalise_tool_call(call: Any) -> dict[str, Any] | None:
    # Modern FunctionCall: .name + .arguments (str JSON)
    if hasattr(call, "name") and (hasattr(call, "arguments") or hasattr(call, "args")):
        raw_args = getattr(call, "arguments", None) or getattr(call, "args", None) or {}
        return {"name": str(call.name), "arguments": _ensure_dict(raw_args)}
    if isinstance(call, dict):
        if "name" in call:
            args = call.get("arguments") or call.get("args") or {}
            return {"name": str(call["name"]), "arguments": _ensure_dict(args)}
        function = call.get("function")
        if isinstance(function, dict) and "name" in function:
            return {
                "name": str(function["name"]),
                "arguments": _ensure_dict(function.get("arguments", {})),
            }
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
