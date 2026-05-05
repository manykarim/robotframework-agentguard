"""Artifact analysis — generated Robot Framework suites + JSON validators (ADR-021)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import jsonschema

from AgentGuard.mcp_scenario.exceptions import ScenarioResultError
from AgentGuard.mcp_scenario.types import ScenarioResult


def get_generated_robot_suites(result: ScenarioResult) -> list[Path]:
    """Return the list of Robot Framework suite paths the scenario produced.

    Convention: ``Run MCP Scenario`` writes ``metadata["generated_suites"]`` as
    a list of paths. If the scenario explicitly built suites via the rf-mcp
    ``build_test_suite`` tool, those paths land under ``metadata.suite_paths``
    too — we union both sources.
    """
    paths: list[Path] = []
    raw_a = result.metadata.get("generated_suites") or []
    raw_b = result.metadata.get("suite_paths") or []
    for r in [*raw_a, *raw_b]:
        try:
            paths.append(Path(r))
        except TypeError:
            continue
    # Fallback: scan tool_calls' results for {"suite_path": "..."} entries.
    for tc in result.tool_calls:
        suite = (tc.result or {}).get("suite_path") if isinstance(tc.result, dict) else None
        if isinstance(suite, str):
            paths.append(Path(suite))
    return [p for p in paths if p.exists()]


def get_generated_files(result: ScenarioResult) -> list[Path]:
    """Return arbitrary files the agent produced (per ``metadata['files_created']``)."""
    raw = result.metadata.get("files_created") or []
    return [Path(p) for p in raw if isinstance(p, (str, Path))]


def robot_dryrun(suite_path: Path, *, timeout_seconds: int = 60) -> tuple[int, str, str]:
    """Run ``robot --dryrun`` on ``suite_path``; return (exit_code, stdout, stderr)."""
    if not suite_path.exists():
        raise ScenarioResultError(f"suite path does not exist: {suite_path}")
    binary = shutil.which("robot")
    if binary is None:
        raise ScenarioResultError("robot binary not on PATH; install robotframework first")
    import tempfile

    with tempfile.TemporaryDirectory(prefix="agentguard_robot_dryrun_") as tmpdir:
        proc = subprocess.run(  # noqa: S603 — caller-supplied path
            [binary, "--dryrun", "--outputdir", tmpdir, str(suite_path)],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    return proc.returncode, proc.stdout, proc.stderr


def validate_json_artifact(payload: dict[str, Any] | list[Any], schema: dict[str, Any]) -> None:
    """JSON-Schema-validate ``payload`` against ``schema``; raise on failure."""
    jsonschema.Draft7Validator(schema).validate(payload)


__all__ = [
    "get_generated_files",
    "get_generated_robot_suites",
    "robot_dryrun",
    "validate_json_artifact",
]
