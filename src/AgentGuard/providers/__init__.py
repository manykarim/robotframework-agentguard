"""Provider context — uniform LLM access via LiteLLM (default) and vendor adapters.

See ADR-001 (Provider Abstraction via LiteLLM) and `docs/ddd/bounded-contexts.md` §1.
"""

from AgentGuard.providers.base import (
    AgentGuardProviderError,
    AuthenticationError,
    ChatResponse,
    LLMProviderAdapter,
    ProviderAPIError,
    RateLimitError,
    Usage,
)
from AgentGuard.providers.factory import build_provider

__all__ = [
    "AgentGuardProviderError",
    "AuthenticationError",
    "ChatResponse",
    "LLMProviderAdapter",
    "ProviderAPIError",
    "RateLimitError",
    "Usage",
    "build_provider",
]
