"""Telemetry context — OTel span helpers + Robot Framework listener.

See ADR-012 (OpenTelemetry + Robot Framework Listener).
"""

from AgentGuard.telemetry.spans import (
    get_tracer,
    judge_span,
    keyword_span,
    tool_call_span,
)

__all__ = [
    "get_tracer",
    "judge_span",
    "keyword_span",
    "tool_call_span",
]
