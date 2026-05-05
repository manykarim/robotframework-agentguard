"""Shared pytest fixtures for the AgentGuard test suite.

Default-offline contract:
- Every unit + integration test must pass without `OPENROUTER_API_KEY`.
- Live tests carry `@pytest.mark.live` and are skipped via `live_or_skip`.
- Mock provider returns scripted `ChatResponse` objects from a queue.
- `echo_mcp_server` builds an in-memory FastMCP echo server for transports tests.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable, Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Disable the mcp_eval plugin — it pulls in `anthropic` (not in our deps).

    `pytest-mcp 0.1.0` registers an entry-point that imports `mcp_agent`,
    which in turn imports `anthropic`. We don't ship `anthropic` (LiteLLM is the
    provider abstraction per ADR-001), so the plugin's collection-time import
    fails. Skipping the plugin keeps default-offline `pytest` runs green.

    Also registers Phase-2 markers that aren't yet in pyproject.toml (foundation
    will land them centrally — until then, conftest keeps `--strict-markers`
    happy).
    """
    # Best-effort: only registers if the plugin happens to be loaded.
    try:
        config.pluginmanager.set_blocked("mcp_eval")
    except Exception:  # noqa: BLE001
        pass
    # Phase-2 markers (foundation may centralise these in pyproject.toml later).
    config.addinivalue_line(
        "markers",
        "docker: requires Docker daemon (skipped in CI without it)",
    )


from AgentGuard.providers.base import ChatResponse, Usage
from AgentGuard.providers.mock import MockProvider
from AgentGuard.telemetry.otel_listener import OTelListener

FIXTURES = Path(__file__).parent / "fixtures"


# --------------------------- environment -----------------------------------


@pytest.fixture
def tmp_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Provide a temp dir with a `.env` file containing a fake OpenRouter key.

    Tests that exercise `config.load_env` should chdir into this directory or
    pass the `.env` path explicitly. The fake value is `test`; never use it for
    a real network call.
    """
    env_file = tmp_path / ".env"
    env_file.write_text("OPENROUTER_API_KEY=test\nAGENTGUARD_DEFAULT_MODEL=mock/model\n")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("AGENTGUARD_DEFAULT_MODEL", raising=False)
    monkeypatch.chdir(tmp_path)
    yield tmp_path


# --------------------------- providers -------------------------------------


def _resp(text: str = "ok", tool_calls: list[dict[str, Any]] | None = None) -> ChatResponse:
    return ChatResponse(
        text=text,
        tool_calls=tool_calls or [],
        usage=Usage(prompt_tokens=10, completion_tokens=20, cost_usd=Decimal("0.0001")),
    )


@pytest.fixture
def mock_provider() -> MockProvider:
    """Return a fresh `MockProvider` with a small queue of canned responses."""
    return MockProvider(
        responses=[
            _resp(text="hello"),
            _resp(
                text="world",
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "echo", "arguments": '{"text": "hi"}'},
                    }
                ],
            ),
        ]
    )


@pytest.fixture
def chat_response_factory() -> Callable[..., ChatResponse]:
    """Factory for ad-hoc ChatResponse objects in tests."""
    return _resp


# --------------------------- MCP -------------------------------------------


@pytest.fixture
def echo_mcp_server() -> Any:
    """Yield the canonical in-memory FastMCP echo server (echo, add, slow_op).

    Uses `tests/fixtures/mcp/echo_server.py:build_server` so behaviour stays
    in sync between unit, integration, and acceptance tests.
    """
    pytest.importorskip("fastmcp")
    from tests.fixtures.mcp import echo_server  # local fixture module

    return echo_server.build_server()


# --------------------------- skills ----------------------------------------


def _write_skill(path: Path, frontmatter: dict[str, Any], body: str = "Body.") -> Path:
    yaml = pytest.importorskip("yaml")
    path.mkdir(parents=True, exist_ok=True)
    (path / "SKILL.md").write_text("---\n" + yaml.safe_dump(frontmatter) + "---\n" + body + "\n")
    return path


@pytest.fixture
def sample_skill(tmp_path: Path) -> Path:
    """A valid skill with full frontmatter."""
    return _write_skill(
        tmp_path / "good-skill",
        {
            "name": "good-skill",
            "description": "A well-formed sample skill used by tests.",
            "allowed-tools": ["Read", "Write"],
        },
        body="When asked, respond with 'OK'.",
    )


@pytest.fixture
def bad_skill(tmp_path: Path) -> Path:
    """A skill missing the required `description` field."""
    return _write_skill(
        tmp_path / "bad-skill",
        {"name": "bad-skill"},
        body="Missing description.",
    )


# --------------------------- security --------------------------------------


@pytest.fixture
def mock_aidefence(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Patch `AgentGuard.security.aidefence.scan` to return a fixed result.

    The yielded dict captures the last invocation so tests can assert on calls.
    """
    captured: dict[str, Any] = {"calls": []}

    def fake_scan(content: str, **kwargs: Any) -> dict[str, Any]:
        captured["calls"].append({"content": content, "kwargs": kwargs})
        return {
            "safe": True,
            "score": 0.0,
            "findings": [],
            "source": "mock_aidefence",
        }

    try:
        from AgentGuard.security import aidefence  # type: ignore[attr-defined]

        monkeypatch.setattr(aidefence, "scan", fake_scan, raising=False)
    except ImportError:
        # Module not yet implemented; tests using this fixture should skip.
        pass
    return captured


# --------------------------- telemetry -------------------------------------


@pytest.fixture
def reset_otel_provider() -> Iterator[None]:
    """Reset the OTel singleton — opt-in only; resetting between tests breaks
    OTel's own global TracerProvider lock so tests should request explicitly.
    """
    OTelListener.reset_for_tests()
    yield
    OTelListener.reset_for_tests()


# --------------------------- live test gating ------------------------------


def live_or_skip() -> None:
    """Skip if `OPENROUTER_API_KEY` is missing — call from `@pytest.mark.live`."""
    if not os.getenv("OPENROUTER_API_KEY"):
        pytest.skip("live test requires OPENROUTER_API_KEY")


@pytest.fixture
def require_live() -> None:
    live_or_skip()


# --------------------------- helpers ---------------------------------------


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return path


# --------------------------- Phase 3 — coding_agent ------------------------


def _parse_iso(value: str | None) -> Any:
    """Tolerant ISO-8601 parser used by the JSON->Session loader."""
    if not value:
        return None
    from datetime import datetime

    cleaned = value.rstrip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def load_session_json(path: Path) -> Any:
    """Hydrate a JSON-shaped fixture into a real ``Session`` dataclass.

    The fixtures under ``tests/fixtures/coding_agent/metrics/`` are stored as
    JSON dicts (not pickle/JSONL) so that they can be diffed in code review.
    Each fixture mirrors the canonical :class:`Session` shape; this loader is
    the inverse of ``dataclasses.asdict``.
    """
    try:
        from AgentGuard.coding_agent.session.types import (
            HookEvent,
            Interrupt,
            Message,
            Session,
            ToolCall,
            ToolResponse,
            Usage,
        )
    except ImportError:  # pragma: no cover — Phase 3 race
        pytest.skip("phase3: session.types not yet implemented", allow_module_level=False)

    data = json.loads(Path(path).read_text(encoding="utf-8"))

    msgs = [Message(role=m["role"], content=m["content"], tool_calls=[]) for m in data.get("messages", [])]
    tcs = [
        ToolCall(
            id=t["id"],
            name=t["name"],
            arguments=t.get("arguments", {}),
            timestamp=_parse_iso(t.get("timestamp")),
        )
        for t in data.get("tool_calls", [])
    ]
    trs = [
        ToolResponse(
            tool_call_id=t["tool_call_id"],
            content=t.get("content"),
            is_error=t.get("is_error", False),
            timestamp=_parse_iso(t.get("timestamp")),
        )
        for t in data.get("tool_responses", [])
    ]
    interrupts = [
        Interrupt(timestamp=_parse_iso(i.get("timestamp")), reason=i.get("reason")) for i in data.get("interrupts", [])
    ]
    hes = [
        HookEvent(
            event=h["event"],
            decision=h.get("decision"),
            timestamp=_parse_iso(h.get("timestamp")),
        )
        for h in data.get("hook_events", [])
    ]
    u_raw = data.get("usage") or {}
    usage = Usage(
        prompt_tokens=int(u_raw.get("prompt_tokens", 0)),
        completion_tokens=int(u_raw.get("completion_tokens", 0)),
        cache_read_tokens=int(u_raw.get("cache_read_tokens", 0)),
        cache_write_tokens=int(u_raw.get("cache_write_tokens", 0)),
        cost_usd=u_raw.get("cost_usd"),
    )
    return Session(
        id=data.get("id", "unknown"),
        source=data.get("source", "unknown"),
        messages=msgs,
        tool_calls=tcs,
        tool_responses=trs,
        interrupts=interrupts,
        hook_events=hes,
        usage=usage,
        cwd=data.get("cwd"),
        git_branch=data.get("git_branch"),
        started_at=_parse_iso(data.get("started_at")),
        ended_at=_parse_iso(data.get("ended_at")),
        raw_path=data.get("raw_path"),
        metadata=data.get("metadata", {}),
    )


@pytest.fixture
def healthy_session() -> Any:
    """Hydrate the healthy fixture into a Session dataclass."""
    return load_session_json(FIXTURES / "coding_agent" / "metrics" / "sample_session.json")


@pytest.fixture
def degraded_session() -> Any:
    """Hydrate the degraded fixture into a Session dataclass."""
    return load_session_json(FIXTURES / "coding_agent" / "metrics" / "degraded_session.json")


# Make src/ importable when tests are run from the repo root without install.
_SRC = Path(__file__).parent.parent / "src"
if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
