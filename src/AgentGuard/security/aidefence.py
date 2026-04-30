"""AIDefence MCP client + local conservative regex fallback.

Per ``docs/research/experiments/REPORT.md`` exp_10 — AIDefence is reached
as MCP tools (``aidefence_scan``, ``aidefence_has_pii``, ``aidefence_is_safe``)
on the claude-flow MCP server already declared in the project's ``.mcp.json``.

The MCP connection is opened lazily on first use, cached per process and
reused across keyword calls (lifecycle = SUITE). When the server is not
reachable (no ``npx``, no network, sandbox without subprocess access) every
call falls back to a built-in regex detector so unit tests still pass.
``AIDefenceResult.source == "local_fallback"`` flags the degraded mode.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import threading
from typing import Any, cast

from AgentGuard.security.types import AIDefenceResult, PIIResult

logger = logging.getLogger("AgentGuard.security.aidefence")

_MCP_CMD_ENV = "AGENTGUARD_AIDEFENCE_MCP_CMD"
_MCP_DISABLE_ENV = "AGENTGUARD_AIDEFENCE_DISABLE"
_DEFAULT_CMD = ("npx", "-y", "ruflo@latest", "mcp", "start")


# ---------------------------------------------------------------------------
# Local conservative fallback (always present, no deps)
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str], float], ...] = (
    (
        "ignore_previous",
        re.compile(r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions|rules|prompt)", re.I),
        0.9,
    ),
    ("you_are_now", re.compile(r"\byou\s+are\s+now\s+", re.I), 0.7),
    ("system_override", re.compile(r"\bsystem\s*[:>]\s*", re.I), 0.6),
    ("disregard", re.compile(r"\bdisregard\s+(the\s+)?(above|previous|prior)", re.I), 0.85),
    ("jailbreak", re.compile(r"\b(developer\s+mode|DAN\s+mode|jailbreak)\b", re.I), 0.8),
    ("exfiltrate", re.compile(r"(curl|wget|fetch|POST)\s+[^\s]*(http|file|ftp)://", re.I), 0.5),
)

_PII_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("email", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    ("ssn", re.compile(r"\b(?!000|666)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")),
    ("credit_card", re.compile(r"\b(?:\d[ \-]?){13,19}\b")),
    ("phone", re.compile(r"(?<!\d)(?:\+?\d{1,3}[ \-.]?)?\(?\d{3}\)?[ \-.]?\d{3}[ \-.]?\d{4}(?!\d)")),
)


def _local_scan(text: str) -> AIDefenceResult:
    score = 0.0
    findings: list[str] = []
    for name, pat, weight in _INJECTION_PATTERNS:
        if pat.search(text):
            findings.append(name)
            score = max(score, weight)
    return AIDefenceResult(
        injection_score=score, findings=tuple(findings), source="local_fallback"
    )


def _local_has_pii(text: str) -> PIIResult:
    types: list[str] = []
    for name, pat in _PII_PATTERNS:
        if pat.search(text):
            types.append(name)
    return PIIResult(detected=bool(types), types=tuple(types), source="local_fallback")


# ---------------------------------------------------------------------------
# MCP transport (lazy, cached, thread-safe)
# ---------------------------------------------------------------------------


class _MCPSession:
    """Cached wrapper that owns a single FastMCP client + its event loop.

    The MCP client is async-only; Robot keywords are synchronous.  We keep
    a dedicated thread + event loop so every sync ``call_tool`` reuses the
    same connection rather than re-spawning ``npx`` per keyword call.
    """

    _lock = threading.Lock()
    _instance: _MCPSession | None = None

    @classmethod
    def get(cls) -> _MCPSession | None:
        if os.getenv(_MCP_DISABLE_ENV, "").strip().lower() in {"1", "true", "yes"}:
            return None
        with cls._lock:
            if cls._instance is None:
                inst = cls._try_build()
                if inst is None:
                    return None
                cls._instance = inst
            return cls._instance

    @classmethod
    def _try_build(cls) -> _MCPSession | None:
        cmd_env = os.getenv(_MCP_CMD_ENV, "").strip()
        cmd = tuple(cmd_env.split()) if cmd_env else _DEFAULT_CMD
        executable = cmd[0]
        if shutil.which(executable) is None:
            logger.info(
                "AIDefence MCP launcher %r not on PATH — using local fallback.", executable
            )
            return None
        try:
            from fastmcp import Client  # noqa: F401  (presence check only)
            from fastmcp.client.transports import StdioTransport  # noqa: F401
        except ImportError:
            logger.info("fastmcp not installed — AIDefence falling back to local detector.")
            return None
        try:
            return cls(cmd)
        except Exception as exc:  # noqa: BLE001
            logger.warning("AIDefence MCP session bootstrap failed: %s", exc)
            return None

    def __init__(self, cmd: tuple[str, ...]) -> None:
        self._cmd = cmd
        self._loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self._client_cm: Any = None
        self._client: Any = None
        try:
            self._connect()
        except Exception:
            self.close()
            raise

    def _connect(self) -> None:
        from fastmcp import Client
        from fastmcp.client.transports import StdioTransport

        async def _open() -> tuple[Any, Any]:
            transport = StdioTransport(command=self._cmd[0], args=list(self._cmd[1:]))
            client = Client(transport)
            cm = client.__aenter__()
            entered = await cm
            return client, entered

        fut = asyncio.run_coroutine_threadsafe(_open(), self._loop)
        self._client, _ = fut.result(timeout=20)

    def call(self, tool_name: str, params: dict[str, Any], timeout: float = 15.0) -> dict[str, Any]:
        async def _do() -> dict[str, Any]:
            result = await self._client.call_tool(tool_name, params)
            data = getattr(result, "data", None)
            if data is None:
                content = getattr(result, "content", None)
                if content:
                    text = getattr(content[0], "text", None)
                    if text:
                        import json

                        try:
                            return cast(dict[str, Any], json.loads(text))
                        except (ValueError, TypeError):
                            return {"raw": text}
                return {}
            if isinstance(data, dict):
                return cast(dict[str, Any], data)
            return {"value": data}

        fut = asyncio.run_coroutine_threadsafe(_do(), self._loop)
        return fut.result(timeout=timeout)

    def close(self) -> None:
        if self._client is not None:
            async def _close() -> None:
                try:
                    await self._client.__aexit__(None, None, None)
                except Exception:  # noqa: BLE001
                    pass

            try:
                fut = asyncio.run_coroutine_threadsafe(_close(), self._loop)
                fut.result(timeout=5)
            except Exception:  # noqa: BLE001
                pass
            self._client = None
        try:
            self._loop.call_soon_threadsafe(self._loop.stop)
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# Public surface — the only symbols other modules import
# ---------------------------------------------------------------------------


def is_mcp_reachable() -> bool:
    """Probe whether the AIDefence MCP server can be opened on this host."""
    return _MCPSession.get() is not None


def scan(text: str) -> AIDefenceResult:
    """Run AIDefence prompt-injection scan on ``text``."""
    if not text:
        return AIDefenceResult(injection_score=0.0, findings=(), source="local_fallback")
    session = _MCPSession.get()
    if session is None:
        return _local_scan(text)
    try:
        raw = session.call("aidefence_scan", {"text": text})
    except Exception as exc:  # noqa: BLE001
        logger.warning("aidefence_scan MCP call failed (%s); using local fallback.", exc)
        return _local_scan(text)
    score = _coerce_score(raw)
    findings = _coerce_findings(raw)
    return AIDefenceResult(
        injection_score=score, findings=findings, source="mcp", raw=raw
    )


def has_pii(text: str) -> PIIResult:
    """Run AIDefence PII detector on ``text``."""
    if not text:
        return PIIResult(detected=False, types=(), source="local_fallback")
    session = _MCPSession.get()
    if session is None:
        return _local_has_pii(text)
    try:
        raw = session.call("aidefence_has_pii", {"text": text})
    except Exception as exc:  # noqa: BLE001
        logger.warning("aidefence_has_pii MCP call failed (%s); using local fallback.", exc)
        return _local_has_pii(text)
    detected = bool(raw.get("detected") or raw.get("has_pii") or raw.get("value"))
    raw_types = raw.get("types") or raw.get("pii_types") or []
    if isinstance(raw_types, list):
        types = tuple(str(t) for t in raw_types)
    else:
        types = (str(raw_types),)
    return PIIResult(detected=detected, types=types, source="mcp", raw=raw)


def is_safe(text: str, threshold: float = 0.5) -> bool:
    """Convenience predicate — ``True`` when no high-confidence injection found."""
    if not text:
        return True
    session = _MCPSession.get()
    if session is None:
        return _local_scan(text).injection_score < threshold
    try:
        raw = session.call("aidefence_is_safe", {"text": text})
    except Exception as exc:  # noqa: BLE001
        logger.warning("aidefence_is_safe MCP call failed (%s); using local fallback.", exc)
        return _local_scan(text).injection_score < threshold
    if "safe" in raw:
        return bool(raw["safe"])
    if "value" in raw:
        return bool(raw["value"])
    return scan(text).injection_score < threshold


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _coerce_score(raw: dict[str, Any]) -> float:
    for key in ("injection_score", "score", "confidence", "value"):
        if key in raw:
            try:
                return float(cast(Any, raw[key]))
            except (TypeError, ValueError):
                continue
    if raw.get("flagged") or raw.get("unsafe"):
        return 0.9
    return 0.0


def _coerce_findings(raw: dict[str, Any]) -> tuple[str, ...]:
    for key in ("findings", "matches", "labels", "categories"):
        value = raw.get(key)
        if isinstance(value, list):
            return tuple(str(v) for v in value)
    return ()
