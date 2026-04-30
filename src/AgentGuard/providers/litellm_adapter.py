"""LiteLLM-backed default provider — wraps `litellm.completion`.

OpenRouter routing is expressed as `model="openrouter/<vendor>/<id>"`. Provider
exceptions are normalised to the AgentGuard hierarchy in `base.py`.

Per exp_03 refutation: there is NO `litellm.__version__`; use
`importlib.metadata.version("litellm")`.
"""

from __future__ import annotations

from decimal import Decimal
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from AgentGuard.providers.base import (
    AuthenticationError,
    ChatResponse,
    ProviderAPIError,
    RateLimitError,
    Usage,
)

_DEFAULT_CAPABILITIES: frozenset[str] = frozenset(
    {
        "tool_calls",
        "streaming",
        "openai_compatible",
        "cost_tracking",
    }
)


def _litellm_version() -> str:
    try:
        return version("litellm")
    except PackageNotFoundError:
        return "unknown"


class LiteLLMAdapter:
    """Default `LLMProviderAdapter` implementation."""

    name: str = "litellm"

    def __init__(self, model: str | None = None) -> None:
        self._default_model = model
        self._version = _litellm_version()

    @property
    def default_model(self) -> str | None:
        return self._default_model

    @property
    def version(self) -> str:
        return self._version

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        import litellm
        from litellm import exceptions as lex

        chosen_model = model or self._default_model
        if chosen_model is None:
            raise ProviderAPIError("No model supplied to LiteLLMAdapter.chat() and no default set.")

        call_kwargs: dict[str, Any] = {"model": chosen_model, "messages": messages}
        if tools:
            call_kwargs["tools"] = tools
        call_kwargs.update(kwargs)

        try:
            raw = litellm.completion(**call_kwargs)
        except lex.RateLimitError as exc:
            raise RateLimitError(str(exc)) from exc
        except lex.AuthenticationError as exc:
            raise AuthenticationError(str(exc)) from exc
        except lex.APIError as exc:
            raise ProviderAPIError(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 — last-resort normalisation
            raise ProviderAPIError(f"LiteLLM call failed: {exc}") from exc

        return self._normalise(raw)

    def cost(self, response: ChatResponse) -> Decimal:
        return response.usage.cost_usd

    def supports(self, capability: str) -> bool:
        return capability in _DEFAULT_CAPABILITIES

    @staticmethod
    def _normalise(raw: Any) -> ChatResponse:
        text = ""
        tool_calls: list[dict[str, Any]] = []
        prompt_tokens = 0
        completion_tokens = 0
        cost_usd = Decimal("0")

        choices = getattr(raw, "choices", None) or []
        if choices:
            msg = getattr(choices[0], "message", None)
            if msg is not None:
                text = getattr(msg, "content", None) or ""
                raw_tool_calls = getattr(msg, "tool_calls", None) or []
                for tc in raw_tool_calls:
                    fn = getattr(tc, "function", None)
                    tool_calls.append(
                        {
                            "id": getattr(tc, "id", ""),
                            "type": getattr(tc, "type", "function"),
                            "function": {
                                "name": getattr(fn, "name", "") if fn else "",
                                "arguments": getattr(fn, "arguments", "") if fn else "",
                            },
                        }
                    )

        usage_raw = getattr(raw, "usage", None)
        if usage_raw is not None:
            prompt_tokens = int(getattr(usage_raw, "prompt_tokens", 0) or 0)
            completion_tokens = int(getattr(usage_raw, "completion_tokens", 0) or 0)

        hidden_params = getattr(raw, "_hidden_params", None) or {}
        if isinstance(hidden_params, dict):
            cost_value = hidden_params.get("response_cost")
            if cost_value is not None:
                try:
                    cost_usd = Decimal(str(cost_value))
                except (ValueError, ArithmeticError):
                    cost_usd = Decimal("0")

        return ChatResponse(
            text=text,
            tool_calls=tool_calls,
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=cost_usd,
            ),
            raw=raw,
        )
