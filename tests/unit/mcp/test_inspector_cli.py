"""Tests for `AgentGuard.mcp.inspector_cli` — wraps `npx @modelcontextprotocol/inspector --cli`.

Default-offline: subprocess.run is monkeypatched. Live invocation is gated
behind `@pytest.mark.live` and `npx` availability.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

import pytest

from AgentGuard.mcp.exceptions import MCPInspectorError
from AgentGuard.mcp import inspector_cli


class TestNpxAvailable:
    def test_returns_bool(self) -> None:
        inspector_cli.reset_npx_cache()
        assert isinstance(inspector_cli.npx_available(), bool)

    def test_cached_after_first_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        inspector_cli.reset_npx_cache()
        calls = {"n": 0}

        def fake_which(_name: str) -> str | None:
            calls["n"] += 1
            return "/usr/bin/npx"

        monkeypatch.setattr(shutil, "which", fake_which)
        inspector_cli.npx_available()
        inspector_cli.npx_available()
        assert calls["n"] == 1

    def test_reset_cache_re_probes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        inspector_cli.reset_npx_cache()
        called = {"n": 0}

        def fake_which(_n: str) -> str | None:
            called["n"] += 1
            return "/x"

        monkeypatch.setattr(shutil, "which", fake_which)
        inspector_cli.npx_available()
        inspector_cli.reset_npx_cache()
        inspector_cli.npx_available()
        assert called["n"] == 2


class TestRun:
    def test_zero_exit_returns_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        inspector_cli.reset_npx_cache()
        monkeypatch.setattr(shutil, "which", lambda _n: "/usr/bin/npx")

        class _Proc:
            returncode = 0
            stdout = '{"tools": [{"name": "x"}]}'
            stderr = ""

        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _Proc())
        result = inspector_cli.run(["--method", "tools/list", "--", "uv", "run", "mcp"])
        assert result.ok
        assert result.parsed == {"tools": [{"name": "x"}]}

    def test_non_zero_exit_not_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        inspector_cli.reset_npx_cache()
        monkeypatch.setattr(shutil, "which", lambda _n: "/usr/bin/npx")

        class _Proc:
            returncode = 1
            stdout = "invalid"
            stderr = "boom"

        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _Proc())
        result = inspector_cli.run(["--method", "tools/list"])
        assert not result.ok
        assert result.parsed is None

    def test_text_stdout_no_parse(self, monkeypatch: pytest.MonkeyPatch) -> None:
        inspector_cli.reset_npx_cache()
        monkeypatch.setattr(shutil, "which", lambda _n: "/usr/bin/npx")

        class _Proc:
            returncode = 0
            stdout = "plain text not json"
            stderr = ""

        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _Proc())
        result = inspector_cli.run(["--method", "tools/list"])
        assert result.parsed is None

    def test_missing_npx_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        inspector_cli.reset_npx_cache()
        monkeypatch.setattr(shutil, "which", lambda _n: None)
        with pytest.raises(MCPInspectorError, match="npx"):
            inspector_cli.run(["--method", "tools/list"])

    def test_timeout_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        inspector_cli.reset_npx_cache()
        monkeypatch.setattr(shutil, "which", lambda _n: "/usr/bin/npx")

        def boom(*_a: Any, **_kw: Any) -> None:
            raise subprocess.TimeoutExpired(cmd="x", timeout=1)

        monkeypatch.setattr(subprocess, "run", boom)
        with pytest.raises(MCPInspectorError, match="timed out"):
            inspector_cli.run(["--method", "tools/list"], timeout=1)


class TestBuildTargetArgs:
    def test_stdio_returns_separator(self) -> None:
        args = inspector_cli.build_target_args("uv run mcp", transport="stdio")
        assert "--transport" in args and "stdio" in args
        assert "--" in args

    def test_http_returns_server_url(self) -> None:
        args = inspector_cli.build_target_args(
            "http://x/mcp", transport="http", headers={"Auth": "Bearer xxx"}
        )
        assert "--transport" in args and "http" in args
        assert "--server-url" in args
        assert any("Auth: Bearer" in a for a in args)

    def test_unknown_transport_raises(self) -> None:
        with pytest.raises(MCPInspectorError):
            inspector_cli.build_target_args("x", transport="carrier-pigeon")


@pytest.mark.live
@pytest.mark.skipif(shutil.which("npx") is None, reason="npx not on PATH")
def test_inspector_help_live() -> None:
    result = inspector_cli.run(["--help"], timeout=120)
    # `--help` may exit 0 or 1 depending on inspector version, but stdout should mention --cli.
    assert "--cli" in result.stdout or "--method" in result.stdout
