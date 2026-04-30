"""OpenAI Agents SDK bridge — Agent / Handoff / RunResult ↔ A2A.

Package: ``agents`` (``openai-agents`` on PyPI).

Primitives:

* ``Agent`` — has ``.name``, ``.instructions``, ``.tools``, ``.handoffs``
  (a list of ``Handoff`` or other ``Agent`` references).
* ``Runner.run(agent, input)`` returns a ``RunResult`` with:
  - ``.final_output`` — the terminal agent output,
  - ``.new_items`` — list of ``RunItem`` instances including
    ``ToolCallItem``, ``ToolCallOutputItem``, ``HandoffCallItem``,
    ``MessageOutputItem``,
  - ``.last_agent`` — the last agent that ran (handoff trace endpoint).
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


__all__ = ["OpenAIAgentsBridge"]

_INSTALL_HINT = (
    "pip install 'robotframework-agentguard[bridges]' or pip install openai-agents"
)


class OpenAIAgentsBridge:
    """Adapter for the OpenAI Agents SDK (``agents`` package)."""

    name = "openai_agents"

    @staticmethod
    def is_available() -> bool:
        return find_spec_any("agents")

    @staticmethod
    def to_agent_card(framework_obj: Any) -> AgentCard:
        """Build an ``AgentCard`` from an ``Agent``.

        Skills are the union of declared tools and handoff targets — both are
        delegable capabilities from the perspective of an external caller.
        """
        if not OpenAIAgentsBridge.is_available():
            raise BridgeUnavailable("openai_agents", _INSTALL_HINT)
        agent = framework_obj
        agent_name = getattr(agent, "name", None) or type(agent).__name__
        instructions = getattr(agent, "instructions", "") or ""

        skills: list[Any] = []
        for tool in getattr(agent, "tools", None) or []:
            tool_name = (
                getattr(tool, "name", None) or getattr(tool, "__name__", None) or "tool"
            )
            tool_desc = getattr(tool, "description", "") or getattr(
                tool, "__doc__", ""
            ) or ""
            skills.append(
                make_agent_skill(
                    skill_id=str(tool_name),
                    name=str(tool_name),
                    description=str(tool_desc).strip()[:500],
                    tags=["tool"],
                )
            )
        for handoff in getattr(agent, "handoffs", None) or []:
            target = getattr(handoff, "agent", handoff)
            target_name = getattr(target, "name", None) or type(target).__name__
            target_desc = getattr(target, "instructions", "") or ""
            skills.append(
                make_agent_skill(
                    skill_id=f"handoff:{target_name}",
                    name=str(target_name),
                    description=str(target_desc).strip()[:500],
                    tags=["handoff"],
                )
            )
        return make_agent_card(
            name=str(agent_name),
            description=str(instructions).strip()[:500],
            skills=skills,
        )

    @staticmethod
    def to_task(framework_obj_run_result: Any) -> Task:
        """Build a ``Task`` from a ``RunResult``.

        Presence of ``.final_output`` ⇒ COMPLETED. An exception on the result
        (``.error`` set) ⇒ FAILED.
        """
        if not OpenAIAgentsBridge.is_available():
            raise BridgeUnavailable("openai_agents", _INSTALL_HINT)
        from a2a.types import TaskState

        run_result = framework_obj_run_result
        if getattr(run_result, "error", None):
            task_state = TaskState.TASK_STATE_FAILED
        elif getattr(run_result, "final_output", None) is not None:
            task_state = TaskState.TASK_STATE_COMPLETED
        else:
            task_state = TaskState.TASK_STATE_WORKING

        last_agent = getattr(run_result, "last_agent", None)
        agent_name = getattr(last_agent, "name", "") if last_agent is not None else ""
        task_id = (
            getattr(run_result, "id", None)
            or f"openai-agents-{abs(hash(str(agent_name))) % (10**12)}"
        )
        return make_task(task_id=str(task_id), state=task_state)

    @staticmethod
    def extract_trajectory(framework_obj_run_result: Any) -> list[dict[str, Any]]:
        """Walk ``RunResult.new_items`` for tool calls and handoff calls."""
        if not OpenAIAgentsBridge.is_available():
            raise BridgeUnavailable("openai_agents", _INSTALL_HINT)
        run_result = framework_obj_run_result
        items = (
            getattr(run_result, "new_items", None)
            or getattr(run_result, "items", None)
            or []
        )
        out: list[dict[str, Any]] = []
        for item in items:
            entry = _item_to_trajectory_entry(item)
            if entry is not None:
                out.append(entry)
        return out

    @staticmethod
    def replay(framework_obj_run_result: Any) -> Any:
        """No replay primitive in the SDK; raise with a tracing-API hint."""
        raise NotImplementedError(
            "openai-agents has no replay API. Use the SDK's tracing module "
            "(`agents.tracing`) or re-run with the same input via Runner.run()."
        )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _item_to_trajectory_entry(item: Any) -> dict[str, Any] | None:
    """Map one ``RunItem`` to a BFCL-shaped entry, or None to skip."""
    item_type = type(item).__name__

    # ToolCallItem: .raw_item.function.name / .arguments  (Chat Completions shape)
    # or .raw_item.name / .raw_item.arguments  (Responses API shape).
    if item_type == "ToolCallItem":
        raw = getattr(item, "raw_item", None)
        if raw is None:
            return None
        function = getattr(raw, "function", None)
        if function is not None:
            fn_name = getattr(function, "name", None)
            fn_args = getattr(function, "arguments", None)
            return _make_entry(fn_name, fn_args)
        return _make_entry(getattr(raw, "name", None), getattr(raw, "arguments", None))

    # HandoffCallItem: a tool-call to a handoff function.
    if item_type == "HandoffCallItem":
        raw = getattr(item, "raw_item", None)
        function = getattr(raw, "function", None) if raw is not None else None
        if function is not None:
            name = getattr(function, "name", None)
            ho_args = getattr(function, "arguments", None)
            return _make_entry(f"handoff:{name}" if name else None, ho_args)
        if raw is not None:
            name = getattr(raw, "name", None)
            ho_args = getattr(raw, "arguments", None)
            return _make_entry(f"handoff:{name}" if name else None, ho_args)

    # Dict-shaped fallback (when callers pass already-serialised items).
    if isinstance(item, dict):
        kind = item.get("type", "")
        if kind in {"tool_call", "function_call"}:
            return _make_entry(item.get("name"), item.get("arguments"))
        if kind == "handoff_call":
            name = item.get("name")
            return _make_entry(f"handoff:{name}" if name else None, item.get("arguments"))

    return None


def _make_entry(name: Any, arguments: Any) -> dict[str, Any] | None:
    if name is None:
        return None
    return {"name": str(name), "arguments": _ensure_dict(arguments)}


def _ensure_dict(value: Any) -> dict[str, Any]:
    import json

    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}
