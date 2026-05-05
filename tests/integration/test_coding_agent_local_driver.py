"""Integration tests — LocalDriver end-to-end via the in-process MockProvider
(default) plus an opt-in live OpenRouter smoke test.

The offline path proves the JSONL → Session round-trip works without any
network. The live path verifies the OpenRouter wiring without burning
credit (1 turn, ``gpt-4o-mini``, ~$0.0001/run).
"""

from __future__ import annotations

import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

try:
    from AgentGuard.coding_agent.drivers.base import DriverConfig, DriverResult
    from AgentGuard.coding_agent.drivers.local import LocalDriver
    from AgentGuard.coding_agent.session import parser
    from AgentGuard.providers.base import ChatResponse, Usage
    from AgentGuard.providers.mock import MockProvider
except ImportError:  # pragma: no cover — Phase 3 race
    pytest.skip("phase3: drivers.local or session.parser not yet implemented", allow_module_level=True)


def _resp(text: str = "ok", tool_calls: list[dict[str, Any]] | None = None) -> ChatResponse:
    return ChatResponse(
        text=text,
        tool_calls=tool_calls or [],
        usage=Usage(prompt_tokens=10, completion_tokens=5, cost_usd=Decimal("0.0001")),
    )


# ---------------------------- offline (mock provider) ---------------------


def test_local_driver_offline_writes_session(tmp_path: Path) -> None:
    provider = MockProvider(responses=[_resp("hello world")])
    drv = LocalDriver(provider=provider)
    cfg = DriverConfig(jsonl_path=tmp_path / "session.jsonl")

    result = drv.run("Say hi", cfg)

    assert isinstance(result, DriverResult)
    assert result.exit_code == 0
    assert Path(result.jsonl_path).exists()  # type: ignore[arg-type]


def test_local_driver_offline_jsonl_parses_back(tmp_path: Path) -> None:
    provider = MockProvider(responses=[_resp("hello world")])
    drv = LocalDriver(provider=provider)
    cfg = DriverConfig(jsonl_path=tmp_path / "s.jsonl")
    result = drv.run("hi", cfg)

    s = parser.parse(result.jsonl_path)  # type: ignore[arg-type]
    assert s.source == "claude-code"
    assert len(s.messages) >= 1


def test_local_driver_offline_with_tool_call_records_pair(tmp_path: Path) -> None:
    provider = MockProvider(
        responses=[
            _resp(
                "reading...",
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
            _resp("done"),
        ]
    )
    drv = LocalDriver(provider=provider)
    cfg = DriverConfig(jsonl_path=tmp_path / "s.jsonl")
    result = drv.run("Please read x.py", cfg)
    assert result.session is not None
    assert len(result.session.tool_calls) == 1
    # Pairing must succeed via tool_use_id.
    assert len(result.session.tool_responses) == 1


def test_local_driver_session_attached_to_result(tmp_path: Path) -> None:
    provider = MockProvider(responses=[_resp("hello")])
    drv = LocalDriver(provider=provider)
    cfg = DriverConfig(jsonl_path=tmp_path / "s.jsonl")
    result = drv.run("hi", cfg)
    assert result.session is not None
    assert result.session.id  # non-empty


# ---------------------------- live OpenRouter -----------------------------


@pytest.mark.live
def test_live_local_driver(tmp_path: Path) -> None:
    """Smoke-test the LocalDriver against OpenRouter (≤$0.05 per run).

    Skipped unless ``OPENROUTER_API_KEY`` is in the environment.
    """
    if not os.getenv("OPENROUTER_API_KEY"):
        pytest.skip("live test requires OPENROUTER_API_KEY")

    drv = LocalDriver()
    cfg = DriverConfig(
        jsonl_path=tmp_path / "live.jsonl",
        model="openrouter/openai/gpt-4o-mini",
        max_turns=1,
        timeout_seconds=120,
    )
    result = drv.run("Say 'pong' and stop.", cfg)

    assert result.exit_code == 0
    assert Path(result.jsonl_path).exists()  # type: ignore[arg-type]
    s = parser.parse(result.jsonl_path)  # type: ignore[arg-type]
    assert len(s.messages) >= 1
