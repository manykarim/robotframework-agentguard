"""Integration — exercise AgentGuard's MCP keywords against the live ``rf-mcp`` server.

`rf-mcp` (https://github.com/manykarim/rf-mcp) is the Robot Framework MCP server.
Its module-level FastMCP instance is exposed at ``robotmcp.server.mcp``, so the
in-memory transport from AgentGuard's MCP module binds directly with no subprocess
fragility (see Phase 1 exp_01: ~2 ms/call in-memory roundtrip).

Tests skip cleanly when ``rf-mcp`` is not installed — use ``uv add
'robotframework-agentguard[integrations]'`` or ``pip install rf-mcp``.

PROPOSAL-library-import-structure §3 + §6: imports use the façade form
``from AgentGuard.MCP import MCP`` (Python equivalent of ``Library AgentGuard.MCP``)
rather than the deep ``AgentGuard.mcp.library`` path. The façade aliases the
underlying ``MCPKeywords`` class so the call sites are identical.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

# Façade import — equivalent to `Library AgentGuard.MCP` per
# PROPOSAL-library-import-structure §6. `MCP` is the alias for `MCPKeywords`.
from AgentGuard.MCP import MCP

# ---------------------------------------------------------------------------
# Skip whole module when rf-mcp is not importable. We try the installed package
# first, then a local clone at /home/<user>/workspace/rf-mcp so contributors
# working from a checkout can run these without pip-installing.
# ---------------------------------------------------------------------------
_LOCAL_CLONE = Path.home() / "workspace" / "rf-mcp" / "src"
if importlib.util.find_spec("robotmcp") is None and _LOCAL_CLONE.exists():
    sys.path.insert(0, str(_LOCAL_CLONE))

if importlib.util.find_spec("robotmcp") is None:
    pytest.skip(
        "rf-mcp not installed; run `uv add 'robotframework-agentguard[integrations]'`"
        " or `pip install rf-mcp` to enable.",
        allow_module_level=True,
    )

# Importing robotmcp.server triggers heavy module init (RF runtime + plugins);
# defer to fixture so collection is fast.


@pytest.fixture(scope="module")
def rf_mcp_server() -> Any:
    # FastMCP instance type varies across rf-mcp releases — keep as Any.
    server_mod = importlib.import_module("robotmcp.server")
    return server_mod.mcp


@pytest.fixture
def kw() -> MCP:
    # Constructed via the façade alias so the production ``Library AgentGuard.MCP``
    # path is exercised end-to-end (the alias and the deep class are the same
    # object — see tests/unit/test_library_facades.py).
    return MCP()


# ---- protocol-compliance smoke tests ---------------------------------------


def test_in_memory_connect_lists_tools(kw: MCP, rf_mcp_server: Any) -> None:
    handle = kw.connect_to_mcp_server(rf_mcp_server, transport="memory")
    try:
        # `List MCP Tools` returns a list[dict[str, Any]]; per DDD §6 it is NOT
        # a Should-pair candidate (no scalar to compare). Verify shape via the
        # standard pytest assertion vocabulary.
        tools = kw.list_mcp_tools(handle)
        assert isinstance(tools, list)
        # rf-mcp 0.31 ships ~21 tools across planning, session, discovery, etc.
        assert len(tools) >= 10, f"expected >= 10 tools, got {len(tools)}: {[t.get('name') for t in tools]}"
    finally:
        kw.stop_mcp_server(handle)


@pytest.mark.parametrize(
    "expected",
    [
        # Names documented in rf-mcp README; if upstream renames, this list will need updating.
        "analyze_scenario",
        "find_keywords",
        "manage_session",
        "execute_step",
        "get_session_state",
    ],
)
def test_documented_tool_is_present(kw: MCP, rf_mcp_server: Any, expected: str) -> None:
    handle = kw.connect_to_mcp_server(rf_mcp_server, transport="memory")
    try:
        names = {t["name"] for t in kw.list_mcp_tools(handle)}
        assert expected in names, f"{expected!r} not in {sorted(names)}"
    finally:
        kw.stop_mcp_server(handle)


def test_get_capabilities_returns_dict(kw: MCP, rf_mcp_server: Any) -> None:
    handle = kw.connect_to_mcp_server(rf_mcp_server, transport="memory")
    try:
        caps = kw.get_mcp_capabilities(handle)
        assert isinstance(caps, dict)
        # FastMCP servers always advertise tools; we don't assert on resources/prompts since
        # rf-mcp's surface evolves across releases.
        assert "tools" in caps
    finally:
        kw.stop_mcp_server(handle)


def test_mcp_server_implements_capabilities_keyword_form(kw: MCP, rf_mcp_server: Any) -> None:
    """The variadic predicate ``MCP Server Should Implement Capabilities`` stays
    per DDD §6 (it accepts a *list* of expected tool/resource/prompt names —
    not a scalar — so the operator algebra does not apply).

    Pass real names rf-mcp is documented to ship; the keyword raises on missing
    and returns None on success.
    """
    handle = kw.connect_to_mcp_server(rf_mcp_server, transport="memory")
    try:
        # `find_keywords` and `manage_session` are documented in the rf-mcp README.
        result = kw.mcp_server_should_implement_capabilities(handle, "find_keywords", "manage_session")
        assert result is None
    finally:
        kw.stop_mcp_server(handle)


# ---- representative tool call (deterministic, no LLM required) -------------


def test_find_keywords_returns_results(kw: MCP, rf_mcp_server: Any) -> None:
    handle = kw.connect_to_mcp_server(rf_mcp_server, transport="memory")
    try:
        # `find_keywords` is a discovery tool — it scans the loaded RF libraries for
        # a fuzzy match. BuiltIn is always loaded so "log" is guaranteed to match.
        result = kw.call_mcp_tool(handle, "find_keywords", {"query": "log"})
        assert result["is_error"] is False, result
        # We don't assert on the exact JSON shape (it changes between rf-mcp versions);
        # we just verify a result came back.
        assert result["data"] is not None or result["structured_content"] is not None
    finally:
        kw.stop_mcp_server(handle)


def test_in_memory_latency_within_budget(kw: MCP, rf_mcp_server: Any) -> None:
    """``Measure MCP Tool Latency`` returns a dict — per DDD §6 this is NOT a
    Should-pair candidate (no scalar return to operator-collapse). The dict-
    field assertion stays in the suite-level Python assertion path."""
    handle = kw.connect_to_mcp_server(rf_mcp_server, transport="memory")
    try:
        # Tool with the smallest payload — `find_keywords` is acceptable.
        stats = kw.measure_mcp_tool_latency(handle, "find_keywords", runs=10, arguments={"query": "x"})
        # rf-mcp does heavier work than the trivial echo fixture so we relax the budget
        # vs the in-memory baseline (5 ms): allow 250 ms p50 for find_keywords.
        assert stats["p50"] < 250, stats
    finally:
        kw.stop_mcp_server(handle)
