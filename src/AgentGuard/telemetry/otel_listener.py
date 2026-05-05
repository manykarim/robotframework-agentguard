"""Robot Framework Listener (API v3) that wires OTel into `log.html`.

Behaviour:
- On `start_test`, records the test start time and creates a per-test span store.
- On `end_test`, embeds a JSON `<details>` block of in-process spans (and the
  test verdict) into Robot's HTML log via `BuiltIn().log(..., html=True)`.
- If `OTEL_EXPORTER_OTLP_ENDPOINT` is set, attaches an OTLP exporter so spans
  also flow to a collector. Otherwise an in-memory exporter holds them so the
  listener can still embed them.

ADR-012 — JSON export is mandatory; HTML embedding is the QA-team affordance.
"""

from __future__ import annotations

import json
import logging
import os
from html import escape
from typing import TYPE_CHECKING, Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

if TYPE_CHECKING:
    from collections.abc import Sequence

    from opentelemetry.sdk.trace import ReadableSpan

logger = logging.getLogger("AgentGuard.telemetry.listener")

_PROVIDER_INITIALISED = False
_IN_MEMORY_EXPORTER: InMemorySpanExporter | None = None


def _ensure_tracer_provider() -> InMemorySpanExporter:
    """Install an SDK `TracerProvider` once and return the in-memory exporter."""
    global _PROVIDER_INITIALISED, _IN_MEMORY_EXPORTER

    if _PROVIDER_INITIALISED and _IN_MEMORY_EXPORTER is not None:
        return _IN_MEMORY_EXPORTER

    resource = Resource.create({"service.name": "AgentGuard"})
    provider = TracerProvider(resource=resource)

    in_memory = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(in_memory))

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
        except ImportError:
            logger.warning(
                "AgentGuard: OTEL_EXPORTER_OTLP_ENDPOINT set but "
                "opentelemetry-exporter-otlp not installed; skipping OTLP."
            )

    trace.set_tracer_provider(provider)
    _PROVIDER_INITIALISED = True
    _IN_MEMORY_EXPORTER = in_memory
    return in_memory


def _span_to_dict(span: ReadableSpan) -> dict[str, Any]:
    ctx = span.get_span_context()
    trace_id = format(ctx.trace_id, "032x") if ctx else ""
    span_id = format(ctx.span_id, "016x") if ctx else ""
    return {
        "name": span.name,
        "trace_id": trace_id,
        "span_id": span_id,
        "start_time": span.start_time,
        "end_time": span.end_time,
        "duration_ns": (span.end_time or 0) - (span.start_time or 0),
        "status": span.status.status_code.name,
        "attributes": dict(span.attributes or {}),
    }


class OTelListener:
    """Robot Framework Listener API v3 — embeds OTel spans into `log.html`."""

    ROBOT_LISTENER_API_VERSION = 3

    def __init__(self) -> None:
        self._exporter = _ensure_tracer_provider()
        self._test_span_offsets: dict[str, int] = {}

    def start_suite(self, data: Any, result: Any) -> None:
        suite_id = getattr(data, "id", "") or getattr(data, "name", "")
        logger.debug("AgentGuard.OTelListener: suite start id=%s", suite_id)

    def start_test(self, data: Any, result: Any) -> None:
        test_id = getattr(data, "id", "") or getattr(data, "name", "")
        finished = self._exporter.get_finished_spans()
        self._test_span_offsets[test_id] = len(finished)

    def end_test(self, data: Any, result: Any) -> None:
        test_id = getattr(data, "id", "") or getattr(data, "name", "")
        offset = self._test_span_offsets.pop(test_id, 0)
        finished = list(self._exporter.get_finished_spans())
        new_spans = finished[offset:]
        if not new_spans:
            return

        payload = {
            "test": getattr(data, "name", test_id),
            "status": getattr(result, "status", ""),
            "spans": [_span_to_dict(s) for s in new_spans],
        }
        snippet = self._render_html(payload)

        try:
            from robot.libraries.BuiltIn import BuiltIn

            BuiltIn().log(snippet, html=True)
        except Exception as exc:  # noqa: BLE001 — listener must never crash a test
            logger.debug("AgentGuard.OTelListener: log embed skipped (%s)", exc)

    def end_suite(self, data: Any, result: Any) -> None:
        return

    def log_message(self, message: Any) -> None:
        return

    @staticmethod
    def _render_html(payload: dict[str, Any]) -> str:
        body = json.dumps(payload, default=str, indent=2, sort_keys=True)
        return (
            "<details><summary>AgentGuard OTel spans</summary>"
            f'<pre style="white-space:pre-wrap">{escape(body)}</pre>'
            "</details>"
        )

    @classmethod
    def reset_for_tests(cls) -> None:
        global _PROVIDER_INITIALISED, _IN_MEMORY_EXPORTER
        _PROVIDER_INITIALISED = False
        _IN_MEMORY_EXPORTER = None


def collected_spans() -> Sequence[ReadableSpan]:
    """Test helper — returns every in-memory span recorded so far."""
    exporter = _ensure_tracer_provider()
    return exporter.get_finished_spans()
