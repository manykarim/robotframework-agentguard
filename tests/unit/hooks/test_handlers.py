"""Unit tests for ``AgentGuard.hooks.handlers`` — 4 handler types.

Covers command / http / prompt / agent handlers.

* ``run_command_hook``: subprocess fixture scripts (block / allow / inject).
* ``run_http_hook``: monkeypatch ``httpx.post`` to fake the wire.
* ``run_prompt_hook``: uses the suite-level ``mock_provider`` fixture.
* ``run_agent_hook``: callable + ``module:attr`` import-path branches.
"""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from AgentGuard.hooks import handlers
from AgentGuard.hooks.exceptions import HookExecutionError
from AgentGuard.hooks.types import HookDecision, HookResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_script(path: Path, body: str) -> Path:
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


# ---------------------------------------------------------------------------
# command handler
# ---------------------------------------------------------------------------


def test_command_hook_block_via_exit_code(tmp_path: Path) -> None:
    script = _write_script(
        tmp_path / "block.sh",
        "#!/usr/bin/env bash\necho 'destructive command' >&2\nexit 2\n",
    )
    env = {"hook_event_name": "PreToolUse", "tool_name": "Bash"}
    result = handlers.run_command_hook(script, env)
    assert isinstance(result, HookResult)
    assert result.exit_code == 2
    assert result.decision.decision == "block"
    assert "destructive command" in result.stderr
    assert result.handler_type == "command"


def test_command_hook_allow_default(tmp_path: Path) -> None:
    script = _write_script(
        tmp_path / "allow.sh",
        "#!/usr/bin/env bash\necho '{\"decision\": \"allow\"}'\n",
    )
    result = handlers.run_command_hook(script, {"hook_event_name": "PreToolUse"})
    assert result.exit_code == 0
    assert result.decision.decision == "allow"


def test_command_hook_with_string_stdin(tmp_path: Path) -> None:
    script = _write_script(
        tmp_path / "echo.sh",
        "#!/usr/bin/env bash\ncat\n",
    )
    payload = json.dumps({"hook_event_name": "Stop"})
    result = handlers.run_command_hook(script, payload)
    assert payload in result.stdout


def test_command_hook_missing_handler_raises(tmp_path: Path) -> None:
    with pytest.raises(HookExecutionError, match="not found"):
        handlers.run_command_hook(tmp_path / "nope.sh", {})


def test_command_hook_non_executable_raises(tmp_path: Path) -> None:
    script = tmp_path / "noexec.sh"
    script.write_text("#!/usr/bin/env bash\nexit 0\n")
    # don't chmod +x
    with pytest.raises(HookExecutionError, match="not executable"):
        handlers.run_command_hook(script, {})


def test_command_hook_timeout_raises(tmp_path: Path) -> None:
    script = _write_script(
        tmp_path / "slow.sh",
        "#!/usr/bin/env bash\nsleep 5\n",
    )
    with pytest.raises(HookExecutionError, match="timed out"):
        handlers.run_command_hook(script, {}, timeout=0.2)


def test_command_hook_path_lookup_works() -> None:
    """If handler isn't a file, fall back to PATH (e.g. /bin/true)."""
    result = handlers.run_command_hook("true", {})
    assert result.exit_code == 0


def test_command_hook_records_duration(tmp_path: Path) -> None:
    script = _write_script(tmp_path / "ok.sh", "#!/usr/bin/env bash\nexit 0\n")
    result = handlers.run_command_hook(script, {})
    assert result.duration_ms > 0


def test_command_hook_stop_hook_active_propagates(tmp_path: Path) -> None:
    script = _write_script(tmp_path / "block.sh", "#!/usr/bin/env bash\nexit 2\n")
    env = {"hook_event_name": "Stop", "stop_hook_active": True}
    result = handlers.run_command_hook(script, env)
    assert result.stop_hook_active is True


# ---------------------------------------------------------------------------
# http handler
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text


def test_http_hook_200_allow(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse(200, json.dumps({"decision": "allow"}))

    monkeypatch.setattr(httpx, "post", fake_post)
    result = handlers.run_http_hook("http://x", {"hook_event_name": "PreToolUse"})
    assert result.exit_code == 0
    assert result.decision.decision == "allow"
    assert result.handler_type == "http"
    assert result.handler == "http://x"


def test_http_hook_403_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse(403, json.dumps({"reason": "forbidden"}))

    monkeypatch.setattr(httpx, "post", fake_post)
    result = handlers.run_http_hook("http://x", {})
    assert result.exit_code == 2
    assert result.decision.decision == "block"


def test_http_hook_other_status_warn(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse(500, "")

    monkeypatch.setattr(httpx, "post", fake_post)
    result = handlers.run_http_hook("http://x", {})
    assert result.exit_code == 1


def test_http_hook_transport_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, **kwargs: Any) -> _FakeResponse:
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(HookExecutionError, match="HTTP hook"):
        handlers.run_http_hook("http://x", {})


def test_http_hook_inject_context(monkeypatch: pytest.MonkeyPatch) -> None:
    body_with_ctx = json.dumps({"additional_context": "read-only system path"})

    def fake_post(url: str, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse(200, body_with_ctx)

    monkeypatch.setattr(httpx, "post", fake_post)
    result = handlers.run_http_hook("http://x", {})
    assert "read-only system path" in result.decision.additional_context


# ---------------------------------------------------------------------------
# prompt handler
# ---------------------------------------------------------------------------


def test_prompt_hook_uses_provider(mock_provider: Any) -> None:
    # mock_provider's first response.text == "hello" — parse_decision will
    # treat unparseable text as allow.
    result = handlers.run_prompt_hook("Decide.", {"hook_event_name": "PreToolUse"}, provider=mock_provider)
    assert result.handler_type == "prompt"
    assert result.exit_code == 0
    assert result.decision.decision == "allow"
    # provider.chat was called once
    assert len(mock_provider.calls) == 1


def test_prompt_hook_block_response(chat_response_factory: Callable[..., Any]) -> None:
    from AgentGuard.providers.mock import MockProvider

    provider = MockProvider(
        responses=[chat_response_factory(text='{"decision": "block", "reason": "no"}')]
    )
    result = handlers.run_prompt_hook("Decide.", {}, provider=provider)
    assert result.exit_code == 2
    assert result.decision.decision == "block"


def test_prompt_hook_requires_provider() -> None:
    with pytest.raises(HookExecutionError, match="requires a provider"):
        handlers.run_prompt_hook("p", {}, provider=None)


def test_prompt_hook_provider_error(chat_response_factory: Callable[..., Any]) -> None:
    class _Boom:
        def chat(self, **kwargs: Any) -> Any:
            raise RuntimeError("upstream timeout")

    with pytest.raises(HookExecutionError, match="provider call failed"):
        handlers.run_prompt_hook("p", {}, provider=_Boom())


# ---------------------------------------------------------------------------
# agent handler
# ---------------------------------------------------------------------------


def _agent_dict(envelope: dict[str, Any]) -> dict[str, Any]:
    return {"decision": "allow", "reason": "ok"}


def _agent_block(envelope: dict[str, Any]) -> dict[str, Any]:
    return {"decision": "block", "reason": "denied by agent"}


def _agent_string(envelope: dict[str, Any]) -> str:
    return '{"decision": "allow"}'


def _agent_decision_obj(envelope: dict[str, Any]) -> HookDecision:
    return HookDecision(decision="allow", reason="from-decision")


def _agent_explodes(envelope: dict[str, Any]) -> Any:
    raise ValueError("agent crashed")


def test_agent_hook_callable_dict_result() -> None:
    result = handlers.run_agent_hook(_agent_dict, {"hook_event_name": "PreToolUse"})
    assert result.handler_type == "agent"
    assert result.decision.decision == "allow"
    assert result.exit_code == 0


def test_agent_hook_block_decision() -> None:
    result = handlers.run_agent_hook(_agent_block, {})
    assert result.exit_code == 2
    assert result.decision.decision == "block"


def test_agent_hook_string_result() -> None:
    result = handlers.run_agent_hook(_agent_string, {})
    assert result.decision.decision == "allow"


def test_agent_hook_returns_hookdecision_directly() -> None:
    result = handlers.run_agent_hook(_agent_decision_obj, {})
    assert result.decision.reason == "from-decision"


def test_agent_hook_exception_wraps() -> None:
    with pytest.raises(HookExecutionError, match="agent crashed|raised"):
        handlers.run_agent_hook(_agent_explodes, {})


def test_agent_hook_import_path() -> None:
    # Reach into ourselves via a module path: tests.unit.hooks.test_handlers:_agent_dict
    result = handlers.run_agent_hook(
        "tests.unit.hooks.test_handlers:_agent_dict", {}
    )
    assert result.decision.decision == "allow"


def test_agent_hook_bad_import_path_raises() -> None:
    with pytest.raises(HookExecutionError):
        handlers.run_agent_hook("nonexistent.module:func", {})


def test_agent_hook_missing_attr_raises() -> None:
    with pytest.raises(HookExecutionError, match="not found"):
        handlers.run_agent_hook("tests.unit.hooks.test_handlers:_does_not_exist", {})


def test_agent_hook_non_callable_attr_raises() -> None:
    # json.JSONDecodeError is a class but not directly invokable as a hook;
    # better: pick a non-callable attribute (json.__doc__ is a str).
    with pytest.raises(HookExecutionError, match="not callable"):
        handlers.run_agent_hook("json:__doc__", {})


def test_agent_hook_invalid_form_raises() -> None:
    with pytest.raises(HookExecutionError, match="callable or"):
        handlers.run_agent_hook(42, {})  # type: ignore[arg-type]
