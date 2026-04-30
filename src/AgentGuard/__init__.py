"""AgentGuard — Robot Framework library for testing agentic systems.

Public surface (Phase 1):

    Library    AgentGuard    provider=litellm    model=openrouter/anthropic/claude-sonnet-4-5

Internals are organised by bounded context (see docs/ddd/):
- providers   : LLM access (LiteLLM + vendor adapters)
- mcp         : MCP server testing (transports, tools, resources, prompts)
- skills      : Agent Skill discovery, parsing, grading
- stats       : Mann-Whitney / Cliff's δ / bootstrap / pass@k / TARr@N
- judge       : Classification-based LLM-as-Judge with calibration gating
- tool_calls  : BFCL AST-equality matchers for tool calls and trajectories
- security    : Default-deny skill scanner + redactor + sandbox policy
- telemetry   : OpenTelemetry exporter + Robot Framework listener
"""

from AgentGuard._version import __version__
from AgentGuard.library import AgentGuard

__all__ = ["AgentGuard", "__version__"]
