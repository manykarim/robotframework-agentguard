"""Unit tests for the MCPScenario YAML loader (ADR-021)."""

from __future__ import annotations

from pathlib import Path

import pytest

from AgentGuard.mcp_scenario.exceptions import ScenarioYAMLError
from AgentGuard.mcp_scenario.loader import load_scenario, save_scenario, scenario_from_dict
from AgentGuard.mcp_scenario.types import Scenario

_MIN = {
    "id": "demo",
    "prompt": "Use add(2,3).",
    "expected_outcome": "5",
}


def test_scenario_from_dict_minimal() -> None:
    sc = scenario_from_dict(_MIN)
    assert sc.id == "demo"
    assert sc.name == "demo"  # defaults to id
    assert sc.context == "generic"
    assert sc.min_tool_hit_rate == 0.8
    assert sc.expected_tools == []


def test_scenario_from_dict_full() -> None:
    data = {
        **_MIN,
        "name": "Add Demo",
        "description": "computes 2+3",
        "context": "api",
        "expected_tools": [
            {"tool_name": "add", "min_calls": 1, "max_calls": 1},
            {"tool_name": "log", "min_calls": 0, "max_calls": 5, "required_params": {"level": "INFO"}},
        ],
        "min_tool_hit_rate": 0.9,
        "tags": ["demo", "math"],
    }
    sc = scenario_from_dict(data)
    assert sc.context == "api"
    assert len(sc.expected_tools) == 2
    assert sc.expected_tools[1].required_params == {"level": "INFO"}
    assert sc.tags == ["demo", "math"]


def test_scenario_from_dict_missing_required() -> None:
    with pytest.raises(ScenarioYAMLError, match="missing required keys"):
        scenario_from_dict({"id": "x"})


def test_scenario_from_dict_bad_context() -> None:
    with pytest.raises(ScenarioYAMLError, match="context"):
        scenario_from_dict({**_MIN, "context": "outer-space"})


def test_scenario_from_dict_bad_expected_tool() -> None:
    with pytest.raises(ScenarioYAMLError, match="expected_tools"):
        scenario_from_dict({**_MIN, "expected_tools": [{"min_calls": 1}]})  # no tool_name


def test_load_and_save_round_trip(tmp_path: Path) -> None:
    sc = scenario_from_dict({**_MIN, "expected_tools": [{"tool_name": "add"}]})
    out = save_scenario(sc, tmp_path / "demo.yaml")
    assert out.exists()
    loaded = load_scenario(out)
    assert loaded.id == sc.id
    assert loaded.expected_tools[0].tool_name == "add"


def test_load_real_rf_mcp_scenario_if_present(tmp_path: Path) -> None:
    upstream = Path.home() / "workspace" / "rf-mcp" / "tests" / "e2e" / "scenarios"
    if not upstream.exists():
        pytest.skip("upstream rf-mcp clone not available")
    for yml in upstream.glob("*.yaml"):
        sc = load_scenario(yml)
        assert isinstance(sc, Scenario)
        assert sc.id
        assert sc.prompt
        assert 0.0 <= sc.min_tool_hit_rate <= 1.0
