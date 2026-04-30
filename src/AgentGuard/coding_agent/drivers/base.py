"""``CodingAgentDriver`` Protocol + ``DriverConfig`` / ``DriverResult`` (ADR-009).

Each concrete driver subprocess-wraps a coding-agent CLI (or, in the case of
:class:`AgentGuard.coding_agent.drivers.local.LocalDriver`, runs an in-process
synthetic ReAct loop against an OpenRouter-backed provider) and emits a JSONL
session log shaped like Claude Code so the canonical session-parser can
consume it (research §7.2, exp_07).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover - import for typing only
    from AgentGuard.coding_agent.session.types import Session
else:  # pragma: no cover - runtime fallback when parser sibling isn't ready
    Session = Any  # type: ignore[assignment,misc]


_DEFAULT_SESSION_DIR = Path(".agentguard") / "sessions"


@dataclass(slots=True)
class DriverConfig:
    """Per-invocation driver knobs.

    All fields default to safe values so ``Driver.run(prompt)`` works
    without an explicit config in tests.
    """

    model: str | None = None
    cwd: str | None = None
    env: dict[str, str] | None = None
    timeout_seconds: int = 600
    max_turns: int = 25
    capture_jsonl: bool = True
    jsonl_path: str | Path | None = None
    extra_args: list[str] = field(default_factory=list)

    def resolved_cwd(self) -> Path:
        """Return the working directory as an absolute :class:`Path`."""
        return Path(self.cwd).resolve() if self.cwd else Path.cwd()

    def resolved_jsonl_path(self, driver_name: str) -> Path:
        """Compute the JSONL output path, generating one under
        ``.agentguard/sessions/`` if the user didn't supply one.
        """
        if self.jsonl_path is not None:
            return Path(self.jsonl_path)
        sid = uuid.uuid4().hex[:12]
        target_dir = self.resolved_cwd() / _DEFAULT_SESSION_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir / f"{driver_name}-{sid}.jsonl"


@dataclass(slots=True)
class DriverResult:
    """Outcome of a single :meth:`CodingAgentDriver.run` invocation."""

    driver: str
    exit_code: int
    cwd: str
    jsonl_path: str | None
    session: Session | None
    duration_ms: float
    cost_usd: float | None = None
    stdout: str = ""
    stderr: str = ""

    @property
    def succeeded(self) -> bool:
        """True iff the driver exited cleanly (``exit_code == 0``)."""
        return self.exit_code == 0


@runtime_checkable
class CodingAgentDriver(Protocol):
    """Stable driver surface — see ADR-009.

    Implementations MUST be importable without their backing CLI installed
    (so ``is_available()`` can return ``False`` cheaply); raise
    :class:`AgentGuard.coding_agent.drivers.exceptions.DriverUnavailable` from
    :meth:`run` if the CLI vanished between checks.
    """

    name: str

    def is_available(self) -> bool:
        """Cheap probe — does the underlying CLI exist on PATH (and any
        required env vars exist)? Must NOT raise.
        """
        ...

    def run(
        self,
        prompt: str,
        config: DriverConfig | None = None,
    ) -> DriverResult:
        """Execute ``prompt`` against the wrapped agent and return a
        :class:`DriverResult`. Caller may pass an explicit ``config``;
        otherwise a default :class:`DriverConfig` is used.
        """
        ...


__all__ = [
    "CodingAgentDriver",
    "DriverConfig",
    "DriverResult",
]
