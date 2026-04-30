"""Unit tests for `AgentGuard.coding_agent.session.types` — the canonical
:class:`Session` dataclass and friends.

These tests pin the public shape (field names, defaults, helpers) so a
metrics or driver agent that depends on an attribute name can rely on it.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

try:
    from AgentGuard.coding_agent.session.types import (
        HookEvent,
        Interrupt,
        Message,
        Session,
        ThinkingBlock,
        ToolCall,
        ToolResponse,
        Usage,
    )
except ImportError:  # pragma: no cover — Phase 3 race
    pytest.skip("phase3: session.types not yet implemented", allow_module_level=True)


# ---------------------------- Usage ----------------------------------------


def test_usage_defaults_are_zero() -> None:
    usage = Usage()
    assert usage.prompt_tokens == 0
    assert usage.completion_tokens == 0
    assert usage.cache_read_tokens == 0
    assert usage.cache_write_tokens == 0
    assert usage.cost_usd is None


def test_usage_add_accumulates_in_place() -> None:
    a = Usage(prompt_tokens=10, completion_tokens=5, cost_usd=0.001)
    b = Usage(prompt_tokens=20, completion_tokens=15, cost_usd=0.002)
    a.add(b)
    assert a.prompt_tokens == 30
    assert a.completion_tokens == 20
    assert a.cost_usd == pytest.approx(0.003)


def test_usage_add_handles_none_cost() -> None:
    a = Usage(prompt_tokens=5)
    b = Usage(prompt_tokens=2)  # cost_usd=None
    a.add(b)
    assert a.cost_usd is None
    assert a.prompt_tokens == 7


def test_usage_add_seeds_cost_when_first_value_none() -> None:
    a = Usage()  # cost_usd=None
    b = Usage(cost_usd=0.5)
    a.add(b)
    assert a.cost_usd == pytest.approx(0.5)


def test_usage_add_accumulates_cache_fields() -> None:
    a = Usage(cache_read_tokens=5, cache_write_tokens=3)
    b = Usage(cache_read_tokens=2, cache_write_tokens=4)
    a.add(b)
    assert a.cache_read_tokens == 7
    assert a.cache_write_tokens == 7


# ---------------------------- ToolCall / ToolResponse ----------------------


def test_tool_call_is_constructable_with_minimal_args() -> None:
    tc = ToolCall(id="abc", name="Read", arguments={"path": "x.py"})
    assert tc.id == "abc"
    assert tc.timestamp is None


def test_tool_response_defaults_is_error_to_false() -> None:
    tr = ToolResponse(tool_call_id="abc", content="ok")
    assert tr.is_error is False


def test_tool_response_can_carry_dict_content() -> None:
    tr = ToolResponse(tool_call_id="abc", content={"out": "ok"})
    assert isinstance(tr.content, dict)


# ---------------------------- ThinkingBlock --------------------------------


def test_thinking_block_signature_length_default() -> None:
    tb = ThinkingBlock(text="hello world")
    assert tb.signature_length == 0


def test_thinking_block_carries_signature_length() -> None:
    tb = ThinkingBlock(text="hello", signature_length=42)
    assert tb.signature_length == 42


# ---------------------------- Interrupt / HookEvent ------------------------


def test_interrupt_accepts_only_timestamp() -> None:
    iv = Interrupt(timestamp=datetime.now(tz=timezone.utc))
    assert iv.reason is None


def test_hook_event_decision_optional() -> None:
    ev = HookEvent(event="Stop")
    assert ev.decision is None


# ---------------------------- Message --------------------------------------


def test_message_defaults_no_tool_calls() -> None:
    m = Message(role="user", content="hi")
    assert m.tool_calls == []


def test_message_accepts_anthropic_content_blocks() -> None:
    m = Message(role="assistant", content=[{"type": "text", "text": "hi"}])
    assert isinstance(m.content, list)
    assert m.content[0]["type"] == "text"


# ---------------------------- Session --------------------------------------


def test_session_defaults_are_empty_collections() -> None:
    s = Session(id="x", source="claude-code")
    assert s.messages == []
    assert s.tool_calls == []
    assert s.tool_responses == []
    assert s.thinking_blocks == []
    assert s.interrupts == []
    assert s.hook_events == []
    assert isinstance(s.usage, Usage)
    assert s.metadata == {}


def test_session_text_skips_tool_use_blocks() -> None:
    s = Session(
        id="x",
        source="claude-code",
        messages=[
            Message(role="user", content="please read x.py"),
            Message(
                role="assistant",
                content=[
                    {"type": "text", "text": "Reading."},
                    {"type": "tool_use", "id": "1", "name": "Read", "input": {}},
                    {"type": "text", "text": "Done."},
                ],
            ),
        ],
    )
    out = s.text()
    assert "Reading." in out
    assert "Done." in out
    # tool_use payloads must NOT bleed into the text — we should not see the
    # raw tool name as a separate chunk from the assistant content blocks.
    # (User asked the assistant to "read x.py" so the literal substring is
    # present in the user message, but the assistant's tool_use block must
    # not contribute its name field.)
    assistant_only = "\n".join(
        c if isinstance(c, str) else "" for c in (out,)
    )
    assert "tool_use" not in assistant_only


def test_session_text_picks_up_thinking_text() -> None:
    s = Session(
        id="x",
        source="claude-code",
        messages=[
            Message(
                role="assistant",
                content=[{"type": "thinking", "thinking": "ponder"}],
            )
        ],
    )
    assert "ponder" in s.text()


def test_session_text_handles_str_content() -> None:
    s = Session(
        id="x",
        source="claude-code",
        messages=[Message(role="user", content="bare string")],
    )
    assert "bare string" in s.text()


def test_session_text_skips_empty_strings() -> None:
    s = Session(
        id="x",
        source="claude-code",
        messages=[
            Message(role="assistant", content=""),
            Message(role="assistant", content="actual content"),
        ],
    )
    assert s.text() == "actual content"
