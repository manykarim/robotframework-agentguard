"""Unit tests for `AgentGuard.coding_agent.drivers.local.LocalDriver`.

LocalDriver is the always-runnable Phase-3 driver. We exercise it offline by
injecting a deterministic :class:`MockProvider` so the entire ReAct loop
(message append, tool call execution, JSONL emit, parse-back) runs without a
network request.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

try:
    from AgentGuard.coding_agent.drivers.base import DriverConfig, DriverResult
    from AgentGuard.coding_agent.drivers.exceptions import DriverUnavailable
    from AgentGuard.coding_agent.drivers.local import LocalDriver
    from AgentGuard.providers.base import ChatResponse, Usage
    from AgentGuard.providers.mock import MockProvider
except ImportError:  # pragma: no cover — Phase 3 race
    pytest.skip("phase3: drivers.local not yet implemented", allow_module_level=True)


def _resp(text: str = "done", tool_calls: list[dict[str, Any]] | None = None) -> ChatResponse:
    return ChatResponse(
        text=text,
        tool_calls=tool_calls or [],
        usage=Usage(prompt_tokens=10, completion_tokens=5, cost_usd=Decimal("0.0001")),
    )


@pytest.fixture
def mock_provider_no_tools() -> MockProvider:
    """Single response — no tool calls — drives a one-turn loop."""
    return MockProvider(responses=[_resp(text="all done")])


@pytest.fixture
def mock_provider_one_tool() -> MockProvider:
    return MockProvider(
        responses=[
            _resp(
                text="reading",
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "read",
                            "arguments": json.dumps({"path": "x.py"}),
                        },
                    }
                ],
            ),
            _resp(text="all done"),
        ]
    )


# ---------------------------- protocol shape -------------------------------


def test_driver_name_is_local() -> None:
    assert LocalDriver().name == "local"


def test_is_available_true_when_provider_injected(mock_provider_no_tools: MockProvider) -> None:
    drv = LocalDriver(provider=mock_provider_no_tools)
    assert drv.is_available() is True


def test_is_available_false_without_key_or_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    drv = LocalDriver()
    assert drv.is_available() is False


def test_run_raises_driver_unavailable_when_not_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    drv = LocalDriver()
    with pytest.raises(DriverUnavailable):
        drv.run("hello", DriverConfig())


# ---------------------------- run() loop ----------------------------------


def test_run_no_tool_calls_terminates_after_one_turn(mock_provider_no_tools: MockProvider, tmp_path: Path) -> None:
    drv = LocalDriver(provider=mock_provider_no_tools)
    cfg = DriverConfig(jsonl_path=tmp_path / "session.jsonl", max_turns=10)
    result = drv.run("Hello", cfg)
    assert isinstance(result, DriverResult)
    assert result.driver == "local"
    assert result.exit_code == 0
    # only one chat call needed since no tool was requested
    assert len(mock_provider_no_tools.calls) == 1


def test_run_writes_jsonl_session_log(mock_provider_no_tools: MockProvider, tmp_path: Path) -> None:
    drv = LocalDriver(provider=mock_provider_no_tools)
    cfg = DriverConfig(jsonl_path=tmp_path / "session.jsonl")
    result = drv.run("Hello", cfg)
    assert result.jsonl_path is not None
    assert Path(result.jsonl_path).exists()
    lines = Path(result.jsonl_path).read_text().strip().splitlines()
    assert len(lines) >= 2  # at least system + user prompt


def test_run_with_tool_call_executes_two_turns(mock_provider_one_tool: MockProvider, tmp_path: Path) -> None:
    drv = LocalDriver(provider=mock_provider_one_tool)
    cfg = DriverConfig(jsonl_path=tmp_path / "s.jsonl", max_turns=10)
    result = drv.run("Read x.py", cfg)
    assert result.exit_code == 0
    # Two LLM calls: tool-emitting turn + final summary turn.
    assert len(mock_provider_one_tool.calls) == 2


def test_run_emits_tool_use_record_when_tool_called(mock_provider_one_tool: MockProvider, tmp_path: Path) -> None:
    drv = LocalDriver(provider=mock_provider_one_tool)
    cfg = DriverConfig(jsonl_path=tmp_path / "s.jsonl")
    result = drv.run("Read x.py", cfg)
    text = Path(result.jsonl_path).read_text()  # type: ignore[arg-type]
    assert "tool_use" in text
    assert "tool_result" in text or "toolUseResult" in text


def test_run_aggregates_cost_from_responses(mock_provider_one_tool: MockProvider, tmp_path: Path) -> None:
    drv = LocalDriver(provider=mock_provider_one_tool)
    cfg = DriverConfig(jsonl_path=tmp_path / "s.jsonl")
    result = drv.run("Read x.py", cfg)
    # 2 turns × 0.0001 cost
    assert result.cost_usd is not None
    assert result.cost_usd >= 0.0001


def test_run_provider_failure_sets_exit_code_one(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Provider with empty queue + strict=True raises ProviderAPIError.
    failing = MockProvider(strict=True)
    drv = LocalDriver(provider=failing)
    cfg = DriverConfig(jsonl_path=tmp_path / "s.jsonl", max_turns=2)
    result = drv.run("Hello", cfg)
    assert result.exit_code == 1


def test_run_default_jsonl_path_under_agentguard_dir(
    mock_provider_no_tools: MockProvider, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    drv = LocalDriver(provider=mock_provider_no_tools)
    result = drv.run("Hello", DriverConfig())
    assert result.jsonl_path is not None
    assert ".agentguard" in result.jsonl_path
    assert "sessions" in result.jsonl_path


def test_run_capture_jsonl_false_yields_no_session(mock_provider_no_tools: MockProvider, tmp_path: Path) -> None:
    drv = LocalDriver(provider=mock_provider_no_tools)
    cfg = DriverConfig(jsonl_path=tmp_path / "s.jsonl", capture_jsonl=False)
    result = drv.run("Hello", cfg)
    assert result.jsonl_path is None
    assert result.session is None


def test_run_attaches_parsed_session_when_capture(mock_provider_no_tools: MockProvider, tmp_path: Path) -> None:
    drv = LocalDriver(provider=mock_provider_no_tools)
    cfg = DriverConfig(jsonl_path=tmp_path / "s.jsonl", capture_jsonl=True)
    result = drv.run("Hello", cfg)
    # Session should round-trip through the canonical parser.
    assert result.session is not None
    msgs = getattr(result.session, "messages", [])
    assert len(msgs) >= 1


def test_run_records_per_turn_messages_in_provider_log(mock_provider_one_tool: MockProvider, tmp_path: Path) -> None:
    drv = LocalDriver(provider=mock_provider_one_tool)
    cfg = DriverConfig(jsonl_path=tmp_path / "s.jsonl")
    drv.run("Read x.py", cfg)
    # Second turn must include the tool-result message.
    second_call_messages = mock_provider_one_tool.calls[1]["messages"]
    roles = [m["role"] for m in second_call_messages]
    assert "tool" in roles
