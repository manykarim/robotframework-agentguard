"""Unit tests for ``HooksKeywords`` — Robot keyword wrapper layer.

Mirrors the shape of ``tests/unit/security/test_library_wrapper.py``.
"""

from __future__ import annotations

import stat
from pathlib import Path
from typing import Any

import pytest

from AgentGuard.hooks.exceptions import HookDecisionError, HookLoopDetected
from AgentGuard.hooks.library import HooksKeywords
from AgentGuard.hooks.types import HookDecision, HookResult


@pytest.fixture
def kw() -> HooksKeywords:
    return HooksKeywords()


# ---------------- synthesize ----------------


def test_synthesize_hook_input_returns_dict(kw: HooksKeywords) -> None:
    env = kw.synthesize_hook_input("PreToolUse", tool_name="Bash", tool_input={"command": "ls"})
    assert env["hook_event_name"] == "PreToolUse"
    assert env["tool_name"] == "Bash"


def test_synthesize_unknown_event_raises(kw: HooksKeywords) -> None:
    with pytest.raises(ValueError, match="Unknown hook event"):
        kw.synthesize_hook_input("Bogus")


# ---------------- run hook command ----------------


def _make_script(path: Path, body: str) -> Path:
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def test_run_hook_command_block(kw: HooksKeywords, tmp_path: Path) -> None:
    script = _make_script(tmp_path / "block.sh", "#!/usr/bin/env bash\nexit 2\n")
    env = kw.synthesize_hook_input("PreToolUse", tool_name="Bash")
    result = kw.run_hook_command(script, env)
    assert result.exit_code == 2


def test_run_hook_agent_via_callable(kw: HooksKeywords) -> None:
    def agent(env: dict[str, Any]) -> dict[str, Any]:
        return {"decision": "allow"}

    result = kw.run_hook_agent(agent, kw.synthesize_hook_input("Stop"))
    assert result.decision.decision == "allow"


# ---------------- assertions ----------------


def _result(*, exit_code: int = 0, decision: str = "allow") -> HookResult:
    return HookResult(
        handler="x",
        handler_type="command",
        exit_code=exit_code,
        stdout="",
        stderr="",
        decision=HookDecision(decision=decision),
    )


def test_hook_should_block_passes_on_exit2(kw: HooksKeywords) -> None:
    res = _result(exit_code=2, decision="block")
    assert kw.hook_should_block(res) is res


def test_hook_should_block_raises_when_allowed(kw: HooksKeywords) -> None:
    with pytest.raises(HookDecisionError, match="Expected hook to block"):
        kw.hook_should_block(_result(exit_code=0, decision="allow"))


def test_hook_should_allow_passes(kw: HooksKeywords) -> None:
    res = _result(exit_code=0, decision="allow")
    assert kw.hook_should_allow(res) is res


def test_hook_should_allow_raises_on_block(kw: HooksKeywords) -> None:
    with pytest.raises(HookDecisionError, match="Expected hook to allow"):
        kw.hook_should_allow(_result(exit_code=2, decision="block"))


def test_hook_decision_should_be_matches(kw: HooksKeywords) -> None:
    res = _result(decision="allow")
    assert kw.hook_decision_should_be(res, "ALLOW") is res


def test_hook_decision_should_be_mismatch(kw: HooksKeywords) -> None:
    with pytest.raises(HookDecisionError, match="Expected decision"):
        kw.hook_decision_should_be(_result(decision="allow"), "block")


def test_hook_should_inject_context(kw: HooksKeywords) -> None:
    res = HookResult(
        handler="x",
        handler_type="http",
        exit_code=0,
        stdout="{}",
        stderr="",
        decision=HookDecision(decision="allow", additional_context="read-only system path"),
    )
    assert kw.hook_should_inject_context(res, "read-only") is res


def test_hook_should_inject_context_falls_back_to_stdout(kw: HooksKeywords) -> None:
    res = HookResult(
        handler="x",
        handler_type="http",
        exit_code=0,
        stdout='{"foo": "this contains the marker word"}',
        stderr="",
        decision=HookDecision(decision="allow"),
    )
    assert kw.hook_should_inject_context(res, "marker") is res


def test_hook_should_inject_context_raises_when_missing(kw: HooksKeywords) -> None:
    with pytest.raises(HookDecisionError, match="did not inject"):
        kw.hook_should_inject_context(_result(), "missing")


def test_hook_should_modify_tool_input_to(kw: HooksKeywords) -> None:
    res = HookResult(
        handler="x",
        handler_type="command",
        exit_code=0,
        stdout="{}",
        stderr="",
        decision=HookDecision(decision="allow", modified_tool_input={"command": "ls -la"}),
    )
    assert kw.hook_should_modify_tool_input_to(res, {"command": "ls -la"}) is res


def test_hook_should_modify_tool_input_to_none_raises(kw: HooksKeywords) -> None:
    with pytest.raises(HookDecisionError, match="did not return"):
        kw.hook_should_modify_tool_input_to(_result(), {"k": "v"})


def test_hook_should_modify_tool_input_mismatch(kw: HooksKeywords) -> None:
    res = HookResult(
        handler="x",
        handler_type="command",
        exit_code=0,
        stdout="{}",
        stderr="",
        decision=HookDecision(decision="allow", modified_tool_input={"a": 1}),
    )
    with pytest.raises(HookDecisionError, match="mismatch"):
        kw.hook_should_modify_tool_input_to(res, {"a": 2})


# ---------------- loop detect ----------------


def test_detect_stop_hook_loop_no_loop(kw: HooksKeywords) -> None:
    assert kw.detect_stop_hook_loop([_result()] * 2, window=5) is False


def test_detect_stop_hook_loop_raises(kw: HooksKeywords) -> None:
    res = HookResult(
        handler="x",
        handler_type="command",
        exit_code=2,
        stdout="",
        stderr="",
        decision=HookDecision(decision="block", raw={"_stop_hook_active": True}),
    )
    with pytest.raises(HookLoopDetected):
        kw.detect_stop_hook_loop([res] * 5, window=5)


# ---------------- prompt handler integration ----------------


def test_run_hook_prompt_uses_provider(mock_provider: Any) -> None:
    kw = HooksKeywords(provider=mock_provider, default_model="mock/model")
    result = kw.run_hook_prompt("Decide.", {"hook_event_name": "PreToolUse"})
    # mock_provider returns text="hello" → parse_decision → allow.
    assert result.handler_type == "prompt"
    assert result.decision.decision == "allow"
