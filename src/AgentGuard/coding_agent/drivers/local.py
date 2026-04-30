"""LocalDriver — synthetic ReAct loop over OpenRouter via the litellm provider.

Always-runnable Phase-3 driver: requires only ``OPENROUTER_API_KEY``.
Produces a JSONL session log shaped like Claude Code (per exp_07) so the
canonical session-parser ingests it the same way it ingests a real
``~/.claude/projects/*/<session>.jsonl``.

Crucial property: the tool implementations are **mocked** — we never let the
LLM read, write, or shell out against the real filesystem. The driver exists
to exercise the Phase-3 plumbing end-to-end, not to be an autonomous agent.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from AgentGuard.coding_agent.drivers._jsonl_emit import (
    RunState,
    emit_assistant,
    emit_session_meta,
    emit_tool_result,
    emit_user_prompt,
)
from AgentGuard.coding_agent.drivers.base import DriverConfig, DriverResult
from AgentGuard.coding_agent.drivers.exceptions import DriverUnavailable
from AgentGuard.config import has_openrouter_key
from AgentGuard.providers.factory import build_provider

if TYPE_CHECKING:  # pragma: no cover
    from AgentGuard.providers.base import LLMProviderAdapter

logger = logging.getLogger("AgentGuard.coding_agent.drivers.local")

_DEFAULT_MODEL = "openrouter/openai/gpt-4o-mini"
_SYSTEM_PROMPT = (
    "You are a careful coding assistant operating under AgentGuard test harness. "
    "You may call the tools `read`, `write`, `edit`, `bash`, and `grep`. "
    "Tool calls are sandboxed and return canned responses — DO NOT assume any "
    "side-effects actually occurred. Once you have enough information, reply "
    "with a final natural-language summary and stop calling tools."
)


def _tool(
    name: str,
    description: str,
    props: dict[str, str],
    required: list[str],
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {k: {"type": v} for k, v in props.items()},
                "required": required,
            },
        },
    }


_TOOLS_SCHEMA: list[dict[str, Any]] = [
    _tool("read", "Read a file from the workspace.", {"path": "string"}, ["path"]),
    _tool("write", "Overwrite a file with the supplied text.", {"path": "string", "text": "string"}, ["path", "text"]),
    _tool(
        "edit",
        "Replace `old` with `new` inside `path`.",
        {"path": "string", "old": "string", "new": "string"},
        ["path", "old", "new"],
    ),
    _tool("bash", "Run a shell command.", {"command": "string"}, ["command"]),
    _tool("grep", "Search the workspace for a regex pattern.", {"pattern": "string", "path": "string"}, ["pattern"]),
]


def _mock_tool_result(name: str, args: dict[str, Any]) -> str:
    """Canned tool responses — never touches the real filesystem."""
    if name == "read":
        return f"<mock-read path={args.get('path', '')!r}>file not found</mock-read>"
    if name == "write":
        return f"ok: wrote {len(args.get('text', ''))} bytes to {args.get('path', '')}"
    if name == "edit":
        return f"ok: 0 occurrences of {args.get('old', '')!r} replaced in {args.get('path', '')}"
    if name == "bash":
        return f"<mock-bash>command {args.get('command', '')!r} produced no output</mock-bash>"
    if name == "grep":
        return f"<mock-grep>0 matches for {args.get('pattern', '')!r}</mock-grep>"
    return f"<mock-unknown-tool name={name!r}>"


def _mcp_tools_to_openai_schema(mcp_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Translate MCP tool dicts (from `List MCP Tools`) into OpenAI tool schema."""
    out: list[dict[str, Any]] = []
    for t in mcp_tools:
        name = t.get("name") or t.get("function", {}).get("name")
        if not name:
            continue
        out.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": (t.get("description") or "")[:1024],
                    "parameters": (t.get("inputSchema") or t.get("input_schema") or {"type": "object"}),
                },
            }
        )
    return out


def _coerce_args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        try:
            loaded = json.loads(raw)
            return dict(loaded) if isinstance(loaded, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


class LocalDriver:
    """Synthetic ReAct loop driver — see module docstring."""

    name: str = "local"

    def __init__(self, provider: LLMProviderAdapter | None = None) -> None:
        self._provider = provider

    # ----------------------------- Protocol surface -----------------------

    def is_available(self) -> bool:
        if self._provider is not None:
            return True
        return has_openrouter_key()

    def run(
        self,
        prompt: str,
        config: DriverConfig | None = None,
    ) -> DriverResult:
        cfg = config or DriverConfig()
        if not self.is_available():
            raise DriverUnavailable("LocalDriver requires OPENROUTER_API_KEY (or an injected provider).")

        provider = self._provider or build_provider("litellm", model=cfg.model or _DEFAULT_MODEL)
        model = cfg.model or _DEFAULT_MODEL
        cwd = cfg.resolved_cwd()

        jsonl_path = cfg.resolved_jsonl_path(self.name)
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)

        # ADR-021: when a TrackedMCPSession is attached, swap the mock toolset
        # for the real MCP server's tool schema so the LLM picks tools the
        # server actually exposes; every dispatch goes through the session
        # (auto-recorded as ToolCallRecord).
        mcp_session = getattr(cfg, "mcp_session", None)
        tools_schema: list[dict[str, Any]]
        system_prompt: str
        if mcp_session is not None:
            try:
                mcp_tools = mcp_session.mcp.list_mcp_tools(mcp_session.handle)
            except Exception as exc:  # noqa: BLE001 — fall back loudly
                logger.warning("LocalDriver could not list MCP tools: %s", exc)
                mcp_tools = []
            tools_schema = _mcp_tools_to_openai_schema(mcp_tools)
            tool_names = ", ".join(t["function"]["name"] for t in tools_schema) or "(none)"
            system_prompt = (
                "You are a coding assistant operating under AgentGuard's MCPScenario "
                f"harness. You have access to these MCP tools: {tool_names}. "
                "Each call dispatches to the real MCP server and is recorded for "
                "scenario hit-rate scoring. Reply with a final summary when done."
            )
        else:
            tools_schema = _TOOLS_SCHEMA
            system_prompt = _SYSTEM_PROMPT

        state = RunState(session_id=str(uuid.uuid4()))
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        start = time.perf_counter()
        exit_code = 0
        last_text = ""

        with jsonl_path.open("w", encoding="utf-8") as fp:
            emit_session_meta(fp, state, cwd, model)
            emit_user_prompt(fp, state, cwd, prompt)

            for turn in range(max(1, cfg.max_turns)):
                try:
                    resp = provider.chat(
                        messages=messages,
                        tools=tools_schema,
                        model=model,
                    )
                except Exception as exc:  # noqa: BLE001 — surface as exit_code=1
                    logger.warning("LocalDriver turn %d failed: %s", turn, exc)
                    exit_code = 1
                    break

                state.prompt_tokens += resp.usage.prompt_tokens
                state.completion_tokens += resp.usage.completion_tokens
                state.total_cost += resp.usage.cost_usd

                assistant_uuid = str(uuid.uuid4())
                last_text = resp.text or ""
                emit_assistant(
                    fp,
                    state,
                    cwd,
                    model,
                    assistant_uuid,
                    last_text,
                    resp.tool_calls,
                    resp.usage,
                )
                messages.append(self._assistant_message(last_text, resp.tool_calls))
                state.parent_uuid = assistant_uuid

                if not resp.tool_calls:
                    break

                for tc in resp.tool_calls:
                    self._dispatch_tool_call(fp, state, cwd, tc, messages, mcp_session=mcp_session)

        duration_ms = (time.perf_counter() - start) * 1000.0
        session = _try_parse(jsonl_path) if cfg.capture_jsonl else None
        return DriverResult(
            driver=self.name,
            exit_code=exit_code,
            cwd=str(cwd),
            jsonl_path=str(jsonl_path) if cfg.capture_jsonl else None,
            session=session,
            duration_ms=duration_ms,
            cost_usd=float(state.total_cost) if state.total_cost else 0.0,
            stdout=last_text,
            stderr="",
        )

    # ----------------------------- Helpers --------------------------------

    @staticmethod
    def _assistant_message(
        text: str,
        tool_calls: list[dict[str, Any]],
    ) -> dict[str, Any]:
        msg: dict[str, Any] = {"role": "assistant", "content": text}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        return msg

    @staticmethod
    def _dispatch_tool_call(
        fp: Any,
        state: RunState,
        cwd: Path,
        tc: dict[str, Any],
        messages: list[dict[str, Any]],
        *,
        mcp_session: Any | None = None,
    ) -> None:
        fn = tc.get("function", {}) or {}
        name = fn.get("name", "")
        args = _coerce_args(fn.get("arguments", "{}"))
        if mcp_session is not None:
            # ADR-021: dispatch through the tracked MCP session — auto-records.
            try:
                mcp_result = mcp_session.call_tool(name, args)
                result_text = _mcp_result_to_text(mcp_result)
            except Exception as exc:  # noqa: BLE001 — surface to LLM
                result_text = f"<mcp-error>{type(exc).__name__}: {exc}</mcp-error>"
        else:
            result_text = _mock_tool_result(name, args)
        tool_user_uuid = str(uuid.uuid4())
        emit_tool_result(
            fp,
            state,
            cwd,
            tool_user_uuid,
            tc.get("id", ""),
            name,
            result_text,
        )
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
                "name": name,
                "content": result_text,
            }
        )
        state.parent_uuid = tool_user_uuid


def _mcp_result_to_text(result: dict[str, Any]) -> str:
    """Render an MCP CallResult dict as a string the LLM can read."""
    if not isinstance(result, dict):
        return str(result)
    if result.get("is_error"):
        return f"<error>{result.get('data') or 'tool returned is_error'}</error>"
    data = result.get("data")
    if data is None:
        data = result.get("structured_content")
    if isinstance(data, (dict, list)):
        return json.dumps(data, default=str)[:2000]
    return str(data)[:2000]


def _try_parse(jsonl_path: Path) -> Any | None:
    """Best-effort handoff to the session-parser sibling agent.

    If the parser module hasn't landed yet, return ``None`` instead of raising —
    drivers must still be runnable in isolation.
    """
    try:
        from AgentGuard.coding_agent.session import parser
    except ImportError:
        return None
    try:
        return parser.parse(jsonl_path, format="claude-code")
    except Exception as exc:  # noqa: BLE001 — never propagate parser bugs
        logger.warning("session.parser.parse() failed for %s: %s", jsonl_path, exc)
        return None


__all__ = ["LocalDriver"]
