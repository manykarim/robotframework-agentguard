"""Four handler types for Claude Code hooks: command, http, prompt, agent.

Per research §2.3 every Claude Code hook is one of:

* ``command`` — shell process; JSON on stdin, JSON-or-text on stdout, exit 2 = block.
* ``http`` — POST JSON to a URL (new Feb 2026); status code maps to exit code.
* ``prompt`` — LLM-evaluated; the test supplies the prompt + the envelope and
  we ask the configured provider to return a JSON decision.
* ``agent`` — a python callable (or ``module:attr`` import path) that takes
  the envelope and returns a decision.

Every handler returns a :class:`HookResult` so the keyword layer can apply the
same assertions regardless of handler type. Helpers live in
``_handler_utils`` to keep this file focused on the four entry points.
"""

from __future__ import annotations

import json
import os
import subprocess  # noqa: S404 — running user-supplied hook handlers is the point
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from AgentGuard.hooks._handler_utils import (
    annotate_decision,
    coerce_agent_result,
    envelope_to_stdin,
    resolve_agent,
    resolve_command,
    status_to_exit_code,
)
from AgentGuard.hooks.decision import parse_decision
from AgentGuard.hooks.exceptions import HookExecutionError
from AgentGuard.hooks.types import HookResult

DEFAULT_TIMEOUT: float = 30.0


def run_command_hook(
    handler: str | Path,
    envelope: dict[str, Any] | str,
    env: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> HookResult:
    """Run ``handler`` as a subprocess with JSON-on-stdin (Claude Code shape)."""
    resolved = resolve_command(handler)
    stdin_payload = envelope_to_stdin(envelope)
    started = time.perf_counter()
    try:
        completed = subprocess.run(  # noqa: S603 — handler is the test's responsibility
            [resolved],
            input=stdin_payload,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env if env is not None else os.environ.copy(),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise HookExecutionError(
            f"Hook handler {resolved!s} timed out after {timeout}s."
        ) from exc
    except OSError as exc:
        raise HookExecutionError(
            f"Hook handler {resolved!s} failed to execute: {exc}"
        ) from exc

    duration_ms = (time.perf_counter() - started) * 1000.0
    decision = annotate_decision(
        parse_decision(completed.stdout, completed.returncode), envelope
    )
    return HookResult(
        handler=str(handler),
        handler_type="command",
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        decision=decision,
        duration_ms=duration_ms,
    )


def run_http_hook(
    url: str,
    body: dict[str, Any],
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> HookResult:
    """POST ``body`` as JSON to ``url`` and translate the response."""
    started = time.perf_counter()
    try:
        response = httpx.post(url, json=body, headers=headers, timeout=timeout)
    except httpx.HTTPError as exc:
        raise HookExecutionError(f"HTTP hook to {url!r} failed: {exc}") from exc

    duration_ms = (time.perf_counter() - started) * 1000.0
    exit_code = status_to_exit_code(response.status_code)
    text = response.text or ""
    decision = annotate_decision(parse_decision(text, exit_code), body)
    return HookResult(
        handler=url,
        handler_type="http",
        exit_code=exit_code,
        stdout=text,
        stderr="",
        decision=decision,
        duration_ms=duration_ms,
    )


def run_prompt_hook(
    prompt: str,
    envelope: dict[str, Any],
    provider: Any,
    model: str | None = None,
) -> HookResult:
    """Ask ``provider`` to evaluate the envelope and return a JSON decision."""
    if provider is None:
        raise HookExecutionError(
            "run_prompt_hook requires a provider; pass one to HooksKeywords()."
        )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": json.dumps(envelope)},
    ]
    started = time.perf_counter()
    try:
        response = provider.chat(messages=messages, model=model)
    except Exception as exc:  # noqa: BLE001
        raise HookExecutionError(f"Prompt hook provider call failed: {exc}") from exc

    duration_ms = (time.perf_counter() - started) * 1000.0
    text = getattr(response, "text", "") or ""
    decision = parse_decision(text, exit_code=0)
    exit_code = 2 if decision.decision == "block" else 0
    decision = annotate_decision(decision, envelope)
    return HookResult(
        handler=f"prompt:{model or 'default'}",
        handler_type="prompt",
        exit_code=exit_code,
        stdout=text,
        stderr="",
        decision=decision,
        duration_ms=duration_ms,
    )


def run_agent_hook(
    agent_callable: Callable[..., Any] | str,
    envelope: dict[str, Any],
) -> HookResult:
    """Invoke a python callable / import-path with ``envelope``."""
    func = resolve_agent(agent_callable)
    started = time.perf_counter()
    try:
        raw = func(envelope)
    except Exception as exc:  # noqa: BLE001
        raise HookExecutionError(f"Agent hook raised: {exc}") from exc

    duration_ms = (time.perf_counter() - started) * 1000.0
    text, decision = coerce_agent_result(raw)
    exit_code = 2 if decision.decision == "block" else 0
    decision = annotate_decision(decision, envelope)
    handler_repr = (
        agent_callable
        if isinstance(agent_callable, str)
        else getattr(agent_callable, "__qualname__", repr(agent_callable))
    )
    return HookResult(
        handler=str(handler_repr),
        handler_type="agent",
        exit_code=exit_code,
        stdout=text,
        stderr="",
        decision=decision,
        duration_ms=duration_ms,
    )


__all__ = [
    "DEFAULT_TIMEOUT",
    "run_agent_hook",
    "run_command_hook",
    "run_http_hook",
    "run_prompt_hook",
]
