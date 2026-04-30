"""LangGraph bridge — graph + checkpointer state ↔ A2A.

Shape of the LangGraph objects we adapt:

* **Graph**: a ``CompiledStateGraph`` (from ``graph.compile()``) — exposes
  ``.nodes`` (dict of node names → node spec) and an optional ``.config``
  carrying ``"name"`` and ``"thread_id"``.
* **State**: a ``StateSnapshot`` (returned by ``graph.get_state(config)``) —
  has ``.values`` (the dict of channel values, typically ``{"messages": [...]}``),
  ``.config`` with ``configurable.thread_id``, and ``.next`` (tuple of pending
  node names).

The trajectory is reconstructed from ``state.values["messages"]`` by walking
``tool_calls`` on each ``AIMessage`` (LangGraph reuses the LangChain message
schema).
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


__all__ = ["LangGraphBridge"]

_INSTALL_HINT = "pip install 'robotframework-agentguard[bridges]' or pip install langgraph"


class LangGraphBridge:
    """Adapter for LangGraph compiled graphs and state snapshots."""

    name = "langgraph"

    @staticmethod
    def is_available() -> bool:
        return find_spec_any("langgraph")

    @staticmethod
    def to_agent_card(framework_obj: Any) -> AgentCard:
        """Build an ``AgentCard`` from a compiled LangGraph.

        Skills are derived from the graph's node names (each node represents
        a delegable capability). The card name comes from
        ``graph.config["name"]`` if set, else the class name.
        """
        if not LangGraphBridge.is_available():
            raise BridgeUnavailable("langgraph", _INSTALL_HINT)
        graph = framework_obj
        config: dict[str, Any] = getattr(graph, "config", None) or {}
        card_name = config.get("name") or type(graph).__name__
        description = config.get("description", "") or getattr(graph, "__doc__", "") or ""

        skills: list[Any] = []
        nodes = getattr(graph, "nodes", None) or {}
        for node_name in nodes:
            # LangGraph reserves __start__ and __end__ as control nodes.
            if isinstance(node_name, str) and node_name.startswith("__"):
                continue
            skills.append(
                make_agent_skill(
                    skill_id=str(node_name),
                    name=str(node_name),
                    description=f"LangGraph node: {node_name}",
                )
            )
        return make_agent_card(
            name=str(card_name),
            description=str(description).strip(),
            skills=skills,
        )

    @staticmethod
    def to_task(framework_obj_run_result: Any) -> Task:
        """Build a ``Task`` from a LangGraph ``StateSnapshot``.

        Uses ``configurable.thread_id`` as the A2A task id; status is derived
        from ``state.next`` (empty tuple ⇒ ``COMPLETED``, non-empty ⇒
        ``WORKING``).
        """
        if not LangGraphBridge.is_available():
            raise BridgeUnavailable("langgraph", _INSTALL_HINT)
        from a2a.types import TaskState

        state = framework_obj_run_result
        config = _state_config(state)
        configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
        thread_id = configurable.get("thread_id") or config.get("thread_id") or ""

        next_nodes = getattr(state, "next", ()) or ()
        if next_nodes:
            task_state = TaskState.TASK_STATE_WORKING
        else:
            task_state = TaskState.TASK_STATE_COMPLETED

        return make_task(
            task_id=str(thread_id),
            state=task_state,
            context_id=str(thread_id),
        )

    @staticmethod
    def extract_trajectory(framework_obj_run_result: Any) -> list[dict[str, Any]]:
        """Walk ``state.values["messages"]`` for ``tool_calls``."""
        if not LangGraphBridge.is_available():
            raise BridgeUnavailable("langgraph", _INSTALL_HINT)
        state = framework_obj_run_result
        values: dict[str, Any] = getattr(state, "values", None) or {}
        messages = values.get("messages", []) if isinstance(values, dict) else []
        return _trajectory_from_messages(messages)

    @staticmethod
    def replay(framework_obj_run_result: Any) -> list[dict[str, Any]]:
        """Walk the graph's checkpointer to produce per-step Session-shaped frames.

        ``framework_obj_run_result`` may be:

        * a ``CompiledStateGraph`` (exposes ``get_state_history(config)``);
        * a ``StateSnapshot`` carrying ``.graph`` / ``._graph`` back-reference;
        * any object with a ``.checkpointer`` (``BaseCheckpointSaver``) and
          ``.config`` — we call ``checkpointer.list(config)``.

        Each yielded item is normalised to::

            {
              "checkpoint_id": str | None,
              "values":       dict,
              "next":         list[str],
              "messages":     list,
              "tool_calls":   list[{"name": str, "arguments": dict}],
            }

        which mirrors the canonical Session frame shape used by the Phase-3
        ``CodingAgent`` parser, so a LangGraph replay slots into the same
        downstream metric calculators as a Claude Code JSONL replay.
        """
        if not LangGraphBridge.is_available():
            raise BridgeUnavailable("langgraph", _INSTALL_HINT)

        state = framework_obj_run_result
        history = _resolve_state_history(state)

        frames: list[dict[str, Any]] = []
        for step in history:
            step_config = _state_config(step)
            configurable = (
                step_config.get("configurable", {})
                if isinstance(step_config, dict)
                else {}
            )
            values = getattr(step, "values", None) or {}
            values_dict: dict[str, Any] = values if isinstance(values, dict) else {}
            messages = values_dict.get("messages", []) if values_dict else []
            next_nodes = list(getattr(step, "next", ()) or ())
            frames.append(
                {
                    "checkpoint_id": configurable.get("checkpoint_id"),
                    "values": values_dict,
                    "next": next_nodes,
                    "messages": list(messages) if isinstance(messages, list) else [],
                    "tool_calls": _trajectory_from_messages(messages),
                }
            )
        return frames


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _state_config(state: Any) -> dict[str, Any]:
    cfg = getattr(state, "config", None)
    if isinstance(cfg, dict):
        return cfg
    return {}


def _resolve_state_history(state: Any) -> list[Any]:
    """Return an ordered list of ``StateSnapshot``-like steps from any LangGraph object.

    Three resolution paths, tried in order:

    1. The object is a compiled graph (``get_state_history`` on the object
       itself) — call ``state.get_state_history(state.config)``.
    2. The object is a ``StateSnapshot`` carrying a ``.graph`` / ``._graph``
       back-reference — delegate to the graph's ``get_state_history``.
    3. The object exposes a ``BaseCheckpointSaver`` on ``.checkpointer`` —
       call ``checkpointer.list(config)``.

    Raises :class:`BridgeUnavailable` when none of the above apply (LangGraph
    requires a checkpointer-bound graph for replay; an unbound graph cannot
    time-travel).
    """
    # Path 1: object exposes get_state_history directly (CompiledStateGraph).
    direct_history = getattr(state, "get_state_history", None)
    if callable(direct_history):
        config = _state_config(state)
        return list(direct_history(config))

    # Path 2: StateSnapshot with a graph back-reference.
    graph = getattr(state, "graph", None) or getattr(state, "_graph", None)
    if graph is not None:
        graph_history = getattr(graph, "get_state_history", None)
        if callable(graph_history):
            return list(graph_history(_state_config(state)))

    # Path 3: explicit checkpointer attribute.
    checkpointer = getattr(state, "checkpointer", None)
    if checkpointer is not None:
        list_fn = getattr(checkpointer, "list", None)
        if callable(list_fn):
            return list(list_fn(_state_config(state)))

    raise BridgeUnavailable(
        "langgraph",
        "LangGraph replay requires a checkpointer-bound graph "
        "(builder.compile(checkpointer=...)). "
        + _INSTALL_HINT,
    )


def _trajectory_from_messages(messages: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not messages:
        return out
    for msg in messages:
        tool_calls = _get_message_tool_calls(msg)
        for call in tool_calls:
            entry = _normalise_tool_call(call)
            if entry is not None:
                out.append(entry)
    return out


def _get_message_tool_calls(msg: Any) -> list[Any]:
    # LangChain AIMessage exposes .tool_calls; older versions used
    # additional_kwargs["tool_calls"]; dict-shaped messages mirror both.
    if isinstance(msg, dict):
        if msg.get("tool_calls"):
            return list(msg["tool_calls"])
        kwargs = msg.get("additional_kwargs") or {}
        return list(kwargs.get("tool_calls") or [])
    if hasattr(msg, "tool_calls") and msg.tool_calls:
        return list(msg.tool_calls)
    extra = getattr(msg, "additional_kwargs", None) or {}
    return list(extra.get("tool_calls") or [])


def _normalise_tool_call(call: Any) -> dict[str, Any] | None:
    """Coerce one LangChain/LangGraph tool_call entry to BFCL shape."""
    if isinstance(call, dict):
        # New-style: {"name": "...", "args": {...}, "id": "..."}
        if "name" in call:
            args = call.get("args") or call.get("arguments") or {}
            return {"name": str(call["name"]), "arguments": _ensure_dict(args)}
        # OpenAI-style envelope: {"function": {"name": ..., "arguments": "..."}}
        function = call.get("function")
        if isinstance(function, dict) and "name" in function:
            raw_args = function.get("arguments", {})
            return {
                "name": str(function["name"]),
                "arguments": _ensure_dict(raw_args),
            }
    name = getattr(call, "name", None)
    if name is not None:
        args = getattr(call, "args", None) or getattr(call, "arguments", None) or {}
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
