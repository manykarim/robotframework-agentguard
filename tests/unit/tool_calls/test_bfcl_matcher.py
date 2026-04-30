"""Tests for the BFCL AST equality matchers (ADR-004)."""

from __future__ import annotations

import json

import pytest

from AgentGuard.tool_calls.bfcl_matcher import (
    ast_equal,
    call_signature,
    coerce_tool_call,
    match_arguments,
    match_arguments_detailed,
    match_name,
    normalize,
)
from AgentGuard.tool_calls.types import ToolCall


def _openai_call(name: str, args: object, cid: str = "c1") -> dict:
    return {
        "id": cid,
        "type": "function",
        "function": {
            "name": name,
            "arguments": args if isinstance(args, str) else json.dumps(args),
        },
    }


class TestCoerceToolCall:
    def test_pass_through_toolcall(self) -> None:
        tc = ToolCall(name="x", arguments={"a": 1})
        assert coerce_tool_call(tc) is tc

    def test_openai_envelope(self) -> None:
        out = coerce_tool_call(_openai_call("add", {"x": 1, "y": 2}))
        assert out.name == "add"
        assert out.arguments == {"x": 1, "y": 2}
        assert out.id == "c1"

    def test_flat_form(self) -> None:
        out = coerce_tool_call({"name": "echo", "arguments": {"text": "hi"}})
        assert out.name == "echo"
        assert out.arguments == {"text": "hi"}

    def test_arguments_as_json_string(self) -> None:
        out = coerce_tool_call({"name": "x", "arguments": '{"a": 1}'})
        assert out.arguments == {"a": 1}

    def test_empty_arguments(self) -> None:
        out = coerce_tool_call({"name": "x", "arguments": ""})
        assert out.arguments == {}

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(ValueError):
            coerce_tool_call({"name": "x", "arguments": "{not json"})

    def test_missing_name_raises(self) -> None:
        with pytest.raises(ValueError):
            coerce_tool_call({"arguments": {}})

    def test_non_mapping_raises(self) -> None:
        with pytest.raises(ValueError):
            coerce_tool_call(42)


class TestMatchName:
    def test_exact_match(self) -> None:
        assert match_name(_openai_call("add", {}), "add")

    def test_mismatch(self) -> None:
        assert not match_name(_openai_call("add", {}), "subtract")

    def test_case_sensitive(self) -> None:
        assert not match_name(_openai_call("Add", {}), "add")

    def test_invalid_call_returns_false(self) -> None:
        assert not match_name({"function": "wrong"}, "add")


class TestMatchArguments:
    def test_ast_ignores_key_order(self) -> None:
        a = _openai_call("f", {"x": 1, "y": 2})
        assert match_arguments(a, {"y": 2, "x": 1})

    def test_ast_ignores_whitespace(self) -> None:
        a = {
            "function": {
                "name": "f",
                "arguments": '{ "x" :   1 , "y" :2 }',
            }
        }
        assert match_arguments(a, {"x": 1, "y": 2})

    def test_value_mismatch_fails(self) -> None:
        assert not match_arguments(_openai_call("f", {"x": 1}), {"x": 2})

    def test_extra_arg_fails(self) -> None:
        assert not match_arguments(_openai_call("f", {"x": 1, "y": 2}), {"x": 1})

    def test_missing_arg_fails(self) -> None:
        assert not match_arguments(_openai_call("f", {"x": 1}), {"x": 1, "y": 2})

    def test_nested_objects_ast_equal(self) -> None:
        a = _openai_call("f", {"opts": {"a": 1, "b": [2, 3]}})
        assert match_arguments(a, {"opts": {"b": [2, 3], "a": 1}})

    def test_strict_mode_no_normalisation(self) -> None:
        a = _openai_call("f", {"x": 1.0})
        # 1.0 == 1 in Python — strict mode still passes that, but key order
        # changes do too because it's a dict equality.
        assert match_arguments(a, {"x": 1.0}, mode="strict")

    def test_semantic_mode_raises(self) -> None:
        with pytest.raises(ValueError, match="semantic"):
            match_arguments(_openai_call("f", {}), {}, mode="semantic")

    def test_schema_coerces_string_to_int(self) -> None:
        a = _openai_call("f", {"x": "42"})
        schema = {"properties": {"x": {"type": "integer"}}}
        assert match_arguments(a, {"x": 42}, schema=schema)

    def test_schema_coerces_string_to_float(self) -> None:
        a = _openai_call("f", {"x": "3.14"})
        schema = {"properties": {"x": {"type": "number"}}}
        assert match_arguments(a, {"x": 3.14}, schema=schema)

    def test_invalid_args_returns_false(self) -> None:
        bad = {"function": {"name": "f", "arguments": "{not json"}}
        assert not match_arguments(bad, {"x": 1})


class TestMatchArgumentsDetailed:
    def test_match_returns_match_result(self) -> None:
        result = match_arguments_detailed(_openai_call("f", {"x": 1}), {"x": 1})
        assert result.matched
        assert result.reasons == ()

    def test_mismatch_returns_reasons(self) -> None:
        result = match_arguments_detailed(_openai_call("f", {"x": 1}), {"x": 2})
        assert not result.matched
        assert any("mismatch" in r for r in result.reasons)

    def test_missing_keys_listed(self) -> None:
        result = match_arguments_detailed(_openai_call("f", {"x": 1}), {"x": 1, "y": 2})
        assert any("missing keys" in r for r in result.reasons)


class TestAstEqual:
    def test_dicts_in_either_order(self) -> None:
        assert ast_equal({"a": 1, "b": 2}, {"b": 2, "a": 1})

    def test_lists_ordered(self) -> None:
        assert ast_equal([1, 2, 3], [1, 2, 3])
        assert not ast_equal([1, 2, 3], [3, 2, 1])

    def test_bool_is_not_int(self) -> None:
        # JSON: true ≠ 1
        assert not ast_equal(True, 1)
        assert not ast_equal(False, 0)

    def test_numeric_equality_with_floats(self) -> None:
        assert ast_equal(1, 1.0)


class TestNormalize:
    def test_sorts_keys(self) -> None:
        out = normalize({"b": 2, "a": 1})
        # First key in iteration order should be "a"
        assert list(out.keys()) == ["a", "b"]

    def test_strips_nones(self) -> None:
        out = normalize({"a": None, "b": 2})
        assert "a" not in out

    def test_parses_json_string(self) -> None:
        out = normalize('{"x": 1}')
        assert out == {"x": 1}


class TestCallSignature:
    def test_same_call_same_signature(self) -> None:
        a = _openai_call("f", {"x": 1, "y": 2})
        b = _openai_call("f", {"y": 2, "x": 1})
        assert call_signature(a) == call_signature(b)

    def test_different_args_different_sig(self) -> None:
        a = _openai_call("f", {"x": 1})
        b = _openai_call("f", {"x": 2})
        assert call_signature(a) != call_signature(b)

    def test_different_name_different_sig(self) -> None:
        a = _openai_call("f", {"x": 1})
        b = _openai_call("g", {"x": 1})
        assert call_signature(a) != call_signature(b)
