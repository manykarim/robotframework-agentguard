"""Exception hierarchy for the session-parser sub-module.

All session-parser failures derive from :class:`SessionParseError`, mirroring
the ``HookError`` pattern in :mod:`AgentGuard.hooks.exceptions` so that
suite-level ``except`` clauses can opt into a single base.
"""

from __future__ import annotations


class SessionParseError(Exception):
    """Base class for every session-parser failure."""


class UnknownSessionFormatError(SessionParseError):
    """Auto-detection could not determine the JSONL/markdown source format
    (no extension match and no recognisable first-line shape)."""


class MalformedSessionError(SessionParseError):
    """The file exists and the format is identified but a record cannot be
    decoded (invalid JSON, missing required field, broken markdown block)."""


class UnpairedToolCallError(SessionParseError):
    """A ``tool_use`` record could not be paired with a ``toolUseResult``.

    Surfaced by strict-mode validation in :mod:`AgentGuard.coding_agent.session
    .claude_code`. Default parsing is permissive — it records unpaired calls
    in :attr:`Session.metadata` rather than raising.
    """


__all__ = [
    "SessionParseError",
    "UnknownSessionFormatError",
    "MalformedSessionError",
    "UnpairedToolCallError",
]
