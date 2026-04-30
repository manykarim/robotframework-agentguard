"""Unit tests for ``metrics.pack.compute_42796_pack`` — the one-shot aggregator
and end-to-end :class:`BehavioralReport` shape.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.conftest import load_session_json

try:
    from AgentGuard.coding_agent.metrics.pack import compute_42796_pack
    from AgentGuard.coding_agent.metrics.registry import METRICS
    from AgentGuard.coding_agent.metrics.types import BehavioralReport, MetricResult
    from AgentGuard.coding_agent.session.types import Session, ToolCall
except ImportError:  # pragma: no cover — Phase 3 race
    pytest.skip("phase3: metrics.pack not yet implemented", allow_module_level=True)

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "coding_agent" / "metrics"


# ---------------------------- shape ----------------------------------------


def test_pack_returns_behavioral_report() -> None:
    s = Session(id="x", source="claude-code")
    report = compute_42796_pack(s)
    assert isinstance(report, BehavioralReport)
    assert report.session_id == "x"


def test_pack_includes_every_registered_metric() -> None:
    s = Session(id="x", source="claude-code")
    report = compute_42796_pack(s)
    assert set(report.metrics.keys()) == set(METRICS.keys())


def test_pack_metric_count_is_twelve() -> None:
    s = Session(id="x", source="claude-code")
    report = compute_42796_pack(s)
    assert len(report.metrics) == 12


def test_pack_each_metric_is_metric_result() -> None:
    s = Session(id="x", source="claude-code")
    report = compute_42796_pack(s)
    for r in report.metrics.values():
        assert isinstance(r, MetricResult)


def test_pack_records_computed_at_timestamp() -> None:
    s = Session(id="x", source="claude-code")
    report = compute_42796_pack(s)
    assert report.computed_at is not None


# ---------------------------- aggregate health -----------------------------


def test_pack_healthy_for_clean_session(healthy_session: Any) -> None:
    report = compute_42796_pack(healthy_session)
    assert report.overall_health == "healthy"


def test_pack_degraded_for_pathological_session(degraded_session: Any) -> None:
    report = compute_42796_pack(degraded_session)
    assert report.overall_health == "degraded"


def test_pack_health_for_empty_session() -> None:
    """Empty session has no signal — every "above" metric (e.g. read_edit_ratio)
    naturally fails its threshold so verdict can be ``degraded``. We assert it
    is one of the three possible outcomes; specific verdict is implementation-defined.
    """
    s = Session(id="x", source="claude-code")
    report = compute_42796_pack(s)
    assert report.overall_health in {"healthy", "unknown", "degraded"}


def test_pack_optional_metric_does_not_force_unknown(degraded_session: Any) -> None:
    """``token_usage_per_prompt`` returns ``passed=None`` when no threshold —
    that alone must not flip overall health to ``unknown``."""
    report = compute_42796_pack(degraded_session)
    # multiple metrics fail; verdict must still be "degraded"
    assert report.overall_health == "degraded"


# ---------------------------- specific thresholds in degraded ---------------


def test_degraded_session_breaches_stop_hook(degraded_session: Any) -> None:
    report = compute_42796_pack(degraded_session)
    assert report.metrics["stop_hook_violations"].value > 0
    assert report.metrics["stop_hook_violations"].passed is False


def test_degraded_session_breaches_user_interrupts(degraded_session: Any) -> None:
    report = compute_42796_pack(degraded_session)
    assert report.metrics["user_interrupts_per_1k"].passed is False


def test_degraded_session_breaches_read_edit_ratio(degraded_session: Any) -> None:
    report = compute_42796_pack(degraded_session)
    # lots of edits with few reads
    assert report.metrics["read_edit_ratio"].value < 4.0
    assert report.metrics["read_edit_ratio"].passed is False


def test_healthy_session_passes_first_run_test_rate(healthy_session: Any) -> None:
    report = compute_42796_pack(healthy_session)
    res = report.metrics["first_run_test_pass_rate"]
    assert res.value > 0
    assert res.passed is True


def test_pack_baseline_kwarg_accepted() -> None:
    """``baseline=`` is reserved for the Mann-Whitney hook — pack must accept it."""
    s = Session(id="x", source="claude-code")
    report = compute_42796_pack(s, baseline=None)
    assert isinstance(report, BehavioralReport)


# ---------------------------- fixture loader sanity -------------------------


def test_fixture_loader_round_trips(degraded_session: Any) -> None:
    assert degraded_session.id == "degraded-001"
    assert len(degraded_session.tool_calls) > 0
    assert len(degraded_session.hook_events) > 0


def test_load_session_json_helper_works() -> None:
    sess = load_session_json(FIXTURES / "sample_session.json")
    assert sess.id == "healthy-001"
