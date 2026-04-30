"""mcp-eval-compatible span helpers.

Span names and attribute keys mirror the conventions used by `mcp-eval` so
existing dashboards (Grafana, Allure, ReportPortal) ingest AgentGuard traces
without remapping. See ADR-012 §Rationale.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from opentelemetry import trace
from opentelemetry.trace import Tracer

if TYPE_CHECKING:
    from collections.abc import Iterator

_TRACER_NAME = "AgentGuard"


def get_tracer() -> Tracer:
    return trace.get_tracer(_TRACER_NAME)


def _set_attrs(span: trace.Span, attrs: dict[str, Any]) -> None:
    for k, v in attrs.items():
        if v is None:
            continue
        if isinstance(v, (str, bool, int, float)):
            span.set_attribute(k, v)
        else:
            span.set_attribute(k, str(v))


@contextmanager
def tool_call_span(
    tool_name: str,
    *,
    server: str | None = None,
    transport: str | None = None,
    arguments: dict[str, Any] | None = None,
) -> Iterator[trace.Span]:
    """Span for one MCP / agent tool call. Mirrors `mcp-eval` `tool_call`."""
    tracer = get_tracer()
    with tracer.start_as_current_span(f"tool_call:{tool_name}") as span:
        _set_attrs(
            span,
            {
                "agentguard.kind": "tool_call",
                "tool.name": tool_name,
                "mcp.server": server,
                "mcp.transport": transport,
                "tool.arguments": arguments,
            },
        )
        yield span


@contextmanager
def judge_span(
    rubric: str,
    *,
    judge_model: str | None = None,
    sample_id: str | None = None,
) -> Iterator[trace.Span]:
    """Span for one LLM-as-Judge classification."""
    tracer = get_tracer()
    with tracer.start_as_current_span(f"judge:{rubric}") as span:
        _set_attrs(
            span,
            {
                "agentguard.kind": "judge",
                "judge.rubric": rubric,
                "judge.model": judge_model,
                "judge.sample_id": sample_id,
            },
        )
        yield span


@contextmanager
def keyword_span(
    keyword_name: str,
    *,
    library: str = "AgentGuard",
    test_name: str | None = None,
) -> Iterator[trace.Span]:
    """Span for one Robot Framework keyword execution."""
    tracer = get_tracer()
    with tracer.start_as_current_span(f"keyword:{keyword_name}") as span:
        _set_attrs(
            span,
            {
                "agentguard.kind": "keyword",
                "rf.keyword": keyword_name,
                "rf.library": library,
                "rf.test": test_name,
            },
        )
        yield span
