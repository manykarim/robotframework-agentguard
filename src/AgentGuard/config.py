"""Configuration helpers — `.env` loading, default-model resolution, feature flags.

`load_env` is idempotent and never raises if the file is missing (warns once).
`redact_env` MUST be used anywhere environment values may be logged or stored —
the OpenRouter / vendor API keys must never appear in plain text.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger("AgentGuard.config")

_DEFAULT_MODEL_FALLBACK = "openrouter/anthropic/claude-sonnet-4-5"
_DEFAULT_JUDGE_FALLBACK = "openrouter/openai/gpt-4o-mini"

_loaded_paths: set[str] = set()


def load_env(path: str | Path | None = ".env") -> None:
    """Load a `.env` file if present. Idempotent across calls.

    Missing file → warning + return (does NOT raise). Missing `python-dotenv`
    is also degraded to a warning so a slim install can still call us.
    """
    if path is None:
        return

    resolved = Path(path).resolve()
    key = str(resolved)
    if key in _loaded_paths:
        return

    if not resolved.exists():
        logger.warning("AgentGuard: .env file not found at %s — skipping.", resolved)
        _loaded_paths.add(key)
        return

    try:
        from dotenv import load_dotenv
    except ImportError:
        logger.warning("AgentGuard: python-dotenv not installed; skipping .env load.")
        _loaded_paths.add(key)
        return

    load_dotenv(dotenv_path=resolved, override=False)
    _loaded_paths.add(key)


def default_model() -> str:
    return os.getenv("AGENTGUARD_DEFAULT_MODEL", _DEFAULT_MODEL_FALLBACK)


def default_judge_model() -> str:
    return os.getenv("AGENTGUARD_JUDGE_MODEL", _DEFAULT_JUDGE_FALLBACK)


def feature_flag(name: str, default: bool = False) -> bool:
    """Read `AGENTGUARD_<NAME>` and parse a boolean (true/1/yes/on)."""
    env_key = f"AGENTGUARD_{name.upper()}"
    raw = os.getenv(env_key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _mask_value(value: str) -> str:
    if len(value) <= 4:
        return "****"
    return f"****{value[-4:]}"


def redact_env() -> dict[str, str]:
    """Return a copy of `os.environ` with all credential-shaped keys masked.

    Anything ending in `_API_KEY`, `_TOKEN`, `_SECRET`, or `_PASSWORD` is
    reduced to `****<last4>` so it can be safely logged or surfaced in
    `agentguard doctor`.
    """
    sensitive_suffixes = ("_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD")
    out: dict[str, str] = {}
    for key, value in os.environ.items():
        if any(key.endswith(suffix) for suffix in sensitive_suffixes):
            out[key] = _mask_value(value) if value else ""
        else:
            out[key] = value
    return out


def has_openrouter_key() -> bool:
    """Boolean probe for `OPENROUTER_API_KEY` — value is NEVER returned."""
    return bool(os.getenv("OPENROUTER_API_KEY", "").strip())
