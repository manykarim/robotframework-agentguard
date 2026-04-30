"""Integration tests — full :class:`BehavioralReport` against synthetic Sessions
and the bundled fixtures.

These pin the cross-metric interactions: a single fixture must drive every
calculator, the aggregate health verdict must match the per-metric verdicts,
and Robot keyword wrappers must surface the same answer as the underlying
calculators.
"""

from __future__ import annotations

from typing import Any

import pytest

try:
    from AgentGuard.coding_agent.library import CodingAgentKeywords
    from AgentGuard.coding_agent.metrics.pack import compute_42796_pack
except ImportError:  # pragma: no cover — Phase 3 race
    pytest.skip("phase3: pack or library not yet implemented", allow_module_level=True)


@pytest.fixture
def kw() -> CodingAgentKeywords:
    return CodingAgentKeywords()


def test_healthy_aggregate_health_is_healthy(healthy_session: Any) -> None:
    report = compute_42796_pack(healthy_session)
    assert report.overall_health == "healthy"


def test_degraded_aggregate_health_is_degraded(degraded_session: Any) -> None:
    report = compute_42796_pack(degraded_session)
    assert report.overall_health == "degraded"


def test_degraded_breaches_at_least_seven_metrics(degraded_session: Any) -> None:
    report = compute_42796_pack(degraded_session)
    failed = [k for k, v in report.metrics.items() if v.passed is False]
    assert len(failed) >= 7, f"only {len(failed)} metrics failed: {failed}"


def test_keyword_wrapper_health_matches_pack(kw: CodingAgentKeywords, degraded_session: Any) -> None:
    via_pack = compute_42796_pack(degraded_session).overall_health
    via_keyword = kw.get_session_health(degraded_session)
    assert via_pack == via_keyword


def test_keyword_value_matches_pack_value(kw: CodingAgentKeywords, healthy_session: Any) -> None:
    pack_val = compute_42796_pack(healthy_session).metrics["read_edit_ratio"].value
    kw_val = kw.read_edit_ratio(healthy_session)
    assert pack_val == pytest.approx(kw_val)


def test_save_then_load_snapshot_roundtrip(kw: CodingAgentKeywords, healthy_session: Any, tmp_path: Any) -> None:
    snap = tmp_path / "snap.json"
    kw.save_session_snapshot(healthy_session, str(snap))
    # we don't load_session_snapshot here because it builds a Session from raw
    # JSON which is implementation-tested in test_library_wrapper.py — this
    # test only verifies the save side worked.
    assert snap.exists() and snap.stat().st_size > 0


def test_specific_thresholds_in_degraded(degraded_session: Any) -> None:
    report = compute_42796_pack(degraded_session)
    # Stop-hook violations > 0
    assert report.metrics["stop_hook_violations"].value > 0
    # Reasoning loops well above default 12.0/1k
    assert report.metrics["reasoning_loops_per_1k"].value > 12.0
    # Read:Edit below default 4.0
    assert report.metrics["read_edit_ratio"].value < 4.0
    # User interrupts above 2.0/1k
    assert report.metrics["user_interrupts_per_1k"].value > 2.0
