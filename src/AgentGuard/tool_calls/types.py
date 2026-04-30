"""Public dataclasses for the ToolCallCorrectness bounded context (ADR-004).

These are the only types exchanged with other contexts (skills, mcp, judge),
so changes here are breaking. Keep them small, frozen where it makes sense,
and free of provider-specific shape leakage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

JSON = str | int | float | bool | None | list["JSON"] | dict[str, "JSON"]
"""Recursive JSON-compatible value type used by tool arguments."""

MatchMode = Literal["strict", "ast", "semantic"]
"""Argument-comparison strategies (research §3.1, ADR-004)."""


@dataclass(slots=True, frozen=True)
class ToolCall:
    """Provider-neutral tool call.

    The OpenAI ``{id, type, function:{name, arguments}}`` envelope from
    ``ChatResponse.tool_calls`` is normalised into this shape via
    :func:`AgentGuard.tool_calls.bfcl_matcher.coerce_tool_call`.

    ``arguments`` is always a parsed dict (never a JSON string) so downstream
    matchers do not need to re-parse on every comparison.
    """

    name: str
    arguments: dict[str, JSON] = field(default_factory=dict)
    id: str | None = None


@dataclass(slots=True, frozen=True)
class ExpectedCall:
    """Single expected tool invocation used by ground truth assertions.

    ``arguments`` may use BFCL "possible answers" semantics: a value of
    ``[v1, v2, ...]`` means "any of these is acceptable". A scalar is treated
    as a one-element possible-answers list internally.
    """

    name: str
    arguments: dict[str, JSON] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class MatchResult:
    """Detailed comparison outcome — surfaced into Robot's ``log.html``."""

    matched: bool
    reasons: tuple[str, ...] = ()
    diff: dict[str, JSON] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.matched


@dataclass(slots=True, frozen=True)
class ToolDefinition:
    """OpenAI-style tool / function definition (the same shape MCP exposes).

    Stored as a dict so we can pass it straight through to providers without
    re-shaping. ``name`` and ``parameters`` are surfaced for matcher use.
    """

    name: str
    description: str = ""
    parameters: dict[str, JSON] = field(default_factory=dict)

    def to_openai(self) -> dict[str, JSON]:
        """Render as the OpenAI/LiteLLM ``tools`` element."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass(slots=True, frozen=True)
class BFCLCase:
    """One row of a BFCL-shaped dataset (single-turn, simple/parallel/multiple)."""

    prompt: str
    tools: tuple[ToolDefinition, ...]
    expected: tuple[ExpectedCall, ...]
    category: str = "simple"
    case_id: str = ""

    @property
    def expected_call(self) -> ExpectedCall:
        """Convenience accessor for ``simple`` cases (single expected call)."""
        if not self.expected:
            raise ValueError(f"BFCLCase {self.case_id!r} has no expected calls")
        return self.expected[0]


@dataclass(slots=True, frozen=True)
class Prediction:
    """Predicted ``ToolCall``\\ s for a single ``BFCLCase``.

    Used by ``BFCL Score Should Be Above`` to compute per-category accuracy.
    """

    case: BFCLCase
    actual: tuple[ToolCall, ...]


__all__ = [
    "BFCLCase",
    "ExpectedCall",
    "JSON",
    "MatchMode",
    "MatchResult",
    "Prediction",
    "ToolCall",
    "ToolDefinition",
]
