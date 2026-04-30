"""Exception hierarchy for the coding-agent driver harness (ADR-009).

All driver-side failures derive from :class:`DriverError`, mirroring the
pattern used by ``SessionParseError`` and ``HookError`` so suite-level
``except`` clauses can opt into a single base.
"""

from __future__ import annotations


class DriverError(Exception):
    """Base class for every driver failure surfaced by AgentGuard."""


class DriverUnavailable(DriverError):  # noqa: N818 — Driver* family namespace
    """The underlying CLI is not installed / not on PATH or required env vars
    are missing. ``is_available()`` returned ``False`` and ``run()`` was
    nonetheless invoked. Tests should ``skip`` on this rather than ``fail``.
    """


class DriverTimeout(DriverError):  # noqa: N818 — Driver* family namespace
    """The wrapped CLI exceeded ``DriverConfig.timeout_seconds``."""


class DriverInvocationError(DriverError):
    """The CLI returned a non-zero exit code or its session log could not be
    located / decoded. Carries ``exit_code`` and ``stderr`` for diagnosis.
    """

    def __init__(
        self,
        message: str,
        *,
        exit_code: int | None = None,
        stderr: str | None = None,
    ) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.stderr = stderr


__all__ = [
    "DriverError",
    "DriverUnavailable",
    "DriverTimeout",
    "DriverInvocationError",
]
