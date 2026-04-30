"""Unit tests for ``CodingAgentKeywords`` — Robot keyword wrapper layer.

The wrapper composes drivers + parser + metric pack into a single Robot
Library. We test the public surface (Robot keyword names + assertion
contracts) without invoking real CLIs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import load_session_json

try:
    from AgentGuard.coding_agent.exceptions import (
        DriverDispatchError,
        MetricThresholdViolated,
        SessionParseFailed,
        SessionSchemaInvalid,
    )
    from AgentGuard.coding_agent.library import CodingAgentKeywords
    from AgentGuard.coding_agent.session.types import Session
except ImportError:  # pragma: no cover — Phase 3 race
    pytest.skip("phase3: coding_agent.library not yet implemented", allow_module_level=True)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "coding_agent"


@pytest.fixture
def kw() -> CodingAgentKeywords:
    return CodingAgentKeywords()


# ---------------------------- driver dispatch -----------------------------


def test_get_last_session_raises_before_any_run(kw: CodingAgentKeywords) -> None:
    with pytest.raises(DriverDispatchError):
        kw.get_last_coding_agent_session()


# ---------------------------- parser keywords -----------------------------


def test_parse_session_jsonl(kw: CodingAgentKeywords) -> None:
    s = kw.parse_session_jsonl(str(FIXTURES / "sessions" / "claude_code_minimal.jsonl"))
    assert s.id == "synthetic-min-001"
    assert s.source == "claude-code"


def test_parse_session_jsonl_unknown_format_raises(
    kw: CodingAgentKeywords, tmp_path: Path
) -> None:
    bad = tmp_path / "bad.jsonl"
    bad.write_text("not json\n")
    with pytest.raises(SessionParseFailed):
        kw.parse_session_jsonl(str(bad))


def test_save_and_load_session_snapshot_roundtrip(
    kw: CodingAgentKeywords, healthy_session: Session, tmp_path: Path
) -> None:
    out = tmp_path / "snap.json"
    kw.save_session_snapshot(healthy_session, str(out))
    assert out.exists()
    payload = json.loads(out.read_text())
    assert payload["id"] == "healthy-001"


def test_validate_session_schema_passes_for_good(
    kw: CodingAgentKeywords, healthy_session: Session
) -> None:
    assert kw.validate_session_schema(healthy_session) is True


def test_validate_session_schema_fails_for_empty_id(kw: CodingAgentKeywords) -> None:
    bad = Session(id="", source="x")
    with pytest.raises(SessionSchemaInvalid):
        kw.validate_session_schema(bad)


# ---------------------------- metric Get keywords -------------------------


def test_read_edit_ratio_value(kw: CodingAgentKeywords, healthy_session: Session) -> None:
    val = kw.read_edit_ratio(healthy_session)
    assert val > 0


def test_read_edit_ratio_should_be_above_passes(
    kw: CodingAgentKeywords, healthy_session: Session
) -> None:
    # healthy session has ratio 5 — passes threshold=4.0
    kw.read_edit_ratio_should_be_above(healthy_session, threshold=4.0)


def test_read_edit_ratio_should_be_above_fails(
    kw: CodingAgentKeywords, degraded_session: Session
) -> None:
    with pytest.raises(MetricThresholdViolated) as excinfo:
        kw.read_edit_ratio_should_be_above(degraded_session, threshold=4.0)
    assert excinfo.value.metric == "read_edit_ratio"


def test_stop_hook_violations_should_be_zero_passes(
    kw: CodingAgentKeywords, healthy_session: Session
) -> None:
    kw.stop_hook_violations_should_be_zero(healthy_session)


def test_stop_hook_violations_should_be_zero_fails(
    kw: CodingAgentKeywords, degraded_session: Session
) -> None:
    with pytest.raises(MetricThresholdViolated):
        kw.stop_hook_violations_should_be_zero(degraded_session)


def test_first_run_test_pass_rate_value(
    kw: CodingAgentKeywords, healthy_session: Session
) -> None:
    val = kw.first_run_test_pass_rate(healthy_session)
    assert 0.0 <= val <= 1.0


def test_token_usage_per_prompt_value(
    kw: CodingAgentKeywords, healthy_session: Session
) -> None:
    val = kw.token_usage_per_prompt(healthy_session)
    assert val > 0


def test_token_usage_below_with_explicit_threshold(
    kw: CodingAgentKeywords, healthy_session: Session
) -> None:
    # healthy session has 1200 total tokens / 2 user prompts = 600 — well below 100k.
    kw.token_usage_per_prompt_should_be_below(healthy_session, threshold=100_000)


def test_token_usage_below_requires_threshold_or_baseline(
    kw: CodingAgentKeywords, healthy_session: Session
) -> None:
    with pytest.raises(DriverDispatchError):
        kw.token_usage_per_prompt_should_be_below(healthy_session)


# ---------------------------- aggregate keywords --------------------------


def test_compute_42796_metric_pack(
    kw: CodingAgentKeywords, healthy_session: Session
) -> None:
    report = kw.compute_42796_metric_pack(healthy_session)
    assert hasattr(report, "metrics")
    assert len(report.metrics) == 12


def test_get_session_health_for_clean(
    kw: CodingAgentKeywords, healthy_session: Session
) -> None:
    assert kw.get_session_health(healthy_session) == "healthy"


def test_get_session_health_for_degraded(
    kw: CodingAgentKeywords, degraded_session: Session
) -> None:
    assert kw.get_session_health(degraded_session) == "degraded"


def test_compute_metric_pack_chains_into_health(
    kw: CodingAgentKeywords, degraded_session: Session
) -> None:
    report = kw.compute_42796_metric_pack(degraded_session)
    # Multiple thresholds breach in degraded fixture.
    failures = [k for k, v in report.metrics.items() if v.passed is False]
    assert len(failures) >= 5


# ---------------------------- ratio/loops Should Be helpers ----------------


def test_simplest_word_should_be_below_threshold_passes(
    kw: CodingAgentKeywords, healthy_session: Session
) -> None:
    kw.simplest_word_frequency_per_1k_should_be_below(healthy_session, threshold=10.0)


def test_self_admitted_errors_should_be_below_passes(
    kw: CodingAgentKeywords, healthy_session: Session
) -> None:
    kw.self_admitted_errors_per_1k_should_be_below(healthy_session, threshold=1.0)


def test_self_admitted_errors_should_be_below_fails(
    kw: CodingAgentKeywords, degraded_session: Session
) -> None:
    with pytest.raises(MetricThresholdViolated):
        kw.self_admitted_errors_per_1k_should_be_below(degraded_session, threshold=0.2)


def test_write_mutation_ratio_should_be_below_fails(
    kw: CodingAgentKeywords, degraded_session: Session
) -> None:
    with pytest.raises(MetricThresholdViolated):
        kw.write_mutation_ratio_should_be_below(degraded_session, threshold=0.06)


def test_user_interrupts_per_1k_should_be_below_fails(
    kw: CodingAgentKeywords, degraded_session: Session
) -> None:
    with pytest.raises(MetricThresholdViolated):
        kw.user_interrupts_per_1k_should_be_below(degraded_session, threshold=2.0)


def test_reasoning_loops_should_be_below_fails(
    kw: CodingAgentKeywords, degraded_session: Session
) -> None:
    with pytest.raises(MetricThresholdViolated):
        kw.reasoning_loops_per_1k_tool_calls_should_be_below(degraded_session, threshold=12.0)


# ---------------------------- run_coding_agent ----------------------------


def test_run_coding_agent_local_offline(tmp_path: Path) -> None:
    """`Run Coding Agent` end-to-end with a mock provider."""
    from decimal import Decimal

    from AgentGuard.providers.base import ChatResponse, Usage
    from AgentGuard.providers.mock import MockProvider

    provider = MockProvider(
        responses=[
            ChatResponse(
                text="ok",
                tool_calls=[],
                usage=Usage(prompt_tokens=5, completion_tokens=3, cost_usd=Decimal("0.0001")),
            )
        ]
    )
    kw = CodingAgentKeywords(provider=provider)
    result = kw.run_coding_agent(
        "hello",
        driver="local",
        jsonl_path=str(tmp_path / "out.jsonl"),
    )
    assert result.exit_code == 0
    assert (tmp_path / "out.jsonl").exists()


def test_run_coding_agent_unknown_driver_raises(kw: CodingAgentKeywords) -> None:
    with pytest.raises(DriverDispatchError):
        kw.run_coding_agent("hi", driver="not-a-driver")


def test_run_coding_agent_and_save_session_writes_snapshot(tmp_path: Path) -> None:
    from decimal import Decimal

    from AgentGuard.providers.base import ChatResponse, Usage
    from AgentGuard.providers.mock import MockProvider

    provider = MockProvider(
        responses=[
            ChatResponse(
                text="ok",
                usage=Usage(prompt_tokens=5, completion_tokens=3, cost_usd=Decimal("0.0001")),
            )
        ]
    )
    kw = CodingAgentKeywords(provider=provider)
    snap = tmp_path / "snap.json"
    kw.run_coding_agent_and_save_session(
        "hello", driver="local", save_to=str(snap)
    )
    assert snap.exists()


def test_get_last_session_after_run(tmp_path: Path) -> None:
    from decimal import Decimal

    from AgentGuard.providers.base import ChatResponse, Usage
    from AgentGuard.providers.mock import MockProvider

    provider = MockProvider(
        responses=[
            ChatResponse(
                text="ok",
                usage=Usage(prompt_tokens=5, completion_tokens=3, cost_usd=Decimal("0.0001")),
            )
        ]
    )
    kw = CodingAgentKeywords(provider=provider)
    kw.run_coding_agent(
        "hello", driver="local", jsonl_path=str(tmp_path / "out.jsonl")
    )
    sess = kw.get_last_coding_agent_session()
    assert sess is not None


# ---------------------------- snapshot load --------------------------------


def test_load_session_snapshot_failure_path(
    kw: CodingAgentKeywords, tmp_path: Path
) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not valid json")
    with pytest.raises(SessionParseFailed):
        kw.load_session_snapshot(str(bad))


def test_validate_session_schema_with_no_messages_attribute(
    kw: CodingAgentKeywords,
) -> None:
    class _BadSession:
        id = "x"
        messages = "not-a-list"

    with pytest.raises(SessionSchemaInvalid):
        kw.validate_session_schema(_BadSession())  # type: ignore[arg-type]


# ---------------------------- behavioral baseline -------------------------


def test_load_behavioral_report_passes_through_none(kw: CodingAgentKeywords) -> None:
    assert kw.load_behavioral_report(None) is None


def test_load_behavioral_report_passes_through_object(kw: CodingAgentKeywords) -> None:
    obj = object()
    assert kw.load_behavioral_report(obj) is obj  # type: ignore[arg-type]


def test_behavioral_report_should_match_baseline_no_samples(
    kw: CodingAgentKeywords, healthy_session: Session
) -> None:
    """When neither current nor baseline has samples, MW comparison is skipped
    and the keyword returns an empty pvalues dict (no regressions)."""
    cur = kw.compute_42796_metric_pack(healthy_session)
    pvalues = kw.behavioral_report_should_match_baseline(cur, cur)
    assert pvalues == {}


# ---------------------------- exhaustive metric Get + Should ---------------


_GET_KEYWORDS = (
    "edits_without_prior_read_percent",
    "first_run_test_pass_rate",
    "repeated_edits_per_file_count",
    "convention_violation_rate_for_session",
)


@pytest.mark.parametrize("name", _GET_KEYWORDS)
def test_every_get_keyword_returns_float(
    kw: CodingAgentKeywords, healthy_session: Session, name: str
) -> None:
    val = getattr(kw, name)(healthy_session)
    assert isinstance(val, float)


def test_edits_without_prior_read_should_be_below_passes(
    kw: CodingAgentKeywords, healthy_session: Session
) -> None:
    kw.edits_without_prior_read_percent_should_be_below(healthy_session, threshold=0.5)


def test_repeated_edits_per_file_should_be_below_passes(
    kw: CodingAgentKeywords, healthy_session: Session
) -> None:
    kw.repeated_edits_per_file_should_be_below(healthy_session, threshold=3.0)


def test_convention_violation_rate_should_be_below_passes(
    kw: CodingAgentKeywords, healthy_session: Session
) -> None:
    kw.convention_violation_rate_for_session_should_be_below(healthy_session, threshold=0.5)


def test_first_run_test_pass_rate_should_be_above_passes(
    kw: CodingAgentKeywords, healthy_session: Session
) -> None:
    kw.first_run_test_pass_rate_should_be_above(healthy_session, threshold=0.5)


def test_edits_without_prior_read_should_be_below_fails(
    kw: CodingAgentKeywords, degraded_session: Session
) -> None:
    with pytest.raises(MetricThresholdViolated):
        kw.edits_without_prior_read_percent_should_be_below(degraded_session, threshold=0.10)


def test_repeated_edits_per_file_should_be_below_fails(
    kw: CodingAgentKeywords, degraded_session: Session
) -> None:
    with pytest.raises(MetricThresholdViolated):
        kw.repeated_edits_per_file_should_be_below(degraded_session, threshold=1.0)


def test_simplest_word_should_be_below_fails(
    kw: CodingAgentKeywords, degraded_session: Session
) -> None:
    with pytest.raises(MetricThresholdViolated):
        kw.simplest_word_frequency_per_1k_should_be_below(degraded_session, threshold=5.0)


def test_convention_violation_rate_should_be_below_fails(
    kw: CodingAgentKeywords, degraded_session: Session
) -> None:
    with pytest.raises(MetricThresholdViolated):
        kw.convention_violation_rate_for_session_should_be_below(degraded_session, threshold=0.05)


def test_first_run_test_pass_rate_should_be_above_fails(
    kw: CodingAgentKeywords, degraded_session: Session
) -> None:
    with pytest.raises(MetricThresholdViolated):
        kw.first_run_test_pass_rate_should_be_above(degraded_session, threshold=0.9)


def test_write_mutation_ratio_should_be_below_passes(
    kw: CodingAgentKeywords, healthy_session: Session
) -> None:
    kw.write_mutation_ratio_should_be_below(healthy_session, threshold=0.06)


def test_token_usage_per_prompt_with_baseline_path(
    kw: CodingAgentKeywords, healthy_session: Session, tmp_path: Path
) -> None:
    """Provide a baseline JSON with a higher token_usage_per_prompt; current
    session should pass (it uses fewer tokens than baseline × multiplier)."""
    baseline_path = tmp_path / "baseline.json"
    baseline_data = {
        "token_usage_per_prompt": 1_000_000.0,
    }
    baseline_path.write_text(json.dumps(baseline_data))
    # baseline=1_000_000 × 1.5 = 1_500_000 → healthy session with ~600 passes.
    kw.token_usage_per_prompt_should_be_below(
        healthy_session, baseline=str(baseline_path), multiplier=1.5
    )
