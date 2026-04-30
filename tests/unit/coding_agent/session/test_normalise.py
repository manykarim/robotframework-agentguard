"""Unit tests for `AgentGuard.coding_agent.session.normalise` — shared
parser helpers (`parse_iso8601`, `coerce_content`, `extract_usage`).
"""

from __future__ import annotations

from datetime import UTC

import pytest

try:
    from AgentGuard.coding_agent.session.normalise import (
        coerce_content,
        extract_message_text,
        extract_usage,
        parse_iso8601,
    )
    from AgentGuard.coding_agent.session.types import Usage
except ImportError:  # pragma: no cover — Phase 3 race
    pytest.skip("phase3: session.normalise not yet implemented", allow_module_level=True)


# ---------------------------- parse_iso8601 --------------------------------


def test_parse_iso_handles_z_suffix() -> None:
    out = parse_iso8601("2026-04-29T10:00:00Z")
    assert out is not None
    assert out.tzinfo is not None
    assert out.year == 2026


def test_parse_iso_handles_explicit_offset() -> None:
    out = parse_iso8601("2026-04-29T10:00:00+00:00")
    assert out is not None
    assert out.utcoffset() == UTC.utcoffset(None)


def test_parse_iso_naive_string_is_assumed_utc() -> None:
    out = parse_iso8601("2026-04-29T10:00:00")
    assert out is not None
    assert out.tzinfo is not None  # forced tz-aware


def test_parse_iso_returns_none_for_empty() -> None:
    assert parse_iso8601("") is None
    assert parse_iso8601(None) is None


def test_parse_iso_returns_none_for_garbage() -> None:
    assert parse_iso8601("not-a-date") is None


def test_parse_iso_returns_none_for_non_string() -> None:
    assert parse_iso8601(123) is None  # type: ignore[arg-type]


# ---------------------------- coerce_content -------------------------------


def test_coerce_content_passes_string_through() -> None:
    assert coerce_content("hello") == "hello"


def test_coerce_content_passes_list_of_dicts() -> None:
    blocks = [{"type": "text", "text": "x"}]
    assert coerce_content(blocks) == blocks


def test_coerce_content_wraps_list_of_strings_as_text_dicts() -> None:
    out = coerce_content(["a", "b"])
    assert isinstance(out, list)
    assert out[0]["type"] == "text"
    assert out[0]["text"] == "a"


def test_coerce_content_falls_back_to_str_for_unknown_types() -> None:
    out = coerce_content(123)
    assert isinstance(out, str)
    assert "123" in out


# ---------------------------- extract_message_text -------------------------


def test_extract_message_text_returns_empty_when_no_message() -> None:
    assert extract_message_text({}) == ""


def test_extract_message_text_handles_str_content() -> None:
    assert extract_message_text({"message": {"content": "hi"}}) == "hi"


def test_extract_message_text_concatenates_text_blocks() -> None:
    out = extract_message_text(
        {
            "message": {
                "content": [
                    {"type": "text", "text": "a"},
                    {"type": "tool_use", "id": "1"},  # ignored
                    {"type": "text", "text": "b"},
                ]
            }
        }
    )
    assert "a" in out and "b" in out


def test_extract_message_text_returns_empty_for_non_dict_message() -> None:
    assert extract_message_text({"message": 5}) == ""


# ---------------------------- extract_usage --------------------------------


def test_extract_usage_returns_zero_for_missing() -> None:
    out = extract_usage(None)
    assert isinstance(out, Usage)
    assert out.prompt_tokens == 0


def test_extract_usage_returns_zero_for_missing_usage_field() -> None:
    out = extract_usage({"role": "assistant"})
    assert out.prompt_tokens == 0


def test_extract_usage_anthropic_keys() -> None:
    out = extract_usage(
        {
            "usage": {
                "input_tokens": 42,
                "output_tokens": 7,
                "cache_read_input_tokens": 3,
                "cache_creation_input_tokens": 2,
                "cost_usd": 0.0001,
            }
        }
    )
    assert out.prompt_tokens == 42
    assert out.completion_tokens == 7
    assert out.cache_read_tokens == 3
    assert out.cache_write_tokens == 2
    assert out.cost_usd == pytest.approx(0.0001)


def test_extract_usage_openai_keys_fallback() -> None:
    out = extract_usage({"usage": {"prompt_tokens": 10, "completion_tokens": 4}})
    assert out.prompt_tokens == 10
    assert out.completion_tokens == 4


def test_extract_usage_invalid_cost_returns_none() -> None:
    out = extract_usage({"usage": {"prompt_tokens": 1, "cost_usd": "not-a-number"}})
    assert out.cost_usd is None
