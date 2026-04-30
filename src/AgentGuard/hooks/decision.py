"""Parse a hook handler's stdout / exit-code into a :class:`HookDecision`.

Claude Code semantics (research §2.3):

* **Exit code 2** → block, regardless of stdout.
* JSON stdout with ``decision`` / ``permissionDecision`` / ``reason``
  drives finer-grained behaviour.
* Plain-text stdout with non-zero exit is a "warn" (we coerce to ``allow``
  with the text in ``reason`` so Robot tests can still inspect it).

The parser is tolerant: malformed JSON falls through to the plain-text path
and never raises, because a buggy handler should be assertable on, not
crash the test.
"""

from __future__ import annotations

import json
from typing import Any

from AgentGuard.hooks.types import HookDecision

# Keys we look at across the various Claude Code / OpenCode / Cline shapes.
_DECISION_KEYS: tuple[str, ...] = ("decision", "verdict", "action")
_PERMISSION_KEYS: tuple[str, ...] = ("permissionDecision", "permission_decision")
_CONTEXT_KEYS: tuple[str, ...] = (
    "additional_context",
    "additionalContext",
    "injected_context",
    "injectedContext",
    "context",
)
_MODIFIED_INPUT_KEYS: tuple[str, ...] = (
    "modified_tool_input",
    "modifiedToolInput",
    "tool_input",
)


def _first(payload: dict[str, Any], keys: tuple[str, ...]) -> Any | None:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def parse_decision(stdout: str, exit_code: int) -> HookDecision:
    """Parse a hook handler's output into a :class:`HookDecision`.

    Exit-code 2 short-circuits to ``block`` because that's the documented
    Claude Code semantics — even a JSON body with ``decision: "allow"`` does
    not override exit code 2.
    """
    text = (stdout or "").strip()

    # Try JSON first — even when exit code is 2 we still parse it so the
    # caller can read ``reason`` / ``additional_context``.
    payload: dict[str, Any] = {}
    if text.startswith("{") and text.endswith("}"):
        try:
            loaded = json.loads(text)
            if isinstance(loaded, dict):
                payload = loaded
        except json.JSONDecodeError:
            payload = {}

    decision_val = _first(payload, _DECISION_KEYS)
    permission_val = _first(payload, _PERMISSION_KEYS)
    reason_val = payload.get("reason", "")
    context_val = _first(payload, _CONTEXT_KEYS) or ""
    modified_input = _first(payload, _MODIFIED_INPUT_KEYS)

    # Coerce decision: exit 2 always wins.
    if exit_code == 2:
        decision = "block"
    elif isinstance(decision_val, str) and decision_val:
        decision = decision_val.lower()
    elif isinstance(permission_val, str) and permission_val.lower() == "deny":
        decision = "block"
    else:
        decision = "allow"

    if not isinstance(reason_val, str):
        reason_val = str(reason_val)
    if not isinstance(context_val, str):
        context_val = json.dumps(context_val)

    if modified_input is not None and not isinstance(modified_input, dict):
        modified_input = None

    return HookDecision(
        decision=decision,
        reason=reason_val,
        permission_decision=(permission_val.lower() if isinstance(permission_val, str) else None),
        additional_context=context_val,
        modified_tool_input=modified_input,
        raw=payload,
    )


__all__ = ["parse_decision"]
