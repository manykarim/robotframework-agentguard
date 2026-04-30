"""``codex`` CLI driver — wraps OpenAI's Codex CLI (ADR-009).

The 2026 Codex CLI exposes a ``--json`` flag that streams JSONL events to
stdout and writes a per-session log under ``~/.codex/sessions/``. We capture
both: stdout for live tests, and the native session log as a fallback.
"""

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path
from typing import Any

from AgentGuard.coding_agent.drivers._subprocess import cli_present, run_cli
from AgentGuard.coding_agent.drivers.base import DriverConfig, DriverResult
from AgentGuard.coding_agent.drivers.exceptions import (
    DriverInvocationError,
    DriverUnavailable,
)

logger = logging.getLogger("AgentGuard.coding_agent.drivers.codex")

_BINARY = "codex"


class CodexDriver:
    """Subprocess wrapper around the OpenAI Codex CLI."""

    name: str = "codex"

    def is_available(self) -> bool:
        return cli_present(_BINARY)

    def run(
        self,
        prompt: str,
        config: DriverConfig | None = None,
    ) -> DriverResult:
        cfg = config or DriverConfig()
        if not self.is_available():
            raise DriverUnavailable(f"{_BINARY!r} not found on PATH")

        cwd = cfg.resolved_cwd()
        jsonl_path = cfg.resolved_jsonl_path(self.name)
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)

        argv: list[str] = [_BINARY, "--json", "--auto", "--task", prompt]
        if cfg.model:
            argv.extend(["--model", cfg.model])
        argv.extend(cfg.extra_args)

        start = time.perf_counter()
        outcome = run_cli(
            argv,
            cwd=cwd,
            env=cfg.env,
            timeout_seconds=cfg.timeout_seconds,
        )

        if cfg.capture_jsonl and outcome.stdout:
            jsonl_path.write_text(outcome.stdout, encoding="utf-8")

        if cfg.capture_jsonl and not jsonl_path.exists():
            native = _latest_native_session()
            if native is not None:
                shutil.copyfile(native, jsonl_path)

        if outcome.exit_code != 0 and not jsonl_path.exists():
            raise DriverInvocationError(
                f"{_BINARY} exited {outcome.exit_code}",
                exit_code=outcome.exit_code,
                stderr=outcome.stderr,
            )

        session = _try_parse(jsonl_path) if cfg.capture_jsonl else None
        duration_ms = (time.perf_counter() - start) * 1000.0
        return DriverResult(
            driver=self.name,
            exit_code=outcome.exit_code,
            cwd=str(cwd),
            jsonl_path=str(jsonl_path) if cfg.capture_jsonl else None,
            session=session,
            duration_ms=duration_ms,
            cost_usd=None,
            stdout=outcome.stdout,
            stderr=outcome.stderr,
        )


def _latest_native_session() -> Path | None:
    sessions_dir = Path.home() / ".codex" / "sessions"
    if not sessions_dir.exists():
        return None
    files = sorted(sessions_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def _try_parse(jsonl_path: Path) -> Any | None:
    try:
        from AgentGuard.coding_agent.session import parser
    except ImportError:
        return None
    try:
        return parser.parse(jsonl_path, format="codex")
    except Exception as exc:  # noqa: BLE001
        logger.warning("session.parser.parse() failed: %s", exc)
        return None


__all__ = ["CodexDriver"]
