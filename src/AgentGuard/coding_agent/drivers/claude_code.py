"""``claude`` CLI driver — captures the stream-json transcript (ADR-009).

Invocation (per Anthropic CLI 2026):

    claude --print --output-format stream-json --include-partial-messages \
           --session-id <uuid> -- <prompt-or-empty>

The CLI streams Claude-Code-shaped JSONL records on stdout when
``--output-format stream-json`` is set; we redirect them straight into the
configured ``jsonl_path``. The native session-log under
``~/.claude/projects/<dir>/<session-id>.jsonl`` is left untouched.
"""

from __future__ import annotations

import logging
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from AgentGuard.coding_agent.drivers._subprocess import cli_present, run_cli
from AgentGuard.coding_agent.drivers.base import DriverConfig, DriverResult
from AgentGuard.coding_agent.drivers.exceptions import (
    DriverInvocationError,
    DriverUnavailable,
)

logger = logging.getLogger("AgentGuard.coding_agent.drivers.claude_code")

_BINARY = "claude"


class ClaudeCodeDriver:
    """Subprocess wrapper around the official ``claude`` CLI."""

    name: str = "claude-code"

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

        session_id = str(uuid.uuid4())
        argv: list[str] = [
            _BINARY,
            "--print",
            "--output-format",
            "stream-json",
            "--include-partial-messages",
            "--session-id",
            session_id,
        ]
        if cfg.model:
            argv.extend(["--model", cfg.model])
        argv.extend(cfg.extra_args)

        start = time.perf_counter()
        outcome = run_cli(
            argv,
            cwd=cwd,
            env=cfg.env,
            timeout_seconds=cfg.timeout_seconds,
            stdin_text=prompt,
        )

        # The CLI streams JSONL on stdout when --output-format is stream-json.
        if cfg.capture_jsonl and outcome.stdout:
            jsonl_path.write_text(outcome.stdout, encoding="utf-8")

        # Belt-and-braces: if no stdout was captured, hunt the per-project log.
        if cfg.capture_jsonl and not jsonl_path.exists():
            native = _find_native_session(cwd, session_id)
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


def _find_native_session(cwd: Path, session_id: str) -> Path | None:
    home = Path.home()
    project_root = home / ".claude" / "projects"
    if not project_root.exists():
        return None
    candidate = project_root / _slug(cwd) / f"{session_id}.jsonl"
    if candidate.exists():
        return candidate
    for hit in project_root.rglob(f"{session_id}.jsonl"):
        return hit
    return None


def _slug(path: Path) -> str:
    return "-" + str(path).replace("/", "-").lstrip("-")


def _try_parse(jsonl_path: Path) -> Any | None:
    try:
        from AgentGuard.coding_agent.session import parser
    except ImportError:
        return None
    try:
        return parser.parse(jsonl_path, format="claude-code")
    except Exception as exc:  # noqa: BLE001
        logger.warning("session.parser.parse() failed: %s", exc)
        return None


__all__ = ["ClaudeCodeDriver"]
