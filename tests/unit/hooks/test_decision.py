"""Unit tests for ``AgentGuard.hooks.decision`` — parse handler stdout/exit."""

from __future__ import annotations

import json

from AgentGuard.hooks.decision import parse_decision


def test_exit_2_overrides_stdout() -> None:
    """Even ``decision: allow`` JSON cannot beat exit code 2."""
    text = json.dumps({"decision": "allow", "reason": "ignored"})
    decision = parse_decision(text, exit_code=2)
    assert decision.decision == "block"
    assert decision.reason == "ignored"  # the reason text survives


def test_plain_allow_default() -> None:
    decision = parse_decision("", 0)
    assert decision.decision == "allow"
    assert decision.reason == ""


def test_decision_field_lowercased() -> None:
    decision = parse_decision('{"decision": "BLOCK"}', 0)
    assert decision.decision == "block"


def test_permission_decision_deny_maps_to_block() -> None:
    decision = parse_decision('{"permissionDecision": "deny", "reason": "no"}', 0)
    assert decision.decision == "block"
    assert decision.permission_decision == "deny"
    assert decision.reason == "no"


def test_permission_decision_allow_passthrough() -> None:
    decision = parse_decision('{"permissionDecision": "allow"}', 0)
    assert decision.decision == "allow"
    assert decision.permission_decision == "allow"


def test_additional_context_top_level() -> None:
    decision = parse_decision('{"additional_context": "use cwd=/tmp"}', 0)
    assert decision.additional_context == "use cwd=/tmp"


def test_camel_case_additional_context() -> None:
    decision = parse_decision('{"additionalContext": "warn the user"}', 0)
    assert decision.additional_context == "warn the user"


def test_modified_tool_input_dict_kept() -> None:
    payload = {"modified_tool_input": {"command": "ls -la"}}
    decision = parse_decision(json.dumps(payload), 0)
    assert decision.modified_tool_input == {"command": "ls -la"}


def test_modified_tool_input_non_dict_dropped() -> None:
    payload = {"modified_tool_input": "not-a-dict"}
    decision = parse_decision(json.dumps(payload), 0)
    assert decision.modified_tool_input is None


def test_malformed_json_falls_through_to_allow() -> None:
    # Parser must not raise on garbage.
    decision = parse_decision("{not really json}", 0)
    assert decision.decision == "allow"
    assert decision.reason == ""


def test_non_dict_json_top_level_ignored() -> None:
    decision = parse_decision('["just", "an", "array"]', 0)
    assert decision.decision == "allow"


def test_reason_coerced_to_str() -> None:
    decision = parse_decision('{"reason": 42}', 0)
    assert decision.reason == "42"


def test_context_dict_serialized() -> None:
    decision = parse_decision('{"context": {"key": "value"}}', 0)
    # parser json-dumps non-string contexts
    assert "key" in decision.additional_context


def test_raw_payload_preserved() -> None:
    text = '{"decision": "allow", "extra": "field"}'
    decision = parse_decision(text, 0)
    assert decision.raw["extra"] == "field"


def test_inject_context_alt_keys() -> None:
    decision = parse_decision('{"injected_context": "hint"}', 0)
    assert decision.additional_context == "hint"
