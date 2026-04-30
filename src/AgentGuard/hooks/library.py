"""Robot Framework keyword surface for the Hooks bounded context.

ADR-007 — Composed into the top-level ``AgentGuard`` library via
``DynamicCore``. Each keyword is deterministic and works without an LLM API
key (prompt-handler keywords accept a mock provider).

Eleven keywords, covering all 12 Claude Code lifecycle events and the 4
handler types (command / http / prompt / agent).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from robot.api.deco import keyword

from AgentGuard.hooks import handlers
from AgentGuard.hooks.envelope import synthesize_envelope
from AgentGuard.hooks.exceptions import (
    HookDecisionError,
    HookLoopDetected,
)
from AgentGuard.hooks.loop_detect import detect_stop_loop
from AgentGuard.hooks.types import HookResult

if TYPE_CHECKING:  # pragma: no cover
    from AgentGuard.providers.base import LLMProviderAdapter


__all__ = ["HooksKeywords"]


class HooksKeywords:
    """Robot keywords for synthesising, running, and asserting on Claude Code hooks."""

    ROBOT_LIBRARY_SCOPE = "SUITE"

    def __init__(
        self,
        provider: LLMProviderAdapter | None = None,
        default_model: str | None = None,
    ) -> None:
        self._provider = provider
        self._default_model = default_model

    # ------------------------------------------------------------------
    # synthesis
    # ------------------------------------------------------------------

    @keyword(name="Synthesize Hook Input")
    def synthesize_hook_input(self, event: str, **fields: Any) -> dict[str, Any]:
        """Build the canonical Claude Code stdin JSON envelope for ``event``.

        Validates ``event`` against the 12 known lifecycle events. Caller
        kwargs override any default.
        """
        return synthesize_envelope(event, **fields)

    # ------------------------------------------------------------------
    # handlers (4 types)
    # ------------------------------------------------------------------

    @keyword(name="Run Hook Command")
    def run_hook_command(
        self,
        handler: str | Path,
        stdin: dict[str, Any] | str,
        env: dict[str, str] | None = None,
        timeout: float = handlers.DEFAULT_TIMEOUT,
    ) -> HookResult:
        """Run a shell-style hook handler (JSON-on-stdin, exit-2 = block)."""
        return handlers.run_command_hook(handler, stdin, env=env, timeout=timeout)

    @keyword(name="Run Hook HTTP")
    def run_hook_http(
        self,
        url: str,
        body: dict[str, Any],
        headers: dict[str, str] | None = None,
        timeout: float = handlers.DEFAULT_TIMEOUT,
    ) -> HookResult:
        """POST ``body`` to ``url`` (HTTP hook handler, new Feb 2026)."""
        return handlers.run_http_hook(url, body, headers=headers, timeout=timeout)

    @keyword(name="Run Hook Prompt")
    def run_hook_prompt(
        self,
        prompt: str,
        envelope: dict[str, Any],
        model: str | None = None,
    ) -> HookResult:
        """Ask the suite-level provider to evaluate the envelope."""
        return handlers.run_prompt_hook(
            prompt,
            envelope,
            provider=self._provider,
            model=model or self._default_model,
        )

    @keyword(name="Run Hook Agent")
    def run_hook_agent(
        self,
        agent_callable: Callable[..., Any] | str,
        envelope: dict[str, Any],
    ) -> HookResult:
        """Invoke a python callable or ``pkg.module:attr`` import-path agent hook."""
        return handlers.run_agent_hook(agent_callable, envelope)

    # ------------------------------------------------------------------
    # assertions (5)
    # ------------------------------------------------------------------

    @keyword(name="Hook Should Block")
    def hook_should_block(self, result: HookResult) -> HookResult:
        """Assert exit_code == 2 OR decision == "block"."""
        if result.exit_code == 2 or result.decision.decision == "block":
            return result
        raise HookDecisionError(
            f"Expected hook to block (exit=2 or decision='block'); got "
            f"exit={result.exit_code}, decision={result.decision.decision!r}, "
            f"reason={result.decision.reason!r}."
        )

    @keyword(name="Hook Should Allow")
    def hook_should_allow(self, result: HookResult) -> HookResult:
        """Assert exit_code == 0 AND decision != "block"."""
        if result.exit_code == 0 and result.decision.decision != "block":
            return result
        raise HookDecisionError(
            f"Expected hook to allow (exit=0 and decision != 'block'); got "
            f"exit={result.exit_code}, decision={result.decision.decision!r}, "
            f"reason={result.decision.reason!r}."
        )

    @keyword(name="Hook Decision Should Be")
    def hook_decision_should_be(
        self, result: HookResult, expected: str
    ) -> HookResult:
        """Assert ``result.decision.decision == expected`` (case-insensitive)."""
        actual = result.decision.decision.lower()
        wanted = expected.strip().lower()
        if actual == wanted:
            return result
        raise HookDecisionError(
            f"Expected decision={wanted!r}; got {actual!r} "
            f"(reason={result.decision.reason!r})."
        )

    @keyword(name="Hook Should Inject Context")
    def hook_should_inject_context(
        self, result: HookResult, contains: str
    ) -> HookResult:
        """Assert the hook returned an injected-context string containing ``contains``.

        Looks at ``decision.additional_context`` first; falls back to scanning
        the raw stdout payload for the substring (some handlers wrap the
        injection in custom keys).
        """
        haystack = result.decision.additional_context or ""
        if contains in haystack:
            return result
        # Tolerant fallback — scan the raw stdout JSON for the substring.
        if contains in (result.stdout or ""):
            return result
        raise HookDecisionError(
            f"Hook did not inject expected context: looking for {contains!r} "
            f"in additional_context={haystack!r} / stdout snippet={result.stdout[:200]!r}."
        )

    @keyword(name="Hook Should Modify Tool Input To")
    def hook_should_modify_tool_input_to(
        self, result: HookResult, expected_input: dict[str, Any]
    ) -> HookResult:
        """Assert the hook's modified_tool_input equals ``expected_input``."""
        actual = result.decision.modified_tool_input
        if actual is None:
            raise HookDecisionError(
                "Hook did not return a modified_tool_input field "
                f"(stdout snippet={result.stdout[:200]!r})."
            )
        if actual == expected_input:
            return result
        raise HookDecisionError(
            "Hook modified_tool_input mismatch:\n"
            f"  expected: {json.dumps(expected_input, sort_keys=True)}\n"
            f"  actual:   {json.dumps(actual, sort_keys=True)}"
        )

    # ------------------------------------------------------------------
    # loop detection
    # ------------------------------------------------------------------

    @keyword(name="Detect Stop Hook Loop")
    def detect_stop_hook_loop(
        self,
        events: Sequence[HookResult],
        window: int = 5,
    ) -> bool:
        """Detect ``stop_hook_active`` infinite-Stop antipatterns.

        Raises :class:`HookLoopDetected` when ``window`` consecutive results
        all return ``block`` while the envelope's ``stop_hook_active=True``.
        Returns ``False`` when no loop is detected.
        """
        detected = detect_stop_loop(events, window=window, raise_on_detect=False)
        if detected:
            raise HookLoopDetected(
                f"Detected Stop-hook loop: {window} consecutive blocks "
                f"with stop_hook_active=True."
            )
        return False
