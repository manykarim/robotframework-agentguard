"""Live end-to-end — real OpenRouter LLM driving the rf-mcp Robot Framework MCP server.

Runs only when ``OPENROUTER_API_KEY`` is set (``@pytest.mark.live``). Validates
that AgentGuard's ``Generate Tool Call`` keyword can produce a structurally
correct call against an rf-mcp tool definition via a real model — the full
stack tested in one shot:

    OpenRouter LLM  →  AgentGuard provider (LiteLLM)
                    →  AgentGuard ``Generate Tool Call`` (BFCL AST matcher)
                    →  validates the structurally-correct rf-mcp tool call.

Cost ceiling per run: <$0.005 (gpt-4o-mini, N=1, ≤500 output tokens).
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

import pytest

# Skip when rf-mcp is unreachable.
_LOCAL_CLONE = Path.home() / "workspace" / "rf-mcp" / "src"
if importlib.util.find_spec("robotmcp") is None and _LOCAL_CLONE.exists():
    sys.path.insert(0, str(_LOCAL_CLONE))

if importlib.util.find_spec("robotmcp") is None:
    pytest.skip(
        "rf-mcp not installed; install via `pip install rf-mcp`.",
        allow_module_level=True,
    )

from AgentGuard.config import load_env
from AgentGuard.mcp.library import MCPKeywords
from AgentGuard.providers.factory import build_provider
from AgentGuard.tool_calls.library import ToolCallKeywords

# Load .env before the OPENROUTER_API_KEY skip-check so local runs work the same
# way as CI (where the secret is injected via the workflow's env block).
load_env()

if not os.getenv("OPENROUTER_API_KEY"):
    pytest.skip("OPENROUTER_API_KEY not set", allow_module_level=True)


@pytest.fixture(scope="module")
def rf_mcp_server() -> Any:
    server_mod = importlib.import_module("robotmcp.server")
    return server_mod.mcp


@pytest.fixture
def mcp_kw() -> MCPKeywords:
    return MCPKeywords()


@pytest.mark.live
def test_real_llm_generates_call_against_rf_mcp_tool_schema(rf_mcp_server: Any, mcp_kw: MCPKeywords) -> None:
    """End-to-end: real OpenRouter LLM, real rf-mcp tool schema, BFCL matcher.

    1. Pull the live ``find_keywords`` tool schema from rf-mcp.
    2. Ask gpt-4o-mini to call ``find_keywords`` with a deterministic prompt.
    3. Assert the returned tool call name matches and arguments parse as JSON.
    """
    handle = mcp_kw.connect_to_mcp_server(rf_mcp_server, transport="memory")
    try:
        tools = mcp_kw.list_mcp_tools(handle)
        find_kw_tool = next((t for t in tools if t["name"] == "find_keywords"), None)
        assert find_kw_tool is not None, "rf-mcp must expose 'find_keywords'"
    finally:
        mcp_kw.stop_mcp_server(handle)

    provider = build_provider("litellm", "openrouter/openai/gpt-4o-mini")
    tool_def = {
        "type": "function",
        "function": {
            "name": find_kw_tool["name"],
            "description": find_kw_tool.get("description") or "Find Robot Framework keywords",
            "parameters": find_kw_tool.get("inputSchema") or {"type": "object"},
        },
    }
    tc_kw = ToolCallKeywords(provider=provider, default_model="openrouter/openai/gpt-4o-mini")
    calls = tc_kw.generate_tool_call(
        prompt="Use the find_keywords tool to look up Robot Framework keywords matching the term 'log'.",
        tools=[tool_def],
    )
    assert calls, "LLM did not produce any tool calls"
    tc_kw.tool_call_should_match_name(calls[0], "find_keywords")
    # arguments must be a dict (not a JSON string we forgot to parse)
    assert isinstance(calls[0].arguments, dict)


@pytest.mark.live
def test_real_llm_describes_rf_mcp_capabilities(rf_mcp_server: Any, mcp_kw: MCPKeywords) -> None:
    """Sanity check: the model can summarise rf-mcp's tool list given names + descriptions.

    No tool-call required; this just exercises the LLM round-trip with the API key
    and verifies our provider abstraction works end-to-end.
    """
    handle = mcp_kw.connect_to_mcp_server(rf_mcp_server, transport="memory")
    try:
        tools = mcp_kw.list_mcp_tools(handle)
    finally:
        mcp_kw.stop_mcp_server(handle)

    catalogue = "\n".join(f"- {t['name']}: {t.get('description') or ''}"[:200] for t in tools[:10])
    provider = build_provider("litellm", "openrouter/openai/gpt-4o-mini")
    response = provider.chat(
        messages=[
            {
                "role": "system",
                "content": "Reply in a single sentence. No markdown, no bullet points.",
            },
            {
                "role": "user",
                "content": f"Summarise what these MCP tools do collectively:\n{catalogue}",
            },
        ],
        model="openrouter/openai/gpt-4o-mini",
        max_tokens=80,
    )
    assert response.text and len(response.text) > 10, response
