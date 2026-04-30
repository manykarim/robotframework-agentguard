"""Direct unit tests for ``ToolCallKeywords`` — the Robot keyword wrapper layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from AgentGuard.tool_calls.library import ToolCallKeywords, _to_openai_tool
from AgentGuard.tool_calls.types import (
    BFCLCase,
    ExpectedCall,
    Prediction,
    ToolCall,
    ToolDefinition,
)


@pytest.fixture
def kw() -> ToolCallKeywords:
    return ToolCallKeywords(default_model="mockllm/model")


# ---------------- name matching ----------------


def test_tool_call_should_match_name_passes(kw: ToolCallKeywords) -> None:
    kw.tool_call_should_match_name({"name": "search", "arguments": {}}, "search")


def test_tool_call_should_match_name_raises(kw: ToolCallKeywords) -> None:
    with pytest.raises(AssertionError, match="Tool name mismatch"):
        kw.tool_call_should_match_name({"name": "search", "arguments": {}}, "fetch")


def test_tool_call_should_match_name_safe_name_for_malformed(kw: ToolCallKeywords) -> None:
    # No "name" key — _safe_name returns "<malformed>"
    with pytest.raises(AssertionError):
        kw.tool_call_should_match_name({"foo": "bar"}, "fetch")


# ---------------- argument matching ----------------


def test_tool_call_arguments_should_match_passes(kw: ToolCallKeywords) -> None:
    kw.tool_call_arguments_should_match(
        {"name": "f", "arguments": {"a": 1, "b": 2}},
        {"a": 1, "b": 2},
        mode="ast",
    )


def test_tool_call_arguments_should_match_raises_on_mismatch(kw: ToolCallKeywords) -> None:
    with pytest.raises(AssertionError, match="do not match"):
        kw.tool_call_arguments_should_match(
            {"name": "f", "arguments": {"a": 1}},
            {"a": 2},
            mode="ast",
        )


def test_tool_call_arguments_strict_mode(kw: ToolCallKeywords) -> None:
    kw.tool_call_arguments_should_match(
        {"name": "f", "arguments": {"x": "1"}},
        {"x": "1"},
        mode="strict",
    )


# ---------------- required parameters ----------------


def test_required_parameters_should_be_present_passes(kw: ToolCallKeywords) -> None:
    schema = {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]}
    kw.required_parameters_should_be_present({"name": "f", "arguments": {"x": 1}}, schema)


def test_required_parameters_should_be_present_raises(kw: ToolCallKeywords) -> None:
    schema = {
        "type": "object",
        "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}},
        "required": ["x", "y"],
    }
    with pytest.raises(AssertionError, match="Missing required parameter"):
        kw.required_parameters_should_be_present({"name": "f", "arguments": {"x": 1}}, schema)


# ---------------- parallel / sequence ----------------


def test_parallel_tool_calls_should_match_passes(kw: ToolCallKeywords) -> None:
    actual = [{"name": "a", "arguments": {}}, {"name": "b", "arguments": {}}]
    expected = [{"name": "b", "arguments": {}}, {"name": "a", "arguments": {}}]
    kw.parallel_tool_calls_should_match(actual, expected)


def test_parallel_tool_calls_should_match_raises_on_count_mismatch(kw: ToolCallKeywords) -> None:
    actual = [{"name": "a", "arguments": {}}]
    expected = [{"name": "a", "arguments": {}}, {"name": "b", "arguments": {}}]
    with pytest.raises(AssertionError, match="do not match"):
        kw.parallel_tool_calls_should_match(actual, expected)


def test_tool_sequence_should_match_passes(kw: ToolCallKeywords) -> None:
    seq = [{"name": "a"}, {"name": "b"}, {"name": "c"}]
    kw.tool_sequence_should_match(seq, ["a", "*", "c"])


def test_tool_sequence_should_match_raises(kw: ToolCallKeywords) -> None:
    seq = [{"name": "a"}, {"name": "b"}]
    with pytest.raises(AssertionError, match="does not match"):
        kw.tool_sequence_should_match(seq, ["x", "y"])


def test_tool_sequence_strict_mode(kw: ToolCallKeywords) -> None:
    seq = [{"name": "a"}, {"name": "b"}]
    kw.tool_sequence_should_match(seq, ["a", "b"], wildcards=False)


def test_should_not_call_any_tool_passes(kw: ToolCallKeywords) -> None:
    kw.should_not_call_any_tool([])


def test_should_not_call_any_tool_raises(kw: ToolCallKeywords) -> None:
    with pytest.raises(AssertionError, match="Expected no tool calls"):
        kw.should_not_call_any_tool([{"name": "x"}])


# ---------------- BFCL ----------------


def test_load_bfcl_dataset_returns_list(kw: ToolCallKeywords) -> None:
    cases = kw.load_bfcl_dataset(category="simple", limit=5)
    assert isinstance(cases, list)


def test_bfcl_score_should_be_above_passes(kw: ToolCallKeywords) -> None:
    case = BFCLCase(
        case_id="t1",
        prompt="add 1+2",
        tools=[],
        expected=[ExpectedCall(name="add", arguments={"x": 1, "y": 2})],
        category="simple",
    )
    pred = Prediction(case=case, actual=[ToolCall(name="add", arguments={"x": 1, "y": 2})])
    score = kw.bfcl_score_should_be_above([pred], threshold=0.5)
    assert score == pytest.approx(1.0)


def test_bfcl_score_raises_on_empty(kw: ToolCallKeywords) -> None:
    with pytest.raises(AssertionError, match="empty"):
        kw.bfcl_score_should_be_above([], threshold=0.5)


def test_bfcl_score_raises_on_invalid_threshold(kw: ToolCallKeywords) -> None:
    case = BFCLCase(case_id="x", prompt="", tools=[], expected=[], category="simple")
    pred = Prediction(case=case, actual=[])
    with pytest.raises(ValueError, match="threshold"):
        kw.bfcl_score_should_be_above([pred], threshold=1.5)


def test_bfcl_score_raises_when_below_threshold(kw: ToolCallKeywords) -> None:
    case = BFCLCase(
        case_id="t1",
        prompt="add",
        tools=[],
        expected=[ExpectedCall(name="add", arguments={"x": 1})],
        category="simple",
    )
    pred = Prediction(case=case, actual=[ToolCall(name="multiply", arguments={"x": 9})])
    with pytest.raises(AssertionError, match="score"):
        kw.bfcl_score_should_be_above([pred], threshold=0.9)


# ---------------- Generate Tool Call ----------------


def test_generate_tool_call_without_provider_raises(kw: ToolCallKeywords) -> None:
    with pytest.raises(RuntimeError, match="provider"):
        kw.generate_tool_call("hi", tools=[])


@dataclass
class _StubResp:
    tool_calls: list[Any]


def test_generate_tool_call_with_provider_returns_calls() -> None:
    raw = [{"name": "search", "arguments": {"q": "x"}}]
    provider = type("P", (), {"chat": lambda self, **kw: _StubResp(tool_calls=raw)})()
    kw = ToolCallKeywords(provider=provider, default_model="mockllm/model")
    out = kw.generate_tool_call(
        "find x",
        tools=[{"name": "search", "description": "d", "parameters": {}}],
    )
    assert len(out) == 1
    assert out[0].name == "search"


def test_generate_tool_call_with_typed_tool_definition() -> None:
    raw = [{"name": "f", "arguments": {}}]
    provider = type("P", (), {"chat": lambda self, **kw: _StubResp(tool_calls=raw)})()
    kw = ToolCallKeywords(provider=provider, default_model="mockllm/model")
    tdef = ToolDefinition(name="f", description="d", parameters={"type": "object"})
    out = kw.generate_tool_call("p", tools=[tdef])
    assert out[0].name == "f"


# ---------------- helpers ----------------


def test_extract_tool_names_from_messages(kw: ToolCallKeywords) -> None:
    messages: list[dict[str, Any]] = [
        {"role": "assistant", "tool_calls": [{"name": "a"}, {"name": "b"}]},
        {"role": "assistant", "tool_calls": [{"name": "c"}]},
    ]
    names = kw.extract_tool_names_from_messages(messages)
    assert names == ["a", "b", "c"] or set(names) == {"a", "b", "c"}


def test_to_openai_tool_dict_passthrough() -> None:
    t = {"type": "function", "function": {"name": "f", "description": "", "parameters": {}}}
    assert _to_openai_tool(t) == t


def test_to_openai_tool_plain_dict_wrapped() -> None:
    out = _to_openai_tool({"name": "f", "description": "d", "parameters": {"x": 1}})
    assert out["type"] == "function"
    assert out["function"]["name"] == "f"


def test_to_openai_tool_typed() -> None:
    tdef = ToolDefinition(name="f", description="d", parameters={"type": "object"})
    out = _to_openai_tool(tdef)
    assert isinstance(out, dict)


def test_to_openai_tool_invalid_raises() -> None:
    with pytest.raises(TypeError):
        _to_openai_tool(42)  # type: ignore[arg-type]
