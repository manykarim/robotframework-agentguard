"""Scenario YAML <-> dataclass round-trip (rf-mcp v1 schema, ADR-021).

The schema is byte-equivalent to ``manykarim/rf-mcp/tests/e2e/scenarios/*.yaml``.
Unknown frontmatter keys are kept under ``Scenario.metadata`` so future rf-mcp
schema bumps don't break old AgentGuard parsers (ADR-014 forwards-compat).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from AgentGuard.mcp_scenario.exceptions import (
    ScenarioResultError,
    ScenarioYAMLError,
)
from AgentGuard.mcp_scenario.types import (
    ExpectedToolCall,
    Scenario,
    ScenarioResult,
    ToolCallRecord,
)

_REQUIRED_KEYS: tuple[str, ...] = ("id", "prompt", "expected_outcome")


def load_scenario(path: str | Path) -> Scenario:
    """Parse ``path`` (a YAML file) into a :class:`Scenario`."""
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise ScenarioYAMLError(f"could not read scenario {path!r}: {exc}") from exc
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise ScenarioYAMLError(f"{path}: invalid YAML: {exc}") from exc
    return scenario_from_dict(data, source=str(p))


def scenario_from_dict(data: dict[str, Any], *, source: str | None = None) -> Scenario:
    """Translate a dict (from YAML or in-memory) into a :class:`Scenario`."""
    if not isinstance(data, dict):
        raise ScenarioYAMLError(f"scenario must be a mapping, got {type(data).__name__}")
    missing = [k for k in _REQUIRED_KEYS if k not in data]
    if missing:
        loc = source or "<inline>"
        raise ScenarioYAMLError(f"{loc}: missing required keys: {missing}")

    expected = []
    for entry in data.get("expected_tools") or []:
        if not isinstance(entry, dict) or "tool_name" not in entry:
            raise ScenarioYAMLError("expected_tools[] entries must be mappings with at least 'tool_name'")
        expected.append(
            ExpectedToolCall(
                tool_name=str(entry["tool_name"]),
                min_calls=int(entry.get("min_calls", 1)),
                max_calls=(int(entry["max_calls"]) if entry.get("max_calls") is not None else None),
                required_params=(dict(entry["required_params"]) if entry.get("required_params") else None),
            )
        )

    ctx = data.get("context", "generic")
    if ctx not in ("web", "api", "mobile", "desktop", "generic"):
        raise ScenarioYAMLError(f"context must be one of web|api|mobile|desktop|generic, got {ctx!r}")

    return Scenario(
        id=str(data["id"]),
        name=str(data.get("name", data["id"])),
        description=str(data.get("description", "")),
        prompt=str(data["prompt"]),
        expected_outcome=str(data["expected_outcome"]),
        context=ctx,
        expected_tools=expected,
        min_tool_hit_rate=float(data.get("min_tool_hit_rate", 0.8)),
        tags=[str(t) for t in (data.get("tags") or [])],
    )


def save_scenario(scenario: Scenario, path: str | Path) -> Path:
    """Write ``scenario`` back to YAML at ``path``; rf-mcp v1 schema."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = scenario_to_dict(scenario)
    out.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return out


def scenario_to_dict(scenario: Scenario) -> dict[str, Any]:
    return {
        "id": scenario.id,
        "name": scenario.name,
        "description": scenario.description,
        "context": scenario.context,
        "prompt": scenario.prompt,
        "expected_tools": [
            {
                "tool_name": e.tool_name,
                "min_calls": e.min_calls,
                **({"max_calls": e.max_calls} if e.max_calls is not None else {}),
                **({"required_params": dict(e.required_params)} if e.required_params else {}),
            }
            for e in scenario.expected_tools
        ],
        "expected_outcome": scenario.expected_outcome,
        "min_tool_hit_rate": scenario.min_tool_hit_rate,
        "tags": list(scenario.tags),
    }


# ---- ScenarioResult IO -----------------------------------------------------


def save_scenario_result(result: ScenarioResult, path: str | Path) -> Path:
    """Persist ``result`` as JSON at ``path``; rf-mcp metrics/*.json shape."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = scenario_result_to_dict(result)
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return out


def load_scenario_result(path: str | Path) -> ScenarioResult:
    """Read a previously-saved :class:`ScenarioResult` JSON."""
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScenarioResultError(f"could not load scenario result {path!r}: {exc}") from exc
    return scenario_result_from_dict(data)


def scenario_result_to_dict(result: ScenarioResult) -> dict[str, Any]:
    return asdict(result)


def scenario_result_from_dict(data: dict[str, Any]) -> ScenarioResult:
    raw_calls = data.get("tool_calls") or []
    calls = [
        ToolCallRecord(
            tool_name=str(r["tool_name"]),
            arguments=dict(r.get("arguments") or {}),
            success=bool(r.get("success", True)),
            result=r.get("result"),
            error=r.get("error"),
            timestamp=float(r.get("timestamp", 0.0)),
        )
        for r in raw_calls
    ]
    return ScenarioResult(
        scenario_id=str(data["scenario_id"]),
        success=bool(data.get("success", False)),
        tool_calls=calls,
        tool_hit_rate=float(data.get("tool_hit_rate", 0.0)),
        total_tool_calls=int(data.get("total_tool_calls", len(calls))),
        expected_tool_calls_met=int(data.get("expected_tool_calls_met", 0)),
        expected_tool_calls_total=int(data.get("expected_tool_calls_total", 0)),
        errors=list(data.get("errors") or []),
        execution_time_seconds=float(data.get("execution_time_seconds", 0.0)),
        agent_output=data.get("agent_output"),
        metadata=dict(data.get("metadata") or {}),
    )


__all__ = [
    "load_scenario",
    "load_scenario_result",
    "save_scenario",
    "save_scenario_result",
    "scenario_from_dict",
    "scenario_result_from_dict",
    "scenario_result_to_dict",
    "scenario_to_dict",
]
