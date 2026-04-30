"""Deterministic in-process provider for offline tests.

Returns a pre-supplied list of `ChatResponse` objects in order. When the queue
is exhausted, the last response is repeated (callers that need stricter
behaviour should pass `strict=True`).
"""

from __future__ import annotations

from collections import deque
from decimal import Decimal
from typing import Any

from AgentGuard.providers.base import ChatResponse, ProviderAPIError


class MockProvider:
    """Replayable provider for unit tests."""

    name: str = "mock"

    def __init__(
        self,
        responses: list[ChatResponse] | None = None,
        *,
        strict: bool = False,
        capabilities: frozenset[str] | None = None,
    ) -> None:
        self._queue: deque[ChatResponse] = deque(responses or [])
        self._last: ChatResponse | None = None
        self._strict = strict
        self._capabilities = capabilities or frozenset({"tool_calls"})
        self._calls: list[dict[str, Any]] = []

    @property
    def calls(self) -> list[dict[str, Any]]:
        return list(self._calls)

    def enqueue(self, response: ChatResponse) -> None:
        self._queue.append(response)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        self._calls.append({"messages": messages, "tools": tools, "model": model, "kwargs": kwargs})
        if self._queue:
            self._last = self._queue.popleft()
            return self._last
        if self._last is not None and not self._strict:
            return self._last
        raise ProviderAPIError("MockProvider has no queued responses.")

    def cost(self, response: ChatResponse) -> Decimal:
        return response.usage.cost_usd

    def supports(self, capability: str) -> bool:
        return capability in self._capabilities
