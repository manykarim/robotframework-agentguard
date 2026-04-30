"""Robot acceptance helper — instantiate LocalDriver with a MockProvider.

The LocalDriver requires either an OpenRouter key (live) or an injected
provider (offline). The Robot suite calls into this module via ``Evaluate``
to obtain a deterministic offline run without an OpenRouter dependency.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from AgentGuard.coding_agent.drivers.base import DriverConfig, DriverResult
from AgentGuard.coding_agent.drivers.local import LocalDriver
from AgentGuard.providers.base import ChatResponse, Usage
from AgentGuard.providers.mock import MockProvider


def _resp(text: str) -> ChatResponse:
    return ChatResponse(
        text=text,
        tool_calls=[],
        usage=Usage(prompt_tokens=10, completion_tokens=4, cost_usd=Decimal("0.0001")),
    )


def run(prompt: str, jsonl_path: str) -> DriverResult:
    """Run the LocalDriver against a one-shot MockProvider; return the result."""
    provider = MockProvider(responses=[_resp("ack: " + prompt)])
    drv = LocalDriver(provider=provider)
    cfg = DriverConfig(jsonl_path=Path(jsonl_path), max_turns=2)
    return drv.run(prompt, cfg)


__all__ = ["run"]
