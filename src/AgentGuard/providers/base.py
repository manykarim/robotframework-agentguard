"""LLMProviderAdapter Protocol + ChatResponse value object + provider exceptions.

ADR-001: every provider exposes the same `chat / cost / supports` surface so
downstream contexts (MCP, Skills, Judge, Stats) never see vendor-specific types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable


class AgentGuardProviderError(Exception):
    """Base class for every provider error AgentGuard surfaces upward."""


class RateLimitError(AgentGuardProviderError):
    """Provider returned 429 / quota exceeded."""


class AuthenticationError(AgentGuardProviderError):
    """Provider rejected the credentials (invalid or missing API key)."""


class ProviderAPIError(AgentGuardProviderError):
    """Generic upstream API failure (5xx, malformed payload, transport error)."""


@dataclass(slots=True, frozen=True)
class Usage:
    """Token + cost accounting for a single chat call."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: Decimal = Decimal("0")


@dataclass(slots=True)
class ChatResponse:
    """Provider-neutral chat response.

    - `text`         : assistant message content (joined if streamed)
    - `tool_calls`   : list of OpenAI-shaped tool calls (`{id, type, function: {name, arguments}}`)
    - `usage`        : token + cost accounting
    - `raw`          : the underlying provider response (debug / advanced use)
    """

    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    raw: Any | None = None


@runtime_checkable
class LLMProviderAdapter(Protocol):
    """Stable provider surface — see ADR-001."""

    name: str

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        """Single non-streaming chat completion."""
        ...

    def cost(self, response: ChatResponse) -> Decimal:
        """Return USD cost of `response` (uses the provider's own pricing)."""
        ...

    def supports(self, capability: str) -> bool:
        """Capability probe — e.g. `extended_thinking`, `structured_outputs`."""
        ...
