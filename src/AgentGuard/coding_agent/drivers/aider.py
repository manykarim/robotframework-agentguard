"""``aider`` CLI driver (ADR-009).

Aider writes a markdown chat history to ``.aider.chat.history.md`` in the
working directory; we copy that into the configured ``jsonl_path`` (the
parser knows how to consume the markdown form). ``--no-auto-commits`` and
``--yes`` keep the run non-interactive and side-effect-free at the git layer.
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

logger = logging.getLogger("AgentGuard.coding_agent.drivers.aider")

_BINARY = "aider"
_CHAT_HISTORY = ".aider.chat.history.md"


class AiderDriver:
    """Subprocess wrapper around the ``aider`` CLI."""

    name: str = "aider"

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

        argv: list[str] = [
            _BINARY,
            "--no-auto-commits",
            "--yes",
            "--message",
            prompt,
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
        )

        if cfg.capture_jsonl:
            history = cwd / _CHAT_HISTORY
            if history.exists():
                shutil.copyfile(history, jsonl_path)
            elif outcome.stdout:
                jsonl_path.write_text(outcome.stdout, encoding="utf-8")

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


def _try_parse(jsonl_path: Path) -> Any | None:
    try:
        from AgentGuard.coding_agent.session import parser
    except ImportError:
        return None
    try:
        return parser.parse(jsonl_path, format="aider")
    except Exception as exc:  # noqa: BLE001
        logger.warning("session.parser.parse() failed: %s", exc)
        return None


__all__ = ["AiderDriver"]
