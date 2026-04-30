"""Value objects for the Hooks module.

* :class:`HookEnvelope` — the canonical JSON-on-stdin payload Claude Code
  hands to a hook handler.
* :class:`HookDecision` — parsed result of a handler's stdout (or its
  exit-code-driven equivalent).
* :class:`HookResult` — the full record returned by
  :func:`AgentGuard.hooks.handlers.run_command_hook` and friends; holds the
  raw process IO plus the parsed decision so assertions can dig into either.

All dataclasses are ``frozen=True, slots=True`` to keep the surface immutable
and type-safe (mypy --strict clean).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

DecisionLiteral = Literal["block", "allow", "escalate", "approve", "deny"]


@dataclass(frozen=True, slots=True)
class HookEnvelope:
    """The canonical Claude Code JSON envelope passed on stdin to a hook.

    ``payload`` is the raw dict (kept for serialisation), while the typed
    fields are convenience accessors for the most-common keys.
    """

    event: str
    payload: dict[str, Any]
    session_id: str = ""
    transcript_path: str = ""
    cwd: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical dict shape Claude Code expects."""
        return dict(self.payload)


@dataclass(frozen=True, slots=True)
class HookDecision:
    """Parsed decision out of a hook handler.

    * ``decision`` is the high-level verb the test asserts on. Exit-code 2
      always maps to ``"block"`` regardless of stdout.
    * ``permission_decision`` is the finer-grained Claude Code field
      (``"allow" | "ask" | "deny"``).
    * ``additional_context`` carries the inline string Claude Code injects
      back into the model's context (per ``additional_context`` /
      ``injected_context`` keys in the official schema).
    * ``modified_tool_input`` is the (optional) replacement ``tool_input`` a
      ``PreToolUse`` hook may return.
    """

    decision: str = "allow"
    reason: str = ""
    permission_decision: str | None = None
    additional_context: str = ""
    modified_tool_input: dict[str, Any] | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class HookResult:
    """Full record of a handler invocation.

    Attributes mirror what a Robot test author needs to assert on:

    * ``exit_code`` — process exit (``2 == block`` in Claude Code semantics).
    * ``stdout`` / ``stderr`` — raw process IO (text).
    * ``decision`` — parsed :class:`HookDecision`.
    * ``handler`` — the handler reference (path / URL / callable repr).
    * ``handler_type`` — ``"command" | "http" | "prompt" | "agent"``.
    * ``duration_ms`` — wall-clock cost of the invocation.
    """

    handler: str
    handler_type: Literal["command", "http", "prompt", "agent"]
    exit_code: int
    stdout: str
    stderr: str
    decision: HookDecision
    duration_ms: float = 0.0

    @property
    def reason(self) -> str:
        """Convenience pass-through to ``decision.reason``."""
        return self.decision.reason

    @property
    def stop_hook_active(self) -> bool:
        """``True`` when the underlying envelope's stop_hook_active was set.

        This is set by :func:`AgentGuard.hooks.handlers.run_command_hook` on
        the ``raw`` dict so ``loop_detect`` can read it without the original
        envelope.
        """
        return bool(self.decision.raw.get("_stop_hook_active", False))


__all__ = ["HookEnvelope", "HookDecision", "HookResult", "DecisionLiteral"]
