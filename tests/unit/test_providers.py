"""Unit tests for `AgentGuard.providers` (mock + LiteLLM via offline `mock_response=`).

Covers:
- `build_provider` factory: name resolution, mock + litellm + Phase-2 sentinel.
- `MockProvider`: queue replay, `strict` exhaustion, capability probe, call recording.
- `LiteLLMAdapter`: normalisation of tool calls, usage, cost; exception mapping.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from AgentGuard.providers import (
    AuthenticationError,
    ChatResponse,
    LLMProviderAdapter,
    ProviderAPIError,
    RateLimitError,
    Usage,
    build_provider,
)
from AgentGuard.providers.factory import _PHASE_2
from AgentGuard.providers.litellm_adapter import LiteLLMAdapter
from AgentGuard.providers.mock import MockProvider


class TestFactory:
    @pytest.mark.parametrize("name", ["", "litellm", "default", "LITELLM", "  default  "])
    def test_default_returns_litellm(self, name: str) -> None:
        prov = build_provider(name, model="openrouter/foo")
        assert isinstance(prov, LiteLLMAdapter)
        assert prov.default_model == "openrouter/foo"

    def test_mock_returns_mock(self) -> None:
        prov = build_provider("mock")
        assert isinstance(prov, MockProvider)
        assert prov.name == "mock"

    @pytest.mark.parametrize("name", sorted(_PHASE_2))
    def test_phase2_raises_not_implemented(self, name: str) -> None:
        with pytest.raises(NotImplementedError):
            build_provider(name)

    def test_unknown_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown provider"):
            build_provider("nonsense-2099")

    def test_protocol_runtime_check(self) -> None:
        prov = build_provider("mock")
        assert isinstance(prov, LLMProviderAdapter)


class TestMockProvider:
    def test_replays_queue_in_order(self, mock_provider: MockProvider) -> None:
        first = mock_provider.chat([{"role": "user", "content": "ping"}])
        second = mock_provider.chat([{"role": "user", "content": "ping"}])
        assert first.text == "hello"
        assert second.text == "world"
        assert second.tool_calls and second.tool_calls[0]["function"]["name"] == "echo"

    def test_repeats_last_when_drained(self) -> None:
        prov = MockProvider(responses=[ChatResponse(text="only")])
        a = prov.chat([{"role": "user", "content": "x"}])
        b = prov.chat([{"role": "user", "content": "x"}])
        assert a.text == b.text == "only"

    def test_strict_raises_on_exhaustion(self) -> None:
        prov = MockProvider(responses=[ChatResponse(text="one")], strict=True)
        prov.chat([{"role": "user", "content": "x"}])
        with pytest.raises(ProviderAPIError):
            prov.chat([{"role": "user", "content": "x"}])

    def test_strict_with_no_responses_raises(self) -> None:
        prov = MockProvider(strict=True)
        with pytest.raises(ProviderAPIError):
            prov.chat([{"role": "user", "content": "x"}])

    def test_records_calls(self) -> None:
        prov = MockProvider(responses=[ChatResponse(text="a")])
        prov.chat(
            [{"role": "user", "content": "hi"}],
            tools=[{"type": "function", "function": {"name": "f"}}],
            model="m1",
            extra="kw",
        )
        assert len(prov.calls) == 1
        rec = prov.calls[0]
        assert rec["messages"][0]["content"] == "hi"
        assert rec["tools"][0]["function"]["name"] == "f"
        assert rec["model"] == "m1"
        assert rec["kwargs"]["extra"] == "kw"

    def test_enqueue_appends(self) -> None:
        prov = MockProvider(strict=True)
        prov.enqueue(ChatResponse(text="late"))
        out = prov.chat([{"role": "user", "content": "x"}])
        assert out.text == "late"

    def test_supports_default_capability(self) -> None:
        prov = MockProvider()
        assert prov.supports("tool_calls") is True
        assert prov.supports("extended_thinking") is False

    def test_supports_custom_capabilities(self) -> None:
        prov = MockProvider(capabilities=frozenset({"foo", "bar"}))
        assert prov.supports("foo") is True
        assert prov.supports("tool_calls") is False

    def test_cost_returns_response_cost(self) -> None:
        prov = MockProvider(
            responses=[
                ChatResponse(
                    text="x",
                    usage=Usage(prompt_tokens=1, completion_tokens=1, cost_usd=Decimal("0.05")),
                )
            ]
        )
        resp = prov.chat([{"role": "user", "content": "x"}])
        assert prov.cost(resp) == Decimal("0.05")


# -------------------- LiteLLM offline (mock_response=) ----------------------


class _FakeMessage:
    def __init__(self, content: str = "", tool_calls: list[Any] | None = None) -> None:
        self.content = content
        self.tool_calls = tool_calls


class _FakeChoice:
    def __init__(self, message: _FakeMessage) -> None:
        self.message = message


class _FakeUsage:
    def __init__(self, prompt: int, completion: int) -> None:
        self.prompt_tokens = prompt
        self.completion_tokens = completion


class _FakeToolCall:
    def __init__(self, fid: str, name: str, args: str) -> None:
        self.id = fid
        self.type = "function"

        class _Fn:
            pass

        self.function = _Fn()
        self.function.name = name
        self.function.arguments = args


class _FakeResponse:
    def __init__(
        self,
        text: str = "",
        tool_calls: list[Any] | None = None,
        prompt: int = 1,
        completion: int = 2,
        cost: float | None = 0.0001,
    ) -> None:
        self.choices = [_FakeChoice(_FakeMessage(text, tool_calls))]
        self.usage = _FakeUsage(prompt, completion)
        self._hidden_params = {"response_cost": cost}


class TestLiteLLMAdapter:
    def test_normalises_text_and_usage(self, monkeypatch: pytest.MonkeyPatch) -> None:
        adapter = LiteLLMAdapter(model="mockllm/model")

        import litellm

        def fake_completion(**_kw: Any) -> _FakeResponse:
            return _FakeResponse(text="out", prompt=10, completion=20, cost=0.0003)

        monkeypatch.setattr(litellm, "completion", fake_completion)

        resp = adapter.chat([{"role": "user", "content": "hi"}])
        assert resp.text == "out"
        assert resp.usage.prompt_tokens == 10
        assert resp.usage.completion_tokens == 20
        assert resp.usage.cost_usd == Decimal("0.0003")

    def test_normalises_tool_calls(self, monkeypatch: pytest.MonkeyPatch) -> None:
        adapter = LiteLLMAdapter(model="mockllm/model")

        import litellm

        def fake_completion(**_kw: Any) -> _FakeResponse:
            return _FakeResponse(
                text="",
                tool_calls=[_FakeToolCall("c1", "echo", '{"x": 1}')],
            )

        monkeypatch.setattr(litellm, "completion", fake_completion)

        resp = adapter.chat([{"role": "user", "content": "use tool"}])
        assert len(resp.tool_calls) == 1
        tc = resp.tool_calls[0]
        assert tc["id"] == "c1"
        assert tc["type"] == "function"
        assert tc["function"]["name"] == "echo"
        assert tc["function"]["arguments"] == '{"x": 1}'

    def test_no_model_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        adapter = LiteLLMAdapter(model=None)
        with pytest.raises(ProviderAPIError, match="No model"):
            adapter.chat([{"role": "user", "content": "x"}])

    def test_rate_limit_normalised(self, monkeypatch: pytest.MonkeyPatch) -> None:
        adapter = LiteLLMAdapter(model="mockllm/model")
        import litellm
        from litellm import exceptions as lex

        def boom(**_kw: Any) -> Any:
            raise lex.RateLimitError("429 quota exceeded", llm_provider="openrouter", model="m")

        monkeypatch.setattr(litellm, "completion", boom)
        with pytest.raises(RateLimitError):
            adapter.chat([{"role": "user", "content": "x"}])

    def test_auth_error_normalised(self, monkeypatch: pytest.MonkeyPatch) -> None:
        adapter = LiteLLMAdapter(model="mockllm/model")
        import litellm
        from litellm import exceptions as lex

        def boom(**_kw: Any) -> Any:
            raise lex.AuthenticationError("401 invalid key", llm_provider="openrouter", model="m")

        monkeypatch.setattr(litellm, "completion", boom)
        with pytest.raises(AuthenticationError):
            adapter.chat([{"role": "user", "content": "x"}])

    def test_api_error_normalised(self, monkeypatch: pytest.MonkeyPatch) -> None:
        adapter = LiteLLMAdapter(model="mockllm/model")
        import litellm
        from litellm import exceptions as lex

        def boom(**_kw: Any) -> Any:
            raise lex.APIError(500, "upstream 500", llm_provider="openrouter", model="m")

        monkeypatch.setattr(litellm, "completion", boom)
        with pytest.raises(ProviderAPIError):
            adapter.chat([{"role": "user", "content": "x"}])

    def test_unknown_exception_normalised(self, monkeypatch: pytest.MonkeyPatch) -> None:
        adapter = LiteLLMAdapter(model="mockllm/model")
        import litellm

        def boom(**_kw: Any) -> Any:
            raise RuntimeError("unexpected")

        monkeypatch.setattr(litellm, "completion", boom)
        with pytest.raises(ProviderAPIError, match="LiteLLM call failed"):
            adapter.chat([{"role": "user", "content": "x"}])

    def test_supports_known_capabilities(self) -> None:
        adapter = LiteLLMAdapter(model="m")
        assert adapter.supports("tool_calls")
        assert adapter.supports("streaming")
        assert not adapter.supports("magic_unicorn")

    def test_normalisation_handles_missing_fields(self) -> None:
        class Minimal:
            choices: list[Any] = []
            usage: Any = None
            _hidden_params: dict[str, Any] = {}

        out = LiteLLMAdapter._normalise(Minimal())
        assert out.text == ""
        assert out.tool_calls == []
        assert out.usage.prompt_tokens == 0

    def test_normalisation_bad_cost_falls_back_to_zero(self) -> None:
        class Hidden:
            choices: list[Any] = []
            usage: Any = None
            _hidden_params: dict[str, Any] = {"response_cost": "not-a-number"}

        out = LiteLLMAdapter._normalise(Hidden())
        assert out.usage.cost_usd == Decimal("0")

    def test_version_property(self) -> None:
        adapter = LiteLLMAdapter(model="m")
        assert isinstance(adapter.version, str)


class TestExceptionHierarchy:
    def test_rate_limit_is_provider_error(self) -> None:
        from AgentGuard.providers.base import AgentGuardProviderError

        assert issubclass(RateLimitError, AgentGuardProviderError)
        assert issubclass(AuthenticationError, AgentGuardProviderError)
        assert issubclass(ProviderAPIError, AgentGuardProviderError)


class TestChatResponseDataclass:
    def test_default_values(self) -> None:
        r = ChatResponse()
        assert r.text == ""
        assert r.tool_calls == []
        assert r.usage.prompt_tokens == 0

    def test_usage_immutable(self) -> None:
        u = Usage(prompt_tokens=1, completion_tokens=2, cost_usd=Decimal("0.5"))
        with pytest.raises(AttributeError):
            u.prompt_tokens = 99  # type: ignore[misc]
