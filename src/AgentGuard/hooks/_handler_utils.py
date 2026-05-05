"""Internal helpers shared by :mod:`AgentGuard.hooks.handlers`.

Kept private (leading underscore) because they're implementation detail of
the four handler types and not part of the public Hooks surface.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from AgentGuard.hooks.decision import parse_decision
from AgentGuard.hooks.exceptions import HookExecutionError
from AgentGuard.hooks.types import HookDecision


def resolve_command(handler: str | Path) -> str:
    """Resolve ``handler`` to an absolute, executable path or a PATH name.

    Raises :class:`HookExecutionError` if the file exists but is not
    executable, or if a relative path cannot be located.
    """
    handler_str = str(handler)
    candidate = Path(handler_str)
    if candidate.exists():
        resolved = candidate.resolve()
        if resolved.is_file() and not os.access(resolved, os.X_OK):
            raise HookExecutionError(f"Hook handler {resolved!s} is not executable (chmod +x missing).")
        return str(resolved)
    on_path = shutil.which(handler_str)
    if on_path is None:
        raise HookExecutionError(f"Hook handler {handler_str!r} not found on disk or PATH.")
    return on_path


def envelope_to_stdin(stdin: dict[str, Any] | str) -> str:
    return stdin if isinstance(stdin, str) else json.dumps(stdin)


def stop_hook_active(envelope: dict[str, Any] | str) -> bool:
    """Read ``stop_hook_active`` from a dict OR a JSON-string envelope."""
    if isinstance(envelope, dict):
        return bool(envelope.get("stop_hook_active", False))
    try:
        loaded = json.loads(envelope)
    except (json.JSONDecodeError, TypeError):
        return False
    if not isinstance(loaded, dict):
        return False
    return bool(loaded.get("stop_hook_active", False))


def annotate_decision(decision: HookDecision, envelope: dict[str, Any] | str) -> HookDecision:
    """Stamp the envelope's stop_hook_active onto decision.raw for loop_detect."""
    raw = dict(decision.raw)
    raw["_stop_hook_active"] = stop_hook_active(envelope)
    return HookDecision(
        decision=decision.decision,
        reason=decision.reason,
        permission_decision=decision.permission_decision,
        additional_context=decision.additional_context,
        modified_tool_input=decision.modified_tool_input,
        raw=raw,
    )


def status_to_exit_code(status: int) -> int:
    """Map HTTP status to Claude Code exit-code semantics (research §2.3)."""
    if status == 200:
        return 0
    if status == 403:
        return 2
    return 1


def resolve_agent(agent: Callable[..., Any] | str) -> Callable[..., Any]:
    """Resolve a callable / ``pkg.module:attr`` string to a callable."""
    if callable(agent):
        return agent
    if isinstance(agent, str) and ":" in agent:
        module_name, attr = agent.split(":", 1)
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            raise HookExecutionError(f"Agent hook import failed for {module_name!r}: {exc}") from exc
        if not hasattr(module, attr):
            raise HookExecutionError(f"Agent hook attribute {attr!r} not found in {module_name!r}.")
        resolved = getattr(module, attr)
        if not callable(resolved):
            raise HookExecutionError(f"Agent hook {agent!r} is not callable.")
        return resolved  # type: ignore[no-any-return]
    raise HookExecutionError(f"Agent hook must be a callable or 'pkg.module:attr' string; got {agent!r}.")


def coerce_agent_result(result: Any) -> tuple[str, HookDecision]:
    """Turn whatever the agent returned into ``(stdout, HookDecision)``."""
    if isinstance(result, HookDecision):
        return json.dumps(result.raw or {"decision": result.decision}), result
    if isinstance(result, dict):
        text = json.dumps(result)
        return text, parse_decision(text, exit_code=0)
    if isinstance(result, str):
        return result, parse_decision(result, exit_code=0)
    text = json.dumps({"decision": str(result)})
    return text, parse_decision(text, exit_code=0)


__all__ = [
    "annotate_decision",
    "coerce_agent_result",
    "envelope_to_stdin",
    "resolve_agent",
    "resolve_command",
    "status_to_exit_code",
    "stop_hook_active",
]
