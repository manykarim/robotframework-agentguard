"""Integration tests for the Hooks bounded context: full envelope → handler → decision flow.

Exercises the Robot keyword surface (via ``HooksKeywords``) end-to-end
against subprocess fixture scripts and an in-process HTTP server, mirroring
the canonical research §6.3 scenarios.
"""

from __future__ import annotations

import json
import socket
import stat
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest

from AgentGuard.hooks.exceptions import HookLoopDetected
from AgentGuard.hooks.library import HooksKeywords


def _make_script(path: Path, body: str) -> Path:
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


@pytest.fixture
def kw() -> HooksKeywords:
    return HooksKeywords()


# ---------------- Scenario 1: PreToolUse blocks rm -rf ----------------


def test_pretooluse_blocks_destructive_bash(kw: HooksKeywords, tmp_path: Path) -> None:
    """Mirrors research §6.3 ``PreToolUse Hook Blocks Destructive Bash``."""
    script = _make_script(
        tmp_path / "security-check.sh",
        """#!/usr/bin/env bash
read input
if echo "$input" | grep -q 'rm -rf'; then
    echo 'destructive command detected' >&2
    exit 2
fi
echo '{"decision": "allow"}'
""",
    )
    env = kw.synthesize_hook_input(
        "PreToolUse",
        tool_name="Bash",
        tool_input={"command": "rm -rf /"},
    )
    result = kw.run_hook_command(script, env)
    kw.hook_should_block(result)
    assert "destructive" in result.stderr


# ---------------- Scenario 2: Stop forces tests ----------------


def test_stop_hook_forces_test_pass_before_stopping(kw: HooksKeywords, tmp_path: Path) -> None:
    """Mirrors research §6.3 ``Stop Hook Forces Test Pass``."""
    script = _make_script(
        tmp_path / "require-tests.sh",
        """#!/usr/bin/env bash
read input
echo '{"decision": "block", "reason": "Test suite must pass before stopping"}'
exit 0
""",
    )
    env = kw.synthesize_hook_input("Stop", stop_hook_active=False)
    result = kw.run_hook_command(script, env)
    kw.hook_decision_should_be(result, "block")
    assert "Test suite must pass" in result.reason


# ---------------- Scenario 3: HTTP injects context ----------------


class _InjectingHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        body = json.dumps(
            {
                "decision": "allow",
                "additional_context": "read-only system path detected",
            }
        ).encode()
        self.wfile.write(body)

    def log_message(self, *args: Any, **kwargs: Any) -> None:  # silence
        pass


@pytest.fixture
def http_inject_server() -> Iterator[str]:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = HTTPServer(("127.0.0.1", port), _InjectingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/hooks/pre-tool-use"
    finally:
        server.shutdown()
        server.server_close()


def test_http_hook_injects_context(kw: HooksKeywords, http_inject_server: str) -> None:
    """Mirrors research §6.3 ``HTTP Hook Returns Permission Decision``."""
    env = kw.synthesize_hook_input(
        "PreToolUse",
        tool_name="Edit",
        tool_input={"file_path": "/etc/passwd", "new_string": "..."},
    )
    result = kw.run_hook_http(http_inject_server, env)
    kw.hook_should_inject_context(result, "read-only")


# ---------------- Loop detection (composite) ----------------


def test_stop_hook_loop_detected(kw: HooksKeywords, tmp_path: Path) -> None:
    """5 consecutive blocks while stop_hook_active=True ⇒ HookLoopDetected."""
    script = _make_script(tmp_path / "loop.sh", "#!/usr/bin/env bash\nexit 2\n")
    env = kw.synthesize_hook_input("Stop", stop_hook_active=True)
    results = [kw.run_hook_command(script, env) for _ in range(5)]
    with pytest.raises(HookLoopDetected):
        kw.detect_stop_hook_loop(results, window=5)


# ---------------- Agent + prompt integration ----------------


def test_agent_hook_with_modify_tool_input(kw: HooksKeywords) -> None:
    def modify_agent(envelope: dict[str, Any]) -> dict[str, Any]:
        return {
            "decision": "allow",
            "modified_tool_input": {"command": "ls -la"},
        }

    env = kw.synthesize_hook_input("PreToolUse", tool_name="Bash", tool_input={"command": "ls"})
    result = kw.run_hook_agent(modify_agent, env)
    kw.hook_should_modify_tool_input_to(result, {"command": "ls -la"})


def test_prompt_hook_with_mock_provider(mock_provider: Any) -> None:
    """``Run Hook Prompt`` works with the deterministic MockProvider fixture."""
    from decimal import Decimal

    from AgentGuard.providers.base import ChatResponse, Usage
    from AgentGuard.providers.mock import MockProvider

    provider = MockProvider(
        responses=[
            ChatResponse(
                text='{"decision": "block", "reason": "policy violation"}',
                usage=Usage(prompt_tokens=1, completion_tokens=1, cost_usd=Decimal("0")),
            )
        ]
    )
    kw = HooksKeywords(provider=provider, default_model="mock/m")
    env = kw.synthesize_hook_input("PreToolUse", tool_name="Bash")
    result = kw.run_hook_prompt("Decide.", env)
    kw.hook_should_block(result)
