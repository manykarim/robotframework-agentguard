"""Unit tests for ``metrics.registry`` — name-keyed catalog of #42796 metrics."""

from __future__ import annotations

import pytest

try:
    from AgentGuard.coding_agent.metrics import registry
    from AgentGuard.coding_agent.metrics.types import MetricResult
    from AgentGuard.coding_agent.session.types import Session
except ImportError:  # pragma: no cover — Phase 3 race
    pytest.skip("phase3: metrics.registry not yet implemented", allow_module_level=True)


def test_registry_contains_twelve_metrics() -> None:
    assert len(registry.METRICS) == 12


def test_metric_names_returns_list() -> None:
    names = registry.metric_names()
    assert isinstance(names, list)
    assert len(names) == 12


def test_canonical_metric_names_present() -> None:
    expected = {
        "read_edit_ratio",
        "edits_without_prior_read",
        "reasoning_loops_per_1k",
        "user_interrupts_per_1k",
        "stop_hook_violations",
        "first_run_test_pass_rate",
        "token_usage_per_prompt",
        "self_admitted_errors_per_1k",
        "write_mutation_ratio",
        "repeated_edits_per_file",
        "simplest_word_per_1k",
        "convention_violation_rate",
    }
    assert expected == set(registry.metric_names())


def test_get_metric_returns_spec() -> None:
    spec = registry.get_metric("read_edit_ratio")
    assert spec.name == "read_edit_ratio"
    assert spec.direction == "above"
    assert callable(spec.compute)


def test_get_metric_unknown_raises() -> None:
    with pytest.raises(KeyError):
        registry.get_metric("not-a-metric")


def test_compute_metric_uses_default_threshold_when_omitted() -> None:
    s = Session(id="x", source="claude-code")
    res = registry.compute_metric("read_edit_ratio", s)
    assert isinstance(res, MetricResult)
    assert res.threshold == 4.0


def test_compute_metric_threshold_override() -> None:
    s = Session(id="x", source="claude-code")
    res = registry.compute_metric("read_edit_ratio", s, threshold=99.0)
    assert res.threshold == 99.0


def test_compute_metric_threshold_none_disables() -> None:
    s = Session(id="x", source="claude-code")
    res = registry.compute_metric("read_edit_ratio", s, threshold=None)
    assert res.threshold is None
    assert res.passed is None


def test_metric_spec_is_frozen() -> None:
    spec = registry.get_metric("stop_hook_violations")
    with pytest.raises(Exception):
        spec.name = "mutated"  # type: ignore[misc]
