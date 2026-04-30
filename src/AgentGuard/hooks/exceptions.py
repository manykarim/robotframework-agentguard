"""Exception hierarchy for the Hooks module.

All hook keyword failures derive from :class:`HookError`, mirroring the
``SecurityError`` pattern in :mod:`AgentGuard.security.types` so suite-level
``except`` clauses can opt into a single base.
"""

from __future__ import annotations


class HookError(Exception):
    """Base class for every hooks keyword failure."""


class HookExecutionError(HookError):
    """A handler failed to execute (non-zero unexpected exit, missing exec bit,
    transport failure, timeout, etc.)."""


class HookValidationError(HookError):
    """The hook envelope or response could not be validated against the
    canonical Claude Code schema (unknown event, malformed JSON, ...)."""


class HookDecisionError(HookError):
    """An assertion about a hook decision (block/allow/escalate/inject) failed."""


class HookLoopDetected(HookError):  # noqa: N818 — domain-language verb fits the API better than `Error`
    """A Stop-hook ``stop_hook_active`` infinite loop was detected.

    Raised by :func:`AgentGuard.hooks.loop_detect.detect_stop_loop` and surfaced
    by the ``Detect Stop Hook Loop`` keyword.
    """


__all__ = [
    "HookError",
    "HookExecutionError",
    "HookValidationError",
    "HookDecisionError",
    "HookLoopDetected",
]
