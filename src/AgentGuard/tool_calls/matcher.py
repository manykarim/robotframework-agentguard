"""Compatibility shim — re-exports the BFCL matcher API.

The Phase-1 spec splits the matcher implementation across
:mod:`AgentGuard.tool_calls.bfcl_matcher` (AST equality core) and
:mod:`AgentGuard.tool_calls.trajectory` (parallel/sequence). The unit-test
suite was written against a flatter ``matcher`` module name, so this file
re-exports the same callables under their original spellings to keep the
import path stable for tests.

There is no logic here — only ``from ... import``.
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
from AgentGuard.tool_calls.trajectory import (
    bfcl_score,
    extract_tool_names,
    match_parallel,
    match_sequence,
    should_not_call_any_tool,
)

__all__ = [
    "ast_equal",
    "bfcl_score",
    "call_signature",
    "coerce_tool_call",
    "extract_tool_names",
    "match_arguments",
    "match_arguments_detailed",
    "match_name",
    "match_parallel",
    "match_sequence",
    "normalize",
    "should_not_call_any_tool",
]
