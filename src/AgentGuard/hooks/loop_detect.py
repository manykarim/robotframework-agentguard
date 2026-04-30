"""Detect Stop-hook ``stop_hook_active`` infinite-loop antipatterns (ADR-007).

Per research §2.3, a Stop-hook that returns ``block`` even when the envelope
has ``stop_hook_active=True`` will cause Claude Code to loop forever (each
re-entry sees the active flag, the hook keeps blocking, ...). We detect this
by scanning a window of recent :class:`HookResult` records for that pattern.
"""

from __future__ import annotations

from collections.abc import Sequence

from AgentGuard.hooks.exceptions import HookLoopDetected
from AgentGuard.hooks.types import HookResult


def detect_stop_loop(
    results: Sequence[HookResult],
    window: int = 5,
    *,
    raise_on_detect: bool = False,
) -> bool:
    """Return ``True`` if a Stop-hook loop is detected within ``window``.

    The detection rule (per research §2.3): ``window`` consecutive results
    where the hook returns ``block`` *and* the envelope's
    ``stop_hook_active`` is ``True``. Once Claude Code sees a block while
    ``stop_hook_active`` is set, it keeps re-firing the hook with the flag
    still set — that is the canonical loop signature.

    Args:
        results: Recent hook invocation results, oldest-first.
        window: Number of consecutive offending results required to flag.
        raise_on_detect: When True, raise :class:`HookLoopDetected` instead
            of returning ``True``.
    """
    if window < 1:
        raise ValueError(f"window must be >= 1, got {window!r}")
    if len(results) < window:
        return False

    # Slide a window over the last len(results) entries; consecutive only.
    consecutive = 0
    for result in results:
        if result.decision.decision == "block" and result.stop_hook_active:
            consecutive += 1
            if consecutive >= window:
                if raise_on_detect:
                    raise HookLoopDetected(
                        f"Stop-hook loop: {window} consecutive blocks while "
                        f"stop_hook_active=True (handler={result.handler!r})."
                    )
                return True
        else:
            consecutive = 0

    return False


__all__ = ["detect_stop_loop"]
