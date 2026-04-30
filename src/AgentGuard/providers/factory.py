"""Provider factory — `build_provider(name, model)` returns an `LLMProviderAdapter`.

Phase 1 supports `litellm` (default) and `mock`. The vendor-specific adapters
(`anthropic`, `openai`, `ollama`) are reserved for Phase 2 and currently raise
`NotImplementedError` to keep the public API stable while the implementations
land. Imports are lazy so a missing optional dep never breaks `agentguard
doctor`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from AgentGuard.providers.base import LLMProviderAdapter

_PHASE_2: frozenset[str] = frozenset({"anthropic", "openai", "ollama"})


def build_provider(name: str, model: str | None = None) -> LLMProviderAdapter:
    """Construct a provider adapter by short name.

    Supported now: `litellm`, `mock`.
    Reserved (Phase 2, raises `NotImplementedError`): `anthropic`, `openai`, `ollama`.
    """
    key = (name or "").strip().lower()

    if key in {"", "litellm", "default"}:
        from AgentGuard.providers.litellm_adapter import LiteLLMAdapter

        return LiteLLMAdapter(model=model)

    if key == "mock":
        from AgentGuard.providers.mock import MockProvider

        return MockProvider()

    if key in _PHASE_2:
        raise NotImplementedError(f"Provider '{key}' is reserved for Phase 2; use 'litellm' for now.")

    raise ValueError(f"Unknown provider: {name!r}. Choose from: litellm, mock.")
