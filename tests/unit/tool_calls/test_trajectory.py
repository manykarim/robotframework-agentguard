"""Tests for trajectory matchers — multiset (parallel) + ordered subsequence."""

from __future__ import annotations

import pytest

from AgentGuard.tool_calls.trajectory import (
    bfcl_score,
    extract_tool_names,
    match_parallel,
    match_sequence,
    normalise_trajectory,
    should_not_call_any_tool,
)
from AgentGuard.tool_calls.types import ToolCall


def _call(name: str, args: dict | None = None) -> dict:
    return {
        "function": {"name": name, "arguments": args or {}},
        "id": f"c-{name}",
    }


class TestExtractToolNames:
    def test_in_order(self) -> None:
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "tool_calls": [_call("a"), _call("b")]},
            {"role": "tool", "name": "a", "content": "ok"},
            {"role": "assistant", "tool_calls": [_call("c")]},
        ]
        assert extract_tool_names(msgs) == ["a", "b", "c"]

    def test_no_calls(self) -> None:
        assert extract_tool_names([{"role": "user", "content": "hi"}]) == []

    def test_skips_malformed(self) -> None:
        msgs = [
            {"role": "assistant", "tool_calls": [{"junk": "no name"}, _call("ok")]},
        ]
        assert extract_tool_names(msgs) == ["ok"]


class TestNormaliseTrajectory:
    def test_returns_toolcalls(self) -> None:
        out = normalise_trajectory([_call("a"), _call("b")])
        assert all(isinstance(t, ToolCall) for t in out)
        assert [t.name for t in out] == ["a", "b"]

    def test_drops_malformed(self) -> None:
        out = normalise_trajectory([_call("a"), {"junk": "no"}])
        assert [t.name for t in out] == ["a"]


class TestMatchParallel:
    def test_multiset_equality(self) -> None:
        actual = [_call("a"), _call("b", {"v": 1})]
        expected = [_call("b", {"v": 1}), _call("a")]
        assert match_parallel(actual, expected)

    def test_duplicates_count(self) -> None:
        actual = [_call("a"), _call("a")]
        expected = [_call("a"), _call("a")]
        assert match_parallel(actual, expected)

    def test_count_mismatch_fails(self) -> None:
        actual = [_call("a")]
        expected = [_call("a"), _call("a")]
        assert not match_parallel(actual, expected)

    def test_args_mismatch_fails(self) -> None:
        actual = [_call("a", {"v": 1})]
        expected = [_call("a", {"v": 2})]
        assert not match_parallel(actual, expected)


class TestMatchSequence:
    def test_exact_match(self) -> None:
        assert match_sequence(["a", "b", "c"], ["a", "b", "c"])

    def test_subsequence_with_chatter(self) -> None:
        actual = ["a", "noise", "b", "more", "c"]
        expected = ["a", "b", "c"]
        assert match_sequence(actual, expected, wildcards=True)

    def test_wildcard_token(self) -> None:
        actual = ["a", "x", "b"]
        expected = ["a", "*", "b"]
        assert match_sequence(actual, expected, wildcards=True)

    def test_wildcards_off_strict_length(self) -> None:
        actual = ["a", "noise", "b"]
        expected = ["a", "b"]
        assert not match_sequence(actual, expected, wildcards=False)

    def test_missing_call_fails(self) -> None:
        assert not match_sequence(["a"], ["a", "b"])

    def test_dict_expected_with_args(self) -> None:
        actual = [_call("a", {"x": 1}), _call("b", {"y": 2})]
        expected = [{"name": "a", "args": {"x": 1}}, {"name": "b"}]
        assert match_sequence(actual, expected, wildcards=True)

    def test_dict_expected_args_mismatch(self) -> None:
        actual = [_call("a", {"x": 1})]
        expected = [{"name": "a", "args": {"x": 2}}]
        assert not match_sequence(actual, expected, wildcards=True)

    def test_toolcall_expected(self) -> None:
        actual = [_call("a", {"x": 1})]
        expected = [ToolCall(name="a", arguments={"x": 1})]
        assert match_sequence(actual, expected, wildcards=True)


class TestShouldNotCallAnyTool:
    def test_empty_passes(self) -> None:
        assert should_not_call_any_tool([])

    def test_non_empty_fails(self) -> None:
        assert not should_not_call_any_tool([_call("a")])


class TestBfclScore:
    def test_perfect_one(self) -> None:
        assert bfcl_score(["a", "b"], ["a", "b"]) == pytest.approx(1.0)

    def test_completely_wrong_zero(self) -> None:
        # No overlap at all → LCS = 0 → 0.0
        assert bfcl_score(["x", "y"], ["a", "b"]) == pytest.approx(0.0)

    def test_partial_match(self) -> None:
        # 1/2 LCS → 0.5
        assert bfcl_score(["a", "x"], ["a", "b"]) == pytest.approx(0.5)

    def test_empty_expected_with_no_actual_one(self) -> None:
        assert bfcl_score([], []) == pytest.approx(1.0)

    def test_empty_expected_with_actual_zero(self) -> None:
        assert bfcl_score(["a"], []) == pytest.approx(0.0)

    def test_empty_actual_with_expected_zero(self) -> None:
        assert bfcl_score([], ["a"]) == pytest.approx(0.0)
