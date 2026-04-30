"""`agentguard` CLI — `doctor` + `version` subcommands.

`doctor` is intentionally fast and offline-friendly: every check is a boolean,
nothing is printed that could leak a credential, and an exit code of 0/1 means
all-pass / at-least-one-failed.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from AgentGuard import config
from AgentGuard._version import __version__

_REQUIRED_DEPS: tuple[str, ...] = (
    "robot",
    "robotlibcore",
    "litellm",
    "fastmcp",
    "mcp",
    "scipy",
    "numpy",
    "httpx",
    "dotenv",
    "yaml",
    "jsonschema",
    "opentelemetry",
    "rich",
)

_PACKAGE_FOR_VERSION: dict[str, str] = {
    "robot": "robotframework",
    "robotlibcore": "robotframework-pythonlibcore",
    "dotenv": "python-dotenv",
    "yaml": "pyyaml",
    "opentelemetry": "opentelemetry-api",
}


def _check_python() -> tuple[bool, str]:
    ok = sys.version_info >= (3, 12)
    return ok, f"Python {sys.version_info.major}.{sys.version_info.minor}"


def _check_imports() -> tuple[bool, str]:
    missing: list[str] = []
    for mod in _REQUIRED_DEPS:
        try:
            importlib.import_module(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        return False, f"missing: {', '.join(missing)}"
    return True, f"{len(_REQUIRED_DEPS)} deps importable"


def _check_env_file() -> tuple[bool, str]:
    candidate = Path.cwd() / ".env"
    if candidate.exists():
        return True, f"{candidate}"
    return False, f"no .env at {candidate}"


def _check_openrouter_key() -> tuple[bool, str]:
    config.load_env(Path.cwd() / ".env")
    present = config.has_openrouter_key()
    return present, "set" if present else "OPENROUTER_API_KEY not set"


def _check_claude_flow_mcp() -> tuple[bool, str]:
    try:
        import httpx
    except ImportError:
        return False, "httpx not installed"
    try:
        resp = httpx.get("http://127.0.0.1:3000/health", timeout=0.5)
        return resp.status_code < 500, f"HTTP {resp.status_code}"
    except Exception as exc:  # noqa: BLE001 — best-effort optional check
        return False, f"unreachable ({type(exc).__name__})"


_CHECKS: tuple[tuple[str, Callable[[], tuple[bool, str]], bool], ...] = (
    ("python>=3.12", _check_python, True),
    ("dependencies", _check_imports, True),
    (".env file", _check_env_file, False),
    ("OPENROUTER_API_KEY", _check_openrouter_key, False),
    ("claude-flow MCP @ :3000", _check_claude_flow_mcp, False),
)


def _doctor(_args: argparse.Namespace) -> int:
    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title=f"agentguard doctor — {__version__}")
    table.add_column("check", style="bold")
    table.add_column("status")
    table.add_column("detail")

    hard_failed = False
    for name, fn, required in _CHECKS:
        ok, detail = fn()
        status = "PASS" if ok else ("FAIL" if required else "WARN")
        style = "green" if ok else ("red" if required else "yellow")
        table.add_row(name, f"[{style}]{status}[/{style}]", detail)
        if required and not ok:
            hard_failed = True

    console.print(table)
    return 1 if hard_failed else 0


def _safe_version(pkg: str) -> str:
    try:
        return version(pkg)
    except PackageNotFoundError:
        return "?"


def _version(_args: argparse.Namespace) -> int:
    parts = [
        f"litellm={_safe_version('litellm')}",
        f"robotframework={_safe_version('robotframework')}",
        f"fastmcp={_safe_version('fastmcp')}",
        f"scipy={_safe_version('scipy')}",
    ]
    print(f"agentguard {__version__} ({', '.join(parts)})")  # noqa: T201
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agentguard")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_doctor = sub.add_parser("doctor", help="Environment and dependency self-check.")
    p_doctor.set_defaults(func=_doctor)

    p_version = sub.add_parser("version", help="Print agentguard + key dep versions.")
    p_version.set_defaults(func=_version)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
