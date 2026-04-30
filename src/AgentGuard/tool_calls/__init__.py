"""ToolCallCorrectness bounded context — BFCL AST-equality matchers (ADR-004).

Public surface (Phase 1):

* :class:`ToolCallKeywords` — Robot Framework keyword class composed into the
  top-level :class:`AgentGuard.AgentGuard` library.
* :func:`ast_equal`, :func:`match_arguments`, :func:`match_name`,
  :func:`call_signature`, :func:`coerce_tool_call`, :func:`normalize`
  — pure-Python AST equality core.
* :func:`match_parallel`, :func:`match_sequence`, :func:`bfcl_score`,
  :func:`extract_tool_names` — trajectory utilities.
* :class:`BFCLAdapter`, :func:`load_bfcl` — BFCL dataset access.
* :class:`ToolCall`, :class:`ExpectedCall`, :class:`MatchResult`,
  :class:`BFCLCase`, :class:`Prediction`, :class:`ToolDefinition`
  — dataclasses exchanged with other bounded contexts.
"""

from __future__ import annotations

from AgentGuard.tool_calls.bfcl_matcher import (
    ast_equal,
    call_signature,
    coerce_tool_call,
    match_arguments,
    match_arguments_detailed,
    match_name,
    normalize,
)
from AgentGuard.tool_calls.datasets import (
    BFCLAdapter,
    load_bfcl,
)
from AgentGuard.tool_calls.library import ToolCallKeywords, ToolCallLibrary
from AgentGuard.tool_calls.trajectory import (
    bfcl_score,
    extract_tool_names,
    match_parallel,
    match_sequence,
    normalise_trajectory,
    should_not_call_any_tool,
)
from AgentGuard.tool_calls.types import (
    JSON,
    BFCLCase,
    ExpectedCall,
    MatchMode,
    MatchResult,
    Prediction,
    ToolCall,
    ToolDefinition,
)

__all__ = [
    "BFCLAdapter",
    "BFCLCase",
    "ExpectedCall",
    "JSON",
    "MatchMode",
    "MatchResult",
    "Prediction",
    "ToolCall",
    "ToolCallKeywords",
    "ToolCallLibrary",
    "ToolDefinition",
    "ast_equal",
    "bfcl_score",
    "call_signature",
    "coerce_tool_call",
    "extract_tool_names",
    "load_bfcl",
    "match_arguments",
    "match_arguments_detailed",
    "match_name",
    "match_parallel",
    "match_sequence",
    "normalise_trajectory",
    "normalize",
    "should_not_call_any_tool",
]
