"""ToolCallKeywords — Robot Framework surface for the ToolCallCorrectness context.

Composed into the top-level :class:`AgentGuard.AgentGuard` library via
``DynamicCore`` registration. All keywords are sync; ``Generate Tool Call`` is
the only one that touches the provider, which is dependency-injected through
the ``provider=`` argument from ``library.py``.

Tier-1 keywords (everything except ``Generate Tool Call``) are pure-Python and
work without an API key (ADR-019). They never raise on a value mismatch —
they raise :class:`AssertionError` so Robot reports them as test failures.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, Protocol

import jsonschema
from robot.api.deco import keyword

from AgentGuard.tool_calls.bfcl_matcher import (
    coerce_tool_call,
    match_arguments_detailed,
    match_name,
)
from AgentGuard.tool_calls.datasets import load_bfcl
from AgentGuard.tool_calls.trajectory import (
    bfcl_score,
    extract_tool_names,
    match_parallel,
    match_sequence,
)
from AgentGuard.tool_calls.trajectory import (
    should_not_call_any_tool as _should_not_call_any_tool,
)
from AgentGuard.tool_calls.types import (
    JSON,
    BFCLCase,
    ExpectedCall,
    MatchMode,
    Prediction,
    ToolCall,
    ToolDefinition,
)

logger = logging.getLogger("AgentGuard.tool_calls")


class _ProviderLike(Protocol):
    """Minimal local stub of :class:`AgentGuard.providers.base.LLMProviderAdapter`.

    Only ``chat`` is required by ``Generate Tool Call``.
    """

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> Any: ...


if TYPE_CHECKING:  # pragma: no cover
    from AgentGuard.providers.base import LLMProviderAdapter as _Adapter
else:
    try:
        from AgentGuard.providers.base import LLMProviderAdapter as _Adapter
    except ImportError:  # foundation may finalise this later
        _Adapter = _ProviderLike  # type: ignore[misc, assignment]


class ToolCallKeywords:
    """Robot Framework keywords for BFCL-style tool-call correctness."""

    def __init__(
        self,
        provider: _Adapter | None = None,
        *,
        default_model: str | None = None,
    ) -> None:
        self._provider = provider
        self._default_model = default_model

    # ---- name / argument matching ------------------------------------------

    @keyword(name="Tool Call Should Match Name")
    def tool_call_should_match_name(
        self,
        actual: ToolCall | dict[str, Any],
        expected: str,
    ) -> None:
        """Assert the actual tool call invokes ``expected`` (exact string)."""
        if not match_name(actual, expected):
            got = self._safe_name(actual)
            raise AssertionError(
                f"Tool name mismatch: expected {expected!r}, got {got!r}"
            )

    @keyword(name="Tool Call Arguments Should Match")
    def tool_call_arguments_should_match(
        self,
        actual: ToolCall | dict[str, Any],
        expected: dict[str, JSON] | str,
        mode: MatchMode = "ast",
        schema: dict[str, JSON] | None = None,
    ) -> None:
        """Assert AST equality of arguments. ``mode`` ∈ {strict, ast, semantic}.

        ``semantic`` is rejected here because this library tier is offline; the
        suite-level ``Generate Tool Call`` plus a judge keyword should be used
        to escalate. See ADR-004 / ADR-011.
        """
        result = match_arguments_detailed(actual, expected, schema=schema, mode=mode)
        if not result:
            reasons = "; ".join(result.reasons) or "no reason recorded"
            raise AssertionError(
                f"Tool arguments do not match (mode={mode}): {reasons}"
            )

    @keyword(name="Required Parameters Should Be Present")
    def required_parameters_should_be_present(
        self,
        actual: ToolCall | dict[str, Any],
        schema: dict[str, JSON],
    ) -> None:
        """Validate ``actual.arguments`` against a JSON Schema (``required`` only).

        Uses :mod:`jsonschema`. Validation errors are aggregated into a single
        :class:`AssertionError` so the Robot log shows every missing field.
        """
        call = coerce_tool_call(actual)
        validator = jsonschema.Draft7Validator(schema)
        errors = sorted(validator.iter_errors(call.arguments), key=lambda e: e.path)
        # Filter to the "required" failures, which is what the keyword name promises.
        required_errors = [e for e in errors if e.validator == "required"]
        if required_errors:
            details = "; ".join(e.message for e in required_errors)
            raise AssertionError(
                f"Missing required parameter(s) for {call.name!r}: {details}"
            )

    # ---- parallel / sequence ------------------------------------------------

    @keyword(name="Parallel Tool Calls Should Match")
    def parallel_tool_calls_should_match(
        self,
        actual: list[ToolCall | dict[str, Any]],
        expected: list[ToolCall | dict[str, Any]],
    ) -> None:
        """Assert multiset equality of (name, args) over the two lists."""
        if not match_parallel(actual, expected):
            raise AssertionError(
                f"Parallel tool calls do not match: "
                f"got {len(actual)} call(s), expected {len(expected)}"
            )

    @keyword(name="Tool Sequence Should Match")
    def tool_sequence_should_match(
        self,
        actual_seq: list[ToolCall | dict[str, Any]],
        expected_seq: list[str | dict[str, Any] | ToolCall],
        wildcards: bool = True,
    ) -> None:
        """Ordered subsequence match; ``"*"`` matches any single call.

        With ``wildcards=False`` the comparison is element-for-element.
        """
        if not match_sequence(actual_seq, expected_seq, wildcards=wildcards):
            actual_names = [
                self._safe_name(c) for c in actual_seq
            ]
            raise AssertionError(
                f"Tool sequence does not match expected order. "
                f"Actual names: {actual_names}; expected length: {len(expected_seq)}"
            )

    @keyword(name="Should Not Call Any Tool")
    def should_not_call_any_tool(
        self,
        actual_seq: list[ToolCall | dict[str, Any]],
    ) -> None:
        """BFCL ``decide-not-to-act``: assert no tool was called."""
        if not _should_not_call_any_tool(actual_seq):
            names = [self._safe_name(c) for c in actual_seq]
            raise AssertionError(
                f"Expected no tool calls, but got {len(names)}: {names}"
            )

    # ---- BFCL dataset + scoring --------------------------------------------

    @keyword(name="Load BFCL Dataset")
    def load_bfcl_dataset(
        self,
        category: str = "simple",
        limit: int | None = None,
    ) -> list[BFCLCase]:
        """Load BFCL cases via :class:`AgentGuard.tool_calls.datasets.BFCLAdapter`."""
        cases = load_bfcl(category=category, limit=limit)
        logger.info("loaded %d BFCL case(s) for category=%r", len(cases), category)
        return cases

    @keyword(name="BFCL Score Should Be Above")
    def bfcl_score_should_be_above(
        self,
        predictions: list[Prediction],
        threshold: float,
        dataset: str = "simple",
    ) -> float:
        """Compute mean per-case score; raise if it is below ``threshold``."""
        if not predictions:
            raise AssertionError("BFCL Score: predictions list is empty")
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"threshold must be in [0,1], got {threshold!r}")

        scores: list[float] = [
            bfcl_score(
                actual=list(p.actual),
                expected=[
                    ToolCall(name=ec.name, arguments=dict(ec.arguments))
                    for ec in p.case.expected
                ],
            )
            for p in predictions
        ]
        mean = sum(scores) / len(scores)
        logger.info(
            "BFCL %s score over %d case(s): %.3f (threshold %.3f)",
            dataset,
            len(predictions),
            mean,
            threshold,
        )
        if mean < threshold:
            raise AssertionError(
                f"BFCL {dataset} score {mean:.3f} < threshold {threshold:.3f}"
            )
        return mean

    # ---- provider-touching keyword -----------------------------------------

    @keyword(name="Generate Tool Call")
    def generate_tool_call(
        self,
        prompt: str,
        tools: list[ToolDefinition | dict[str, Any]],
        model: str | None = None,
    ) -> list[ToolCall]:
        """Call the suite-level provider; return its parsed tool calls.

        When no provider is wired we raise — unlike skills, there is no
        meaningful "mock tool call" we can fabricate without violating the
        BFCL contract. Tests that need offline behaviour should construct
        :class:`ToolCall`\\ s directly or use ``MockProvider``.
        """
        if self._provider is None:
            raise RuntimeError(
                "Generate Tool Call requires a provider; configure the AgentGuard "
                "library with provider=litellm or inject a MockProvider in tests."
            )
        target_model = model or self._default_model
        openai_tools = [_to_openai_tool(t) for t in tools]
        t0 = time.perf_counter()
        response = self._provider.chat(
            messages=[{"role": "user", "content": prompt}],
            tools=openai_tools,
            model=target_model,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        logger.debug("provider responded in %.1fms", elapsed_ms)

        raw_calls = getattr(response, "tool_calls", []) or []
        return [coerce_tool_call(rc) for rc in raw_calls]

    # ---- helpers ------------------------------------------------------------

    @staticmethod
    def _safe_name(call: ToolCall | dict[str, Any]) -> str:
        try:
            return coerce_tool_call(call).name
        except ValueError:
            return "<malformed>"

    @keyword(name="Extract Tool Names From Messages")
    def extract_tool_names_from_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> list[str]:
        """Return the ordered list of tool names called across an assistant transcript."""
        return extract_tool_names(messages)


def _to_openai_tool(tool: ToolDefinition | dict[str, Any]) -> dict[str, Any]:
    if isinstance(tool, ToolDefinition):
        rendered = tool.to_openai()
        return dict(rendered)
    if isinstance(tool, dict):
        if tool.get("type") == "function" and "function" in tool:
            return tool
        return {
            "type": "function",
            "function": {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
                "parameters": tool.get("parameters", {}),
            },
        }
    raise TypeError(f"unsupported tool definition type: {type(tool).__name__}")


# Backwards-compat alias used by ``DynamicCore`` registration.
ToolCallLibrary = ToolCallKeywords


# Re-export ExpectedCall for convenience in test suites.
__all__ = [
    "ExpectedCall",
    "ToolCallKeywords",
    "ToolCallLibrary",
]
