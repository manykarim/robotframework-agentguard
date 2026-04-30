"""Unit tests for `AgentGuard.telemetry.otel_listener` + `spans`.

Listener behaviour: starts a tracer provider once, records new spans per test,
embeds the JSON payload into log.html via BuiltIn.log (best-effort, never
raises). Span helpers wrap `tool_call`, `judge`, `keyword` with mcp-eval-style
attributes.
"""

from __future__ import annotations

from typing import Any

import pytest

from AgentGuard.telemetry import (
    get_tracer,
    judge_span,
    keyword_span,
    tool_call_span,
)
from AgentGuard.telemetry.otel_listener import (
    OTelListener,
    _ensure_tracer_provider,
    _span_to_dict,
    collected_spans,
)


@pytest.fixture(autouse=True)
def _provider_installed() -> None:
    """Ensure the SDK TracerProvider is installed before each test."""
    _ensure_tracer_provider()


class _FakeData:
    def __init__(self, name: str = "T", id_: str = "s1-t1") -> None:
        self.name = name
        self.id = id_


class _FakeResult:
    def __init__(self, status: str = "PASS") -> None:
        self.status = status


class TestSpanHelpers:
    def test_tool_call_span_records_attributes(self) -> None:
        with tool_call_span("echo", server="svr", transport="memory", arguments={"x": 1}):
            pass
        spans = collected_spans()
        names = [s.name for s in spans]
        assert "tool_call:echo" in names
        match = next(s for s in spans if s.name == "tool_call:echo")
        attrs = dict(match.attributes or {})
        assert attrs["agentguard.kind"] == "tool_call"
        assert attrs["tool.name"] == "echo"
        assert attrs["mcp.server"] == "svr"
        assert attrs["mcp.transport"] == "memory"

    def test_judge_span_records_attributes(self) -> None:
        with judge_span("rubric.helpful", judge_model="gpt", sample_id="s1"):
            pass
        m = next(s for s in collected_spans() if s.name == "judge:rubric.helpful")
        attrs = dict(m.attributes or {})
        assert attrs["judge.rubric"] == "rubric.helpful"
        assert attrs["judge.model"] == "gpt"
        assert attrs["judge.sample_id"] == "s1"

    def test_keyword_span_records_attributes(self) -> None:
        with keyword_span("Call MCP Tool", library="AgentGuard", test_name="T1"):
            pass
        m = next(s for s in collected_spans() if s.name == "keyword:Call MCP Tool")
        attrs = dict(m.attributes or {})
        assert attrs["rf.keyword"] == "Call MCP Tool"
        assert attrs["rf.library"] == "AgentGuard"
        assert attrs["rf.test"] == "T1"

    def test_none_attribute_skipped(self) -> None:
        with tool_call_span("t", server=None, transport=None, arguments=None):
            pass
        m = next(s for s in collected_spans() if s.name == "tool_call:t")
        attrs = dict(m.attributes or {})
        assert "mcp.server" not in attrs

    def test_get_tracer_named(self) -> None:
        tr = get_tracer()
        # Smoke: starting a span must not error.
        with tr.start_as_current_span("noop"):
            pass


class TestListener:
    def test_listener_api_v3(self) -> None:
        assert OTelListener.ROBOT_LISTENER_API_VERSION == 3

    def test_lifecycle_emits_html_block(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        listener = OTelListener()

        embedded: list[str] = []

        class _FakeBuiltIn:
            def log(self, msg: str, html: bool = False) -> None:
                if html:
                    embedded.append(msg)

        # Patch BuiltIn import path used inside `end_test`.
        import sys
        import types

        fake_module = types.ModuleType("robot.libraries.BuiltIn")
        fake_module.BuiltIn = _FakeBuiltIn  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "robot.libraries.BuiltIn", fake_module)
        # Ensure parent module is importable too.
        if "robot.libraries" not in sys.modules:
            monkeypatch.setitem(sys.modules, "robot.libraries", types.ModuleType("robot.libraries"))

        data = _FakeData(name="MyTest", id_="s1-t1")
        result = _FakeResult(status="PASS")
        listener.start_suite(_FakeData("Suite", "s1"), _FakeResult())
        listener.start_test(data, result)
        with tool_call_span("echo"):
            pass
        listener.end_test(data, result)
        listener.end_suite(_FakeData("Suite", "s1"), _FakeResult())
        listener.log_message(object())

        assert embedded, "expected at least one HTML block injected"
        assert "tool_call:echo" in embedded[0]
        assert "AgentGuard OTel spans" in embedded[0]

    def test_no_new_spans_no_log(self, monkeypatch: pytest.MonkeyPatch) -> None:
        listener = OTelListener()

        class _Boom:
            def log(self, *_: Any, **__: Any) -> None:
                raise AssertionError("should not be called")

        import sys
        import types
        fake_module = types.ModuleType("robot.libraries.BuiltIn")
        fake_module.BuiltIn = _Boom  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "robot.libraries.BuiltIn", fake_module)

        data = _FakeData()
        listener.start_test(data, _FakeResult())
        listener.end_test(data, _FakeResult())  # no spans → no log

    def test_end_test_swallows_log_failures(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        listener = OTelListener()

        # Make the BuiltIn import fail entirely.
        import builtins
        real_import = builtins.__import__

        def fail_import(name: str, *a: Any, **kw: Any) -> Any:
            if name == "robot.libraries.BuiltIn":
                raise RuntimeError("simulated failure")
            return real_import(name, *a, **kw)

        monkeypatch.setattr(builtins, "__import__", fail_import)
        d = _FakeData()
        listener.start_test(d, _FakeResult())
        with tool_call_span("t"):
            pass
        # Must not raise
        listener.end_test(d, _FakeResult())

    def test_span_to_dict_shape(self) -> None:
        with tool_call_span("dict-shape"):
            pass
        s = next(x for x in collected_spans() if x.name == "tool_call:dict-shape")
        d = _span_to_dict(s)
        assert {"name", "trace_id", "span_id", "duration_ns", "status", "attributes"} <= d.keys()
        assert d["name"] == "tool_call:dict-shape"
        assert isinstance(d["trace_id"], str) and len(d["trace_id"]) == 32

    def test_provider_singleton(self) -> None:
        a = _ensure_tracer_provider()
        b = _ensure_tracer_provider()
        assert a is b

    def test_otlp_endpoint_warns_when_exporter_missing(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        OTelListener.reset_for_tests()
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

        # Force ImportError from the OTLP exporter import.
        import builtins
        real_import = builtins.__import__

        def fake_import(name: str, *a: Any, **kw: Any) -> Any:
            if name.startswith("opentelemetry.exporter.otlp"):
                raise ImportError("simulated")
            return real_import(name, *a, **kw)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        import logging
        with caplog.at_level(logging.WARNING, logger="AgentGuard.telemetry.listener"):
            _ensure_tracer_provider()
        assert any("OTLP" in m for m in caplog.messages)
